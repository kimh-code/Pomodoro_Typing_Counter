import sys
import threading
from typing import Optional
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                           QWidget, QVBoxLayout, QHBoxLayout, 
                           QLineEdit, QDialog, QDesktopWidget)
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QPalette, QColor, QPainter, QPaintEvent
from pynput import keyboard
import time

def count_characters(text: str) -> int:
    """실제로 화면에 입력되는 문자만 카운트"""
    count = 0
    for char in str(text):
        if ((0xAC00 <= ord(char) <= 0xD7A3) or  # 완성된 한글
            (0x3131 <= ord(char) <= 0x314E) or  # 한글 자음
            (0x314F <= ord(char) <= 0x3163) or  # 한글 모음
            char.isalnum() or  # 영문자, 숫자
            char in '~!@#$%^&*()_+{}|:"<>?`-=[]\\;\',./'):  # 특수 문자
            count += 1
    return count

class SignalEmitter(QObject):
    """키보드 입력 시그널을 발생시키는 클래스"""
    character_count_signal = pyqtSignal(int)

class InitialSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('설정')
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # 목표 누적 타이핑 수 설정
        typing_count_layout = QHBoxLayout()
        typing_count_layout.addWidget(QLabel('목표 누적 타이핑 수:'))
        self.typing_count = QLineEdit()
        typing_count_layout.addWidget(self.typing_count)
        layout.addLayout(typing_count_layout)

        # 목표 누적 집중시간 설정
        total_focus_layout = QHBoxLayout()
        total_focus_layout.addWidget(QLabel('목표 누적 집중시간:'))
        self.total_focus_hours = QLineEdit()
        total_focus_layout.addWidget(self.total_focus_hours)
        total_focus_layout.addWidget(QLabel('시간'))
        self.total_focus_minutes = QLineEdit()
        total_focus_layout.addWidget(self.total_focus_minutes)
        total_focus_layout.addWidget(QLabel('분'))
        layout.addLayout(total_focus_layout)

        # 희망 누적 휴식시간 설정
        total_rest_layout = QHBoxLayout()
        total_rest_layout.addWidget(QLabel('희망 누적 휴식시간:'))
        self.total_rest_hours = QLineEdit()
        total_rest_layout.addWidget(self.total_rest_hours)
        total_rest_layout.addWidget(QLabel('시간'))
        self.total_rest_minutes = QLineEdit()
        total_rest_layout.addWidget(self.total_rest_minutes)
        total_rest_layout.addWidget(QLabel('분'))
        layout.addLayout(total_rest_layout)

        # 희망 저축된 휴식시간 설정
        saved_rest_layout = QHBoxLayout()
        saved_rest_layout.addWidget(QLabel('희망 저축된 휴식시간:'))
        self.target_saved_rest_hours = QLineEdit()
        saved_rest_layout.addWidget(self.target_saved_rest_hours)
        saved_rest_layout.addWidget(QLabel('시간'))
        self.target_saved_rest_minutes = QLineEdit()
        saved_rest_layout.addWidget(self.target_saved_rest_minutes)
        saved_rest_layout.addWidget(QLabel('분'))
        layout.addLayout(saved_rest_layout)

        # 목표 집중시간 설정 (디폴트 값 25분)
        focus_layout = QHBoxLayout()
        focus_layout.addWidget(QLabel('목표 집중시간:'))
        self.focus_hours = QLineEdit('0')  # 기본적으로 0시간 설정
        focus_layout.addWidget(self.focus_hours)
        focus_layout.addWidget(QLabel('시간'))
        self.focus_minutes = QLineEdit('25')  # 기본적으로 25분 설정
        focus_layout.addWidget(self.focus_minutes)
        focus_layout.addWidget(QLabel('분'))
        layout.addLayout(focus_layout)

        # 희망 휴식시간 설정 (디폴트 값 5분)
        rest_layout = QHBoxLayout()
        rest_layout.addWidget(QLabel('희망 휴식시간:'))
        self.rest_hours = QLineEdit('0')  # 기본적으로 0시간 설정
        rest_layout.addWidget(self.rest_hours)
        rest_layout.addWidget(QLabel('시간'))
        self.rest_minutes = QLineEdit('5')  # 기본적으로 5분 설정
        rest_layout.addWidget(self.rest_minutes)
        rest_layout.addWidget(QLabel('분'))
        layout.addLayout(rest_layout)

        # 알림 텍스트 설정
        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel('텍스트:'))
        self.alert_text = QLineEdit('집중해')
        text_layout.addWidget(self.alert_text)
        layout.addLayout(text_layout)

        # 확인 버튼
        self.ok_button = QPushButton('확인')
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def get_values(self):
        return {
            'target_typing': int(self.typing_count.text() or 0),
            'total_focus_time': (int(self.total_focus_hours.text() or 0) * 60 + 
                                int(self.total_focus_minutes.text() or 0)),
            'total_rest_time': (int(self.total_rest_hours.text() or 0) * 60 + 
                                int(self.total_rest_minutes.text() or 0)),
            'target_saved_rest_time': (int(self.target_saved_rest_hours.text() or 0) * 60 + 
                                        int(self.target_saved_rest_minutes.text() or 0)),
            'focus_time': (int(self.focus_hours.text() or 0) * 60 + 
                            int(self.focus_minutes.text() or 0)),
            'rest_time': (int(self.rest_hours.text() or 0) * 60 + 
                        int(self.rest_minutes.text() or 0)),
            'alert_text': self.alert_text.text()
        }

class PomodoroSession:
    def __init__(self, target_focus_time=25, target_rest_time=5):
        self.target_focus_time = target_focus_time  # 분 단위
        self.target_rest_time = target_rest_time    # 분 단위
        self.cycle_state = 'focus'
        self.time_left = self.target_focus_time * 60  # 초 단위
        self.focus_time = 0          # 현재 세션의 집중 시간 (초 단위)
        self.accumulated_focus = 0    # 전체 누적 집중 시간 (초 단위)
        self.accumulated_rest = 0     # 현재 휴식 시간 (초 단위)
        self.saved_rest_time = 0      # 저축된 휴식 시간 (분 단위)
        self.is_paused = True
        self.incomplete_focus = 0     # 일시정지 시 남은 집중 시간
        
        self.is_rest_cycle = True     # 첫 번째 집중시간의 초과분을 저장하기 위해 True로 시작
        self.current_cycle = 1        # 현재 사이클 번호
        self.current_session_complete = False
        self.last_cycle_state = None  # 일시정지 직전 상태 기억
        
        # 테두리 관련 변수들
        self.red_borders = []         # 빨간색 테두리 진행도 리스트
        self.green_borders = 0        # 완성된 초록색 테두리 개수
        self.current_green_progress = 0  # 현재 진행 중인 초록색 테두리 진행도

    def toggle_mode(self):
        """집중/휴식 모드 전환"""
        print(f"\n=== Mode Change ===")
        print(f"Previous State: {self.cycle_state}")
        
        if self.cycle_state == 'focus':
            # 집중 -> 휴식 전환시 현재 초과 시간 저장
            target_duration = self.target_focus_time * 60
            current_excess = max(0, self.focus_time - target_duration)
            self.saved_rest_time += current_excess / 60
            print(f"Final excess time: {current_excess}s")
            print(f"Total saved rest time: {self.saved_rest_time}min")
            
            self.cycle_state = 'rest'
            self.time_left = self.target_rest_time * 60
            self.accumulated_rest = 0
            
        else:
            self.cycle_state = 'focus'
            self.time_left = self.target_focus_time * 60
            self.focus_time = 0
        
        print(f"New State: {self.cycle_state}")
        print(f"Time Left: {self.time_left}s")
        print(f"Current saved rest time: {self.saved_rest_time}min")
        print(f"==================\n")

    def update(self):
        """1초마다 호출되는 업데이트 함수"""
        print(f"\nTimer State:")
        print(f"- Pomodoro Mode: {self.cycle_state}")
        print(f"- Button Color: {'Green' if self.cycle_state == 'focus' else 'Red'}")
        print(f"- Time Left: {self.time_left}s")
        print(f"- Is Paused: {self.is_paused}")
        
        if not self.is_paused:
            # 시간 감소
            self.time_left -= 1

            if self.time_left <= 0:
                print("\n=== Time's up! Mode Change ===")
                print(f"Before change:")
                print(f"- Pomodoro Mode: {self.cycle_state}")
                print(f"- Button Color: {'Green' if self.cycle_state == 'focus' else 'Red'}")
                
                # 현재 모드 변경 전에 초과 시간 처리
                if self.cycle_state == 'focus':
                    target_duration = self.target_focus_time * 60
                    current_excess = max(0, self.focus_time - target_duration)
                    self.saved_rest_time += current_excess / 60
                    print(f"Final excess time: {current_excess}s")
                    print(f"Total saved rest time: {self.saved_rest_time}min")
                
                # 모드 전환
                self.toggle_mode()
                
                print(f"After change:")
                print(f"- New Pomodoro Mode: {self.cycle_state}")
                print("===========================")

            if self.cycle_state == 'focus':
                self.focus_time += 1
                self.accumulated_focus += 1
                target_seconds = self.target_focus_time * 60
                print(f"Focus Mode - Current: {self.focus_time}s, Target: {target_seconds}s")
                
                # 추가 시간 계산
                if self.focus_time > target_seconds:
                    excess_focus = self.focus_time - target_seconds
                    print(f"Excess focus time detected: {excess_focus}s")
                    
                    # 초록색 재생버튼일 때 휴식모드라면 저축된 휴식시간 증가
                    border_color = self.pomo_start_button.styleSheet().find("#00FF00") != -1
                    if border_color and self.cycle_state == 'rest':
                        self.saved_rest_time += excess_focus / 60
                        print(f"Saved rest time: {self.pomo_session.saved_rest_time:.2f} minutes")

                        # border ratio 계산 (선택적)
                        if self.target_rest_time > 0:
                            border_ratio = self.saved_rest_time / self.target_rest_time
                            self.green_borders = int(border_ratio)
                            self.current_green_progress = border_ratio % 1
                            print(f"Border ratio: {border_ratio}")
                                                                                
    def pause(self):
        """일시정지"""
        if not self.is_paused:
            print(f"\n=== Timer Paused ===")
            print(f"Current State: {self.cycle_state}")
            print(f"Time Left: {self.time_left}s")
            print(f"==================\n")
            
            self.last_cycle_state = self.cycle_state
            self.incomplete_focus = self.time_left
            self.is_paused = True

    def resume(self):
        """재개"""
        if self.is_paused:
            print(f"\n=== Timer Resumed ===")
            print(f"Returning to State: {self.last_cycle_state}")
            print(f"Time Left: {self.incomplete_focus}s")
            print(f"==================\n")
            
            if self.last_cycle_state:
                self.cycle_state = self.last_cycle_state
            if self.incomplete_focus > 0 and self.cycle_state == 'focus':
                self.time_left = self.incomplete_focus
                self.incomplete_focus = 0
            self.is_paused = False
            self.last_cycle_state = None

    def get_display_time(self):
        """누적된 시간을 HH:MM 형식으로 변환"""
        total_minutes = self.accumulated_focus // 60  # 초를 분으로 변환
        hours = total_minutes // 60                   # 분을 시간으로 변환
        minutes = total_minutes % 60                  # 나머지 분
        return f"{hours:02d}:{minutes:02d}"

class PomodoroTypingCounter(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 상태 변수 초기화
        self.char_count = 0
        self.total_char_count = 0
        self.is_counting = False
        self.is_timer_paused = True
        self.hover_timer = None
        self.exit_timer = None
        self.is_opacity_locked = False
        self.last_alert_time = 0
        self.alert_interval = 600  # 10분 (초 단위)
        self.alert_window = None
        
        # 애니메이션 타이머
        self.border_animation_timer = QTimer()
        self.border_animation_timer.timeout.connect(self.update_border_animation)
        self.border_animation_timer.setInterval(50)
        
        self.border_animation_progress = 0.0
        self.is_removing_border = False
        
        # 타이머 설정
        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self.update_focus_time)
        self.focus_timer.setInterval(1000)
        
        self.rest_timer = QTimer()
        self.rest_timer.timeout.connect(self.update_rest_time)
        self.rest_timer.setInterval(1000)

        # UI 초기화 먼저
        self.initUI()

        # 설정 다이얼로그로 값 받기
        settings_dialog = InitialSettingsDialog(self)
        if settings_dialog.exec_() == QDialog.Accepted:
            self.apply_settings(settings_dialog.get_values())
        else:
            sys.exit()
        
        self.signal_emitter = SignalEmitter()
        self.signal_emitter.character_count_signal.connect(self.update_total_char_count)
        self.start_keyboard_listener()

        # 첫 시작 시 회색 재생버튼으로 설정
        self.set_button_inactive_state()

    def initUI(self):
        """UI 초기화"""
        # 윈도우 설정
        self.setGeometry(100, 100, 180, 180)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle('뽀모도로 타이핑 카운터')
        
        # 검은 배경 설정
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        
        # 버튼 스타일
        button_style = """
            QPushButton {
                background-color: #404040;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #808080;
            }
        """
        
        # 타이핑 관련 버튼들
        self.typing_start_button = QPushButton('▶', self)
        self.typing_start_button.setGeometry(10, 20, 50, 30)
        self.typing_start_button.setStyleSheet(button_style)
        self.typing_start_button.enterEvent = self.typing_start_hover
        self.typing_start_button.leaveEvent = self.typing_start_leave

        self.typing_pause_button = QPushButton('⏸', self)
        self.typing_pause_button.setGeometry(65, 20, 50, 30)
        self.typing_pause_button.setStyleSheet(button_style)
        self.typing_pause_button.enterEvent = self.typing_pause_hover
        self.typing_pause_button.leaveEvent = self.typing_pause_leave

        self.typing_reset_button = QPushButton('↺', self)
        self.typing_reset_button.setGeometry(120, 20, 50, 30)
        self.typing_reset_button.setStyleSheet(button_style)
        self.typing_reset_button.enterEvent = self.typing_reset_button_hover
        self.typing_reset_button.leaveEvent = self.typing_reset_button_leave
        
        # 타이핑 카운트 레이블
        self.typing_label = QLabel('0', self)
        self.typing_label.setGeometry(10, 60, 160, 30)
        self.typing_label.setStyleSheet("""
            color: white;
            background-color: transparent;
            font-size: 14px;
            font-weight: bold;
        """)
        self.typing_label.setAlignment(Qt.AlignCenter)
        self.typing_label.raise_()
        
        # 뽀모도로 관련 버튼들
        self.pomo_start_button = QPushButton('▶', self)
        self.pomo_start_button.setGeometry(10, 100, 50, 30)
        self.pomo_start_button.setStyleSheet(button_style)
        self.pomo_start_button.enterEvent = self.start_button_hover
        
        self.pomo_pause_button = QPushButton('⏸', self)
        self.pomo_pause_button.setGeometry(65, 100, 50, 30)
        self.pomo_pause_button.setStyleSheet(button_style)
        self.pomo_pause_button.enterEvent = self.pause_button_hover
        
        self.pomo_reset_button = QPushButton('↺', self)
        self.pomo_reset_button.setGeometry(120, 100, 50, 30)
        self.pomo_reset_button.setStyleSheet(button_style)
        self.pomo_reset_button.enterEvent = self.reset_button_hover
        self.pomo_reset_button.leaveEvent = self.reset_button_leave
        
        # 시간 표시 레이블
        self.time_label = QLabel('0:00', self)
        self.time_label.setGeometry(10, 140, 160, 35)
        self.time_label.setStyleSheet('color: white;')
        self.time_label.setAlignment(Qt.AlignCenter)
        
        # 축하 메시지 레이블
        self.typing_congrats_label = QLabel('축하', self)
        self.typing_congrats_label.setGeometry(10, 35, 160, 30)
        self.typing_congrats_label.setStyleSheet('color: yellow; font-size: 24px; font-weight: bold; background-color: rgba(0,0,0,0);')
        self.typing_congrats_label.setAlignment(Qt.AlignCenter)
        self.typing_congrats_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.typing_congrats_label.hide()
        
        self.focus_congrats_label = QLabel('축하', self)
        self.focus_congrats_label.setGeometry(10, 115, 160, 30)
        self.focus_congrats_label.setStyleSheet('color: yellow; font-size: 24px; font-weight: bold; background-color: rgba(0,0,0,0);')
        self.focus_congrats_label.setAlignment(Qt.AlignCenter)
        self.focus_congrats_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.focus_congrats_label.hide()
        
        # 멈춰 레이블
        self.stop_label = QLabel('멈춰', self)
        self.stop_label.setGeometry(10, 65, 160, 30)
        self.stop_label.setStyleSheet('color: red; font-size: 24px; font-weight: bold; background-color: rgba(0,0,0,0);')
        self.stop_label.setAlignment(Qt.AlignCenter)
        self.stop_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.stop_label.hide()
    
    def apply_settings(self, settings):
        self.target_typing = settings['target_typing']
        self.target_total_focus = settings['total_focus_time']
        self.target_total_rest = settings['total_rest_time']
        self.target_saved_rest = settings['target_saved_rest_time']
        self.target_focus = settings['focus_time']
        self.target_rest = settings['rest_time']
        self.alert_text = settings['alert_text']
        
        # PomodoroSession 초기화 시 분 단위로 전달
        self.pomo_session = PomodoroSession(
            target_focus_time=self.target_focus,
            target_rest_time=self.target_rest
        )

    def start_keyboard_listener(self):
        """키보드 리스너 시작 메서드"""
        def on_press(key):
            try:
                char = None
                
                # 일반 키보드 문자 처리
                if hasattr(key, 'char'):
                    char = key.char
                
                # vk 속성을 사용한 Numpad 키 처리
                if char is None and hasattr(key, 'vk'):
                    # Numpad 키의 가상 키(vk) 매핑
                    if 96 <= key.vk <= 105:  # Numpad 0-9 범위
                        char = str(key.vk - 96)  # 0-9로 변환
                    elif key.vk == 110:  # Numpad Decimal
                        char = '.'
                    elif key.vk == 107:  # Numpad Add
                        char = '+'
                    elif key.vk == 109:  # Numpad Subtract
                        char = '-'
                    elif key.vk == 106:  # Numpad Multiply
                        char = '*'
                    elif key.vk == 111:  # Numpad Divide
                        char = '/'
                
                # 특정 키 이름을 사용한 한글 자음 처리
                if char is None and hasattr(key, 'name'):
                    hangul_map = {
                        'ㄱ': 'ㄱ', 'ㄴ': 'ㄴ', 'ㄷ': 'ㄷ', 'ㄹ': 'ㄹ', 
                        'ㅁ': 'ㅁ', 'ㅂ': 'ㅂ', 'ㅅ': 'ㅅ', 'ㅇ': 'ㅇ',
                        'ㅈ': 'ㅈ', 'ㅊ': 'ㅊ', 'ㅋ': 'ㅋ', 'ㅌ': 'ㅌ', 
                        'ㅍ': 'ㅍ', 'ㅎ': 'ㅎ'
                    }
                    
                    if key.name in hangul_map:
                        char = hangul_map[key.name]
                
                # 눈에 보이지 않는 키 제외 (Enter, Ctrl, Space 등)
                if char is None or char in ['\r', '\x1b', ' ']:
                    return
                
                # 유효한 문자이고 카운팅 중일 때
                if self.is_counting and char is not None:
                    # 문자 수 카운트
                    chars_to_count = count_characters(char)
                    
                    # 카운트할 문자가 있는 경우에만 추가
                    if chars_to_count > 0:
                        self.total_char_count += chars_to_count
                        # signal_emitter를 통해 메인 스레드에 알림
                        self.signal_emitter.character_count_signal.emit(self.total_char_count)
                        
            except Exception as e:
                print(f"키보드 리스너 오류: {e}")
        
        # 별도의 스레드에서 키보드 리스너 실행
        def run_listener():
            with keyboard.Listener(on_press=on_press) as listener:
                self.keyboard_listener = listener
                listener.join()
        
        # 스레드 시작
        threading.Thread(target=run_listener, daemon=True).start()

    def update_border_animation(self):
        """테두리 애니메이션 업데이트"""
        if self.is_removing_border:
            self.border_animation_progress -= 0.1
            if self.border_animation_progress <= 0:
                self.border_animation_progress = 0
                if self.pomo_session.green_borders > 0:
                    self.pomo_session.green_borders -= 1
                    self.border_animation_progress = 1.0
                else:
                    self.border_animation_timer.stop()
                    self.is_removing_border = False
        else:
            self.border_animation_progress = min(1.0, self.border_animation_progress + 0.1)
            if self.border_animation_progress >= 1.0:
                self.border_animation_timer.stop()
        
        self.update()

    def update_focus_time(self):
        print("\n=== Focus Timer Update ===")
        print(f"Saved rest time: {self.pomo_session.saved_rest_time:.2f} minutes")
        print(f"Current cycle state: {self.pomo_session.cycle_state}")
        print(f"Time left: {self.pomo_session.time_left}")
        
        if not self.is_timer_paused:
            if self.pomo_session.time_left > 0:
                self.pomo_session.time_left -= 1
                
                is_green_button = self.pomo_start_button.styleSheet().find("#00FF00") != -1
                if is_green_button:
                    self.pomo_session.focus_time += 1
                    self.pomo_session.accumulated_focus += 1
                    
                    # 투명도 업데이트 추가
                    if not self.is_opacity_locked:
                        progress = min(1.0, self.pomo_session.accumulated_focus / (self.target_focus * 60))
                        opacity = max(0.1, 1.0 - (progress * 0.9))
                        self.setWindowOpacity(opacity)
                        print(f"Updating opacity during focus timer: {opacity * 100:.1f}%")

                    if self.pomo_session.cycle_state == 'rest':
                        self.pomo_session.saved_rest_time += 1/60
            
            # 시간이 다 되면 모드 전환
            if self.pomo_session.time_left <= 0:
                self.pomo_session.toggle_mode()
            
            self.update_time_label()
            self.calculate_border_ratio()

    def update_rest_time(self):
        print("\n=== Rest Timer Update ===")
        print(f"Saved rest time: {self.pomo_session.saved_rest_time:.2f} minutes")
        print(f"Current cycle state: {self.pomo_session.cycle_state}")
        print(f"Time left: {self.pomo_session.time_left}")
        
        if not self.is_timer_paused:
            if self.pomo_session.time_left > 0:
                self.pomo_session.time_left -= 1
                
                is_red_button = self.pomo_start_button.styleSheet().find("#FF0000") != -1
                if is_red_button and self.pomo_session.cycle_state == 'focus':
                    self.pomo_session.saved_rest_time -= 1/60
                
                # 투명도 업데이트 추가
                if not self.is_opacity_locked and self.pomo_session.saved_rest_time > 0:
                    ratio = min(self.pomo_session.saved_rest_time / self.target_rest, 1.0)
                    opacity = max(0.1, 1.0 - (ratio * 0.9))
                    self.setWindowOpacity(opacity)
                    print(f"Updating opacity during rest timer: {opacity * 100:.1f}%")
            
            # 시간이 다 되면 모드 전환
            if self.pomo_session.time_left <= 0:
                self.pomo_session.toggle_mode()
                
            self.pomo_session.accumulated_rest += 1
            self.update_time_label()
            self.calculate_border_ratio()

    def typing_pause_leave(self, event=None):
        """타이핑 일시정지 버튼에서 마우스가 벗어났을 때"""
        self.typing_pause_button.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
        """)

    def typing_reset_button_hover(self, event):
        """타이핑 리셋 버튼 호버"""
        if not self.hover_timer:
            self.hover_timer = QTimer()
            self.hover_timer.timeout.connect(self.reset_typing_counter)
            self.hover_timer.start(5000)
            self.typing_reset_button.setStyleSheet("""
                QPushButton {
                    background-color: #808080;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)

    def typing_reset_button_leave(self, event):
        """타이핑 리셋 버튼 호버 해제"""
        if self.hover_timer:
            self.hover_timer.stop()
            self.hover_timer = None
            self.typing_reset_button.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)

    def start_button_hover(self, event):
        """뽀모도로 시작 버튼 호버"""
        print("\n=== Start Button Hover ===")
        
        # 현재 버튼 상태 확인
        button_style = self.pomo_start_button.styleSheet()
        is_inactive_button = button_style.find("#404040") != -1
        is_green_button = button_style.find("#00FF00") != -1
        is_red_button = button_style.find("#FF0000") != -1
        
        # 버튼 색상 전환
        if is_green_button:
            self.focus_timer.stop()
            self.rest_timer.start()
            self.set_button_active_state(False)  # 빨간색으로 전환
        elif is_red_button or is_inactive_button:
            self.rest_timer.stop()
            self.focus_timer.start()
            self.set_button_active_state(True)   # 초록색으로 전환
        
        self.update_time_label()

    def pause_button_hover(self, event):
        """일시정지 버튼 호버"""
        print(f"일시정지 버튼 호버 - 현재 상태: {'일시정지' if self.is_timer_paused else '실행 중'}")
        
        if self.is_timer_paused:
            print("타이머 재개")
            self.pomo_session.resume()
            self.is_timer_paused = False
            if self.pomo_session.cycle_state == 'focus':
                self.focus_timer.start()
            else:
                self.rest_timer.start()
            self.set_button_active_state(self.pomo_session.cycle_state == 'focus')
            
            self.pomo_pause_button.setStyleSheet("""
                QPushButton {
                    background-color: #808080;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)
        else:
            print("타이머 일시정지")
            self.pomo_session.pause()
            self.is_timer_paused = True
            self.focus_timer.stop()
            self.rest_timer.stop()
            self.set_button_inactive_state()
            
            self.pomo_pause_button.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)
        
        self.update()

    def reset_button_hover(self, event):
        """뽀모도로 리셋 버튼 호버"""
        if not self.hover_timer:
            self.hover_timer = QTimer()
            self.hover_timer.timeout.connect(self.reset_counter)
            self.hover_timer.start(5000)
            self.pomo_reset_button.setStyleSheet("""
                QPushButton {
                    background-color: #808080;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)

    def reset_button_leave(self, event):
        """뽀모도로 리셋 버튼 호버 해제"""
        if self.hover_timer:
            self.hover_timer.stop()
            self.hover_timer = None
            self.pomo_reset_button.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)

    def show_alert(self):
        """알림 창 표시"""
        current_time = time.time()
        if (current_time - self.last_alert_time >= self.alert_interval and 
            self.pomo_session.cycle_state == 'rest' and
            self.alert_window is None):  # 이미 알림 창이 열려있지 않은 경우에만
            
            self.alert_window = QWidget(None, Qt.WindowStaysOnTopHint | Qt.Window)
            self.alert_window.setWindowState(Qt.WindowFullScreen)
            self.alert_window.setStyleSheet("background-color: rgba(0,0,0,0.8);")
            
            screen = QDesktopWidget().screenGeometry()
            
            alert_label = QLabel(self.alert_text, self.alert_window)
            alert_label.setStyleSheet("""
                color: white; 
                font-size: 200px; 
                font-weight: bold;
                background-color: rgba(0,0,0,0);
            """)
            alert_label.setAlignment(Qt.AlignCenter)
            alert_label.setGeometry(0, 0, screen.width(), screen.height())
            
            self.alert_window.setLayout(QVBoxLayout())
            self.alert_window.layout().addWidget(alert_label)
            
            def close_alert():
                self.alert_window.close()
                self.alert_window = None
                self.last_alert_time = time.time()
            
            self.alert_window.keyPressEvent = lambda e: close_alert() if e.key() == Qt.Key_Escape else None
            self.alert_window.show()


    def update_total_char_count(self, count):
        """타이핑 카운트 업데이트"""
        self.total_char_count = count
        self.typing_label.setText(str(self.total_char_count))
        
        # 목표 타이핑 수 달성 체크
        if self.total_char_count >= self.target_typing:
            self.show_typing_congratulation()
        self.update()  # UI 갱신

    def show_typing_congratulation(self):
        """타이핑 목표 달성 축하 메시지 표시"""
        self.typing_congrats_label.show()

    def show_focus_congratulation(self):
        """집중 완료 축하 메시지 표시"""
        self.focus_congrats_label.show()

    def update_time_label(self):
        seconds = self.pomo_session.accumulated_focus
        print(f"Raw seconds: {seconds}")
        
        # 디버깅을 위한 중간 계산 과정 출력
        calc_minutes = seconds / 60  # 부동소수점으로 계산
        print(f"Minutes (float): {calc_minutes}")
        
        minutes = int(calc_minutes)
        hours = minutes // 60
        final_minutes = minutes % 60
        
        print(f"Final calculation: {seconds}s -> {minutes}m -> {hours}h:{final_minutes}m")
        
        time_text = f"{hours:02d}:{final_minutes:02d}"
        self.time_label.setText(time_text)
        print(f"Time label updated: {time_text}")

    def calculate_border_ratio(self):
        """테두리 비율 계산"""
        print("\n=== Border Ratio Calculation ===")
        print(f"Current saved rest time: {self.pomo_session.saved_rest_time}")
        
        if self.target_rest <= 0:
            return 0
            
        if self.pomo_session.saved_rest_time <= 0:
            self.pomo_session.green_borders = 0
            self.pomo_session.current_green_progress = 0
            
            negative_ratio = abs(self.pomo_session.saved_rest_time) / self.target_rest
            current_progress = negative_ratio % 1
            
            if not self.pomo_session.red_borders:
                self.pomo_session.red_borders = [current_progress]
            else:
                self.pomo_session.red_borders[-1] = current_progress
                
                completed_borders = int(negative_ratio)
                while len(self.pomo_session.red_borders) < completed_borders + 1:
                    if current_progress >= 1.0:
                        self.pomo_session.red_borders.append(0.0)
            
            print(f"Negative ratio: {negative_ratio}")
            print(f"Red borders: {self.pomo_session.red_borders}")
            self.update()  # 화면 갱신 추가
            return negative_ratio
        
        else:
            self.pomo_session.red_borders = []
            ratio = self.pomo_session.saved_rest_time / self.target_rest
            self.pomo_session.green_borders = int(ratio)
            self.pomo_session.current_green_progress = ratio % 1
            self.update()  # 화면 갱신 추가
            return ratio

    def mousePressEvent(self, event):
        """마우스 클릭 이벤트"""
        if event.button() == Qt.LeftButton:
            self.dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """마우스 드래그 이벤트"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.dragPosition)
            event.accept()

    def enterEvent(self, event):
        """마우스가 창에 진입할 때"""
        print("\n=== Enter Event ===")
        print(f"Timer Paused: {self.is_timer_paused}")
        
        if not self.is_timer_paused:
            # 실제 집중모드일 때 (초록색 재생버튼)
            if self.pomo_start_button.styleSheet().find("#00FF00") != -1:
                print("Focus Mode (Green button) - Setting opacity to 100%")
                self.setWindowOpacity(1.0)
                self.is_opacity_locked = True
            
            # 실제 휴식모드일 때 (빨간색 재생버튼)
            elif self.pomo_start_button.styleSheet().find("#FF0000") != -1:
                print(f"Rest Mode (Red button)")
                print(f"Saved rest time: {self.pomo_session.saved_rest_time} minutes")
                # 저축된 휴식시간이 0 이하면 불투명
                if self.pomo_session.saved_rest_time <= 0:
                    print("Saved rest time <= 0 - Setting opacity to 100%")
                    self.setWindowOpacity(1.0)
                # 저축된 휴식시간이 0 초과면 불투명
                else:
                    print("Saved rest time > 0 - Setting opacity to 100%")
                    self.setWindowOpacity(1.0)
        
        current_opacity = self.windowOpacity()
        print(f"Current window opacity: {current_opacity * 100:.1f}%")

    def leaveEvent(self, event):
        """마우스가 창을 벗어날 때"""
        print("\n=== Leave Event ===")
        print(f"Timer Paused: {self.is_timer_paused}")
        
        if not self.is_timer_paused:
            # 실제 집중모드일 때 (초록색 재생버튼)
            if self.pomo_start_button.styleSheet().find("#00FF00") != -1:
                print("Focus Mode (Green button)")
                progress = min(1.0, self.pomo_session.accumulated_focus / (self.target_focus * 60))
                print(f"Progress: {progress:.2f}")
                opacity = max(0.1, 1.0 - (progress * 0.9))
                print(f"Calculated opacity: {opacity * 100:.1f}%")
                self.setWindowOpacity(opacity)
                self.is_opacity_locked = False
            
            # 실제 휴식모드일 때 (빨간색 재생버튼)
            elif self.pomo_start_button.styleSheet().find("#FF0000") != -1:
                print("Rest Mode (Red button)")
                saved_rest = self.pomo_session.saved_rest_time
                print(f"Saved rest time: {saved_rest:.2f} minutes")

                # 저축된 휴식시간이 0 이하
                if saved_rest <= 0:
                    print("Saved rest time <= 0 - Setting opacity to 100%")
                    self.setWindowOpacity(1.0)                
                # 저축된 휴식시간이 0 초과
                elif 0 < saved_rest <= self.target_rest:
                    print("0 < saved_rest <= target_rest - Setting opacity to 50%")
                    self.setWindowOpacity(0.5)                
                # 저축된 휴식시간이 희망 휴식시간 초과
                elif self.target_rest < saved_rest <= self.target_saved_rest:
                    print("target_rest < saved_rest <= target_saved_rest - Setting opacity to 30%")
                    self.setWindowOpacity(0.3)
                # 저축된 휴식시간이 희망 저축된 시간 초과
                else:
                    print("saved_rest > target_saved_rest - Setting opacity to 10%")
                    self.setWindowOpacity(0.1)
        
        current_opacity = self.windowOpacity()
        print(f"Final window opacity: {current_opacity * 100:.1f}%")

    def typing_start_hover(self, event=None):
        """타이핑 시작 버튼에 마우스를 올렸을 때"""
        self.is_counting = True
        self.typing_start_button.setStyleSheet("""
            QPushButton {
                background-color: #808080;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
        """)

    def typing_start_leave(self, event=None):
        """타이핑 시작 버튼에서 마우스가 벗어났을 때"""
        if not self.is_counting:
            self.typing_start_button.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)

    def typing_pause_hover(self, event=None):
        """타이핑 일시정지 버튼에 마우스를 올렸을 때"""
        self.is_counting = False
        self.typing_start_button.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        self.typing_pause_button.setStyleSheet("""
            QPushButton {
                background-color: #808080;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
        """)


    def reset_typing_counter(self):
        """타이핑 카운터 리셋"""
        self.total_char_count = 0
        self.typing_label.setText('0')
        if self.hover_timer:
            self.hover_timer.stop()
            self.hover_timer = None
        self.typing_congrats_label.hide()
        self.update()

    def reset_counter(self):
        """뽀모도로 카운터 리셋"""
        self.pomo_session = PomodoroSession(
            target_focus_time=self.target_focus,
            target_rest_time=self.target_rest
        )
        self.is_timer_paused = True
        self.focus_timer.stop()
        self.rest_timer.stop()
        self.border_animation_timer.stop()
        self.time_label.setText('0:00')
        self.focus_congrats_label.hide()
        self.stop_label.hide()
        self.border_animation_progress = 0
        self.is_removing_border = False
        self.setWindowOpacity(1.0)  # 투명도 초기화
        self.is_opacity_locked = False  # 투명도 잠금 해제
        self.set_button_inactive_state()
        self.update()

    def set_button_active_state(self, is_focus):
        """버튼 활성화 상태 설정"""
        color = "#00FF00" if is_focus else "#FF0000"
        state = "focus" if is_focus else "rest"
        print(f"Setting button state to {state} mode")
        
        self.is_timer_paused = False
        
        self.pomo_start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }}
        """)

    def set_button_inactive_state(self):
        """버튼 비활성화 상태 설정"""
        self.pomo_start_button.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
        """)

    def paintEvent(self, event: QPaintEvent):
        """화면 그리기 이벤트"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        print("\n=== Paint Event ===")
        
        # 타이핑 진행도 테두리 (흰색)
        if self.target_typing > 0:
            typing_ratio = min(1.0, self.total_char_count / self.target_typing)
            self.draw_border(painter, typing_ratio, QColor(255, 255, 255), 0)
        
        # 초록색 테두리들
        for i in range(self.pomo_session.green_borders):
            self.draw_border(painter, 1.0, QColor(0, 255, 0), i + 1)
        
        # 진행 중인 초록색 테두리
        if self.pomo_session.current_green_progress > 0:
            self.draw_border(painter, self.pomo_session.current_green_progress, 
                            QColor(0, 255, 0), self.pomo_session.green_borders + 1)
                                    
        # 빨간색 테두리들
        for i, progress in enumerate(self.pomo_session.red_borders):
            self.draw_border(painter, progress, QColor(255, 0, 0), i + 1)

    def draw_border(self, painter, progress, color, offset=0):
        """테두리 그리기"""
        MAX_BORDERS = 22  # 최대 테두리 수 제한
        
        if offset > MAX_BORDERS:
            return
            
        pen = painter.pen()
        pen.setColor(color)
        pen.setWidth(2)
        painter.setPen(pen)
        
        margin = offset * 4
        w = self.width() - (margin * 2)
        h = self.height() - (margin * 2)
        x, y = margin, margin
        
        total_length = 2 * (w + h)
        current_length = total_length * progress
        
        def draw_line_segment(start_x, start_y, end_x, end_y, available_length):
            segment_length = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5
            if available_length <= 0:
                return 0
            if available_length >= segment_length:
                painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))
                return segment_length
            ratio = available_length / segment_length
            painter.drawLine(
                int(start_x), 
                int(start_y),
                int(start_x + (end_x - start_x) * ratio),
                int(start_y + (end_y - start_y) * ratio)
            )
            return available_length
        
        remaining_length = current_length
        
        if color == QColor(255, 0, 0):  # 빨간색 테두리 (반시계 방향)
            # 시작: 좌측 상단
            # 왼쪽 (상→하)
            remaining_length -= draw_line_segment(x, y, x, y + h, remaining_length)
            if remaining_length > 0:
                # 하단 (좌→우)
                remaining_length -= draw_line_segment(x, y + h, x + w, y + h, remaining_length)
                if remaining_length > 0:
                    # 우측 (하→상)
                    remaining_length -= draw_line_segment(x + w, y + h, x + w, y, remaining_length)
                    if remaining_length > 0:
                        # 상단 (우→좌)
                        draw_line_segment(x + w, y, x, y, remaining_length)
        

        else:  # 녹색 또는 흰색 테두리 (시계 방향)
            # 좌상단에서 시작
            # 상단 (좌→우)
            remaining_length -= draw_line_segment(x, y, x + w, y, remaining_length)
            if remaining_length > 0:
                # 우측 (상→하)
                remaining_length -= draw_line_segment(x + w, y, x + w, y + h, remaining_length)
                if remaining_length > 0:
                    # 하단 (우→좌)
                    remaining_length -= draw_line_segment(x + w, y + h, x, y + h, remaining_length)
                    if remaining_length > 0:
                        # 좌측 (하→상)
                        draw_line_segment(x, y + h, x, y, remaining_length)


def main():
    app = QApplication(sys.argv)
    window = PomodoroTypingCounter()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()