import sys
import time
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLineEdit, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSlot, QRect
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor

import logging
logger = logging.getLogger(__name__)



# 导入事件总线和全局事件枚举（仅保留订阅重绘信号，截图信号无发布逻辑）
from core.global_event_enums import GlobalEvents
from core.event_bus import EventBusInstance

class PaintOnMinmap(QWidget):
    """
    小地图绘制组件：响应重绘信号，截图仅返回图像+当前时间（无事件总线发布）
    """
    def __init__(self, title: str = '', border_color: QColor = Qt.red, geometry: QRect = QRect(31, 1076, 360, 348)):
        super().__init__()
        self.window_title = title
        self.border_color = border_color
        self.is_title_bar_show = False  # 标题栏显示标志
        self.paint_list = []  # 绘制内容列表 [(文本, x比例, y比例)]

        self.init_ui(geometry)
        self.subscribe_signals()  # 订阅信号

    def init_ui(self, geometry):
        """初始化窗口样式"""
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowTransparentForInput
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(geometry)
        self.show()

    def subscribe_signals(self):
        """订阅小地图相关信号（仅重绘+截图触发，无发布）"""
        EventBusInstance.subscribe(GlobalEvents.REQ_MINIMAP_REPAINT, self.repaint)
        EventBusInstance.subscribe(GlobalEvents.REQ_MINIMAP_SCREENSHOT, self.capture_with_time)  # 绑定简化后的截图方法

    def paintEvent(self, event):
        """绘制事件：标题栏边框 / 红色文本"""
        if self.is_title_bar_show:
            # 绘制标题栏红色边框
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(self.border_color, 5))
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
        else:
            # 绘制红色文本
            with QPainter(self) as painter:
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(QPen(QColor(255, 0, 0), 1))

                # 设置字体
                font = painter.font()
                font.setPointSize(12)
                font.setBold(True)
                painter.setFont(font)

                # 遍历绘制内容
                for text, x, y in self.paint_list:
                    text_rect = painter.boundingRect(0, 0, 0, 0, Qt.AlignLeft, text)
                    draw_x = self.width() * x - text_rect.width() / 2
                    draw_y = self.height() * y + text_rect.height() / 2
                    painter.drawText(int(draw_x), int(draw_y), text)

    @pyqtSlot(list)
    def repaint(self, paint_list: list):
        """响应重绘信号：更新绘制列表并触发重绘"""
        self.paint_list = paint_list
        self.update()

    @pyqtSlot()
    def show_title_bar(self):
        """显示标题栏（带边框）"""
        old_geo = self.geometry()
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.CustomizeWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            & (~Qt.WindowMinimizeButtonHint)
            & (~Qt.WindowMaximizeButtonHint)
            & (~Qt.WindowCloseButtonHint)
        )
        self.setWindowTitle(self.window_title)
        self.setWindowOpacity(0.5)
        self.setGeometry(old_geo)
        self.is_title_bar_show = True
        self.show()

    @pyqtSlot()
    def hide_title_bar(self):
        """隐藏标题栏（恢复绘制）"""
        old_geo = self.geometry()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowTransparentForInput
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setWindowOpacity(1.0)
        self.setGeometry(old_geo)
        self.is_title_bar_show = False
        self.show()

    @pyqtSlot()
    def captureUnderWindow(self):
        """隐藏窗口并获取下方截图，返回QPixmap"""
        old_opacity = self.windowOpacity()
        self.setWindowOpacity(0.0)
        QApplication.processEvents()

        # 获取截图
        screen = QApplication.primaryScreen()
        geo = self.geometry()
        screenshot = screen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())

        # 恢复窗口
        self.setWindowOpacity(old_opacity)
        QApplication.processEvents()

        EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT] = screenshot

        return screenshot

    @pyqtSlot()
    def capture_with_time(self, *args):
        """
        简化版截图方法：仅返回截图图像和当前时间（无事件总线发布）
        *args：兼容信号传递的多余参数，修复 TypeError 报错
        :return: (screenshot_pixmap, capture_time)
        """

        logger.debug("接收到REQ_MINIMAP_SCREENSHOT信号，开始截图")

        # 获取截图和当前高精度时间
        screenshot_pixmap = self.captureUnderWindow()
        capture_time = time.perf_counter()

        logger.debug(f"截图完成")


        # 仅返回数据，无任何发布操作
        return screenshot_pixmap, capture_time

if __name__ == '__main__':
    # 简洁调试窗口：仅保留核心测试功能
    class DebugWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("PaintOnMINIMAP 调试")
            self.resize(400, 300)
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

            # 实例化小地图组件
            self.paint_win = PaintOnMinmap(title="测试小地图", border_color=Qt.red)
            self.paint_win.paint_list = [("A", 0.79, 0.53)]

            # 布局和控件
            self.main_layout = QVBoxLayout()
            self._init_input_widgets()
            self._init_button_widgets()
            self.setLayout(self.main_layout)

        def _init_input_widgets(self):
            """初始化输入控件（文本/X/Y比例）"""
            # 文本输入
            text_layout = QHBoxLayout()
            text_layout.addWidget(QLabel("绘制文本："))
            self.text_edit = QLineEdit("A")
            text_layout.addWidget(self.text_edit)
            self.main_layout.addLayout(text_layout)

            # X比例输入
            x_layout = QHBoxLayout()
            x_layout.addWidget(QLabel("X比例："))
            self.x_edit = QLineEdit("0.79")
            x_layout.addWidget(self.x_edit)
            self.main_layout.addLayout(x_layout)

            # Y比例输入
            y_layout = QHBoxLayout()
            y_layout.addWidget(QLabel("Y比例："))
            self.y_edit = QLineEdit("0.53")
            y_layout.addWidget(self.y_edit)
            self.main_layout.addLayout(y_layout)

        def _init_button_widgets(self):
            """初始化功能按钮"""
            # 手动更新绘制
            self.btn_update = QPushButton("手动更新绘制")
            self.btn_update.clicked.connect(self.update_paint)
            self.main_layout.addWidget(self.btn_update)

            # 信号触发重绘
            self.btn_signal_repaint = QPushButton("信号触发重绘")
            self.btn_signal_repaint.clicked.connect(self.trigger_repaint)
            self.main_layout.addWidget(self.btn_signal_repaint)

            # 信号触发截图（获取返回的图像和时间）
            self.btn_signal_capture = QPushButton("信号触发截图（获取图像+时间）")
            self.btn_signal_capture.clicked.connect(self.trigger_capture_and_get_data)
            self.main_layout.addWidget(self.btn_signal_capture)

            # 窗口切换按钮
            self.btn_show_title = QPushButton("显示标题栏")
            self.btn_hide_title = QPushButton("隐藏标题栏")
            self.btn_show_title.clicked.connect(self.paint_win.show_title_bar)
            self.btn_hide_title.clicked.connect(self.paint_win.hide_title_bar)
            self.main_layout.addWidget(self.btn_show_title)
            self.main_layout.addWidget(self.btn_hide_title)

            # 手动截图保存
            self.btn_save = QPushButton("手动截图保存")
            self.btn_save.clicked.connect(self.save_screenshot)
            self.main_layout.addWidget(self.btn_save)

        @pyqtSlot()
        def update_paint(self):
            """手动更新绘制内容"""
            try:
                text = self.text_edit.text().strip() or "默认文本"
                x = max(0.0, min(1.0, float(self.x_edit.text())))
                y = max(0.0, min(1.0, float(self.y_edit.text())))
                self.paint_win.paint_list = [(text, x, y)]
                self.paint_win.update()
            except ValueError as e:
                print(f"输入错误：{e}")

        @pyqtSlot()
        def trigger_repaint(self):
            """信号触发重绘"""
            try:
                text = self.text_edit.text().strip() or "信号文本"
                x = max(0.0, min(1.0, float(self.x_edit.text())))
                y = max(0.0, min(1.0, float(self.y_edit.text())))
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_REPAINT, [(text, x, y)])
            except ValueError as e:
                print(f"信号重绘失败：{e}")

        @pyqtSlot()
        def trigger_capture_and_get_data(self):
            """信号触发截图，并获取返回的图像和时间"""
            # 直接调用截图方法（或通过信号触发后获取返回值）
            screenshot_pixmap, capture_time = self.paint_win.capture_with_time()
            print(f"截图获取成功：")
            print(f"  - 截图尺寸：{screenshot_pixmap.width()}x{screenshot_pixmap.height()}")
            print(f"  - 当前时间戳：{capture_time:.6f}")
            # 如需保存，可在此处处理
            # screenshot_pixmap.save(f"minimap_{capture_time:.6f}.png")

        @pyqtSlot()
        def save_screenshot(self):
            """手动截图并保存"""
            pixmap, _ = self.paint_win.capture_with_time()
            pixmap.save("minimap_screenshot.png")
            print("截图已保存：minimap_screenshot.png")

    # 运行调试
    app = QApplication(sys.argv)
    debug_win = DebugWindow()
    debug_win.show()
    sys.exit(app.exec_())