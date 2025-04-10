import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QInputDialog
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPalette, QColor, QPainter
from pynput import keyboard
import threading

class TypingCounter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.char_count = 0
        self.is_counting = False
        self.hover_timer = None
        self.reset_hover_count = 0
        self.exit_timer = None
        self.target_count = self.get_target_count()
        self.showing_congrats = False
        self.initUI()
        self.init_keyboard_listener()

    def get_target_count(self):
        number, ok = QInputDialog.getInt(self, '목표 설정', '목표 글자 수를 입력하세요:', 100, 1, 100000, 1)
        if ok:
            return number
        else:
            sys.exit()

    def initUI(self):
        # 창 설정
        self.setGeometry(100, 100, 180, 100)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle('타이핑 카운터')
        
        # 배경색 설정 (검정)
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

        # 시작 버튼
        self.start_button = QPushButton('▶', self)
        self.start_button.setGeometry(10, 20, 50, 30)
        self.start_button.setStyleSheet(button_style)
        self.start_button.enterEvent = self.start_button_hover
        
        # 일시정지 버튼
        self.pause_button = QPushButton('⏸', self)
        self.pause_button.setGeometry(65, 20, 50, 30)
        self.pause_button.setStyleSheet(button_style)
        self.pause_button.enterEvent = self.pause_button_hover
        
        # 초기화 버튼
        self.reset_button = QPushButton('↺', self)
        self.reset_button.setGeometry(120, 20, 50, 30)
        self.reset_button.setStyleSheet(button_style)
        self.reset_button.enterEvent = self.reset_button_hover
        self.reset_button.leaveEvent = self.reset_button_leave

        # 카운터 레이블
        self.counter_label = QLabel('0', self)
        self.counter_label.setGeometry(10, 60, 160, 30)
        self.counter_label.setStyleSheet('color: white;')
        self.counter_label.setAlignment(Qt.AlignCenter)

        # 축하 메시지 레이블
        self.congrats_label = QLabel('축하', self)
        self.congrats_label.setGeometry(0, 0, 180, 100)
        self.congrats_label.setStyleSheet('color: yellow; font-size: 24px; font-weight: bold; background-color: rgba(0,0,0,0);')
        self.congrats_label.setAlignment(Qt.AlignCenter)
        self.congrats_label.setAttribute(Qt.WA_TransparentForMouseEvents)  # 마우스 이벤트가 레이블을 통과하도록 설정
        self.congrats_label.hide()

        self.show()

    def paintEvent(self, event):
        if not self.showing_congrats and self.char_count > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 테두리 그리기
            progress = min(self.char_count / self.target_count, 1.0)
            pen = painter.pen()
            pen.setColor(QColor(255, 255, 255))  # 흰색
            pen.setWidth(2)
            painter.setPen(pen)
            
            # 진행도에 따라 테두리 그리기
            w, h = self.width(), self.height()
            total_length = 2 * (w + h)  # 전체 테두리 길이
            progress_length = int(total_length * progress)  # 현재 진행도에 따른 길이
            
            # 테두리를 시계방향으로 그리기
            # 위쪽
            top_length = min(progress_length, w)
            if top_length > 0:
                painter.drawLine(0, 0, int(top_length), 0)
            
            # 오른쪽
            if progress_length > w:
                right_length = min(progress_length - w, h)
                painter.drawLine(w, 0, w, int(right_length))
            
            # 아래쪽
            if progress_length > w + h:
                bottom_length = min(progress_length - (w + h), w)
                painter.drawLine(w, h, w - int(bottom_length), h)
            
            # 왼쪽
            if progress_length > 2 * w + h:
                left_length = min(progress_length - (2 * w + h), h)
                painter.drawLine(0, h, 0, h - int(left_length))

    def init_keyboard_listener(self):
        def on_press(key):
            if self.is_counting:
                self.char_count += 1
                self.counter_label.setText(f'{self.char_count}')
                
                if self.char_count == self.target_count:
                    self.show_congratulation()
                
                self.update()  # 화면 갱신하여 타원 업데이트

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

    def show_congratulation(self):
        self.showing_congrats = True
        self.congrats_label.show()
        self.update()

    def hide_congratulation(self):
        self.showing_congrats = False
        self.congrats_label.hide()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.dragPosition)
            event.accept()

    def start_button_hover(self, event):
        self.is_counting = True
        self.update_button_states('start')

    def pause_button_hover(self, event):
        self.is_counting = False
        self.update_button_states('pause')

    def reset_button_hover(self, event):
        if not self.hover_timer:
            self.hover_timer = QTimer()
            self.hover_timer.timeout.connect(self.reset_counter)
            self.hover_timer.start(5000)
            self.update_button_states('reset')

    def reset_button_leave(self, event):
        if self.hover_timer:
            self.hover_timer.stop()
            self.hover_timer = None
            self.update_button_states('')

    def reset_counter(self):
        self.char_count = 0
        self.counter_label.setText(f'{self.char_count}')
        self.hover_timer.stop()
        self.hover_timer = None
        self.update_button_states('')
        self.hide_congratulation()  # 초기화 시 축하 텍스트 숨기기
        self.update()

    def update_button_states(self, active_button):
        dark_style = """
            background-color: #404040;
            color: white;
            border: none;
            padding: 10px;
            border-radius: 5px;
        """
        light_style = """
            background-color: #808080;
            color: white;
            border: none;
            padding: 10px;
            border-radius: 5px;
        """
        
        self.start_button.setStyleSheet(light_style if active_button == 'start' else dark_style)
        self.pause_button.setStyleSheet(light_style if active_button == 'pause' else dark_style)
        self.reset_button.setStyleSheet(light_style if active_button == 'reset' else dark_style)

    def enterEvent(self, event):
        if not self.exit_timer:
            self.exit_timer = QTimer()
            self.exit_timer.timeout.connect(self.close)
            self.exit_timer.start(30000)

    def leaveEvent(self, event):
        if self.exit_timer:
            self.exit_timer.stop()
            self.exit_timer = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TypingCounter()
    sys.exit(app.exec_())