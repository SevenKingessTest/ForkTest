# 导入必要的Qt模块
import time
import logging
import numpy as np
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, pyqtSlot, QPoint, QTimer, QRect
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QImage  # 新增导入QPainter（绘制）、QPen（画笔）

from core.global_event_enums import GlobalEvents
from core.event_bus import EventBusInstance

# 配置日志
logger = logging.getLogger(__name__)

class Screenshot(QWidget):
    def __init__(self, parent=None, title: str = '', border_color: QColor = Qt.red, geometry: QRect = QRect(800, 1000, 80, 60)):
        super().__init__(parent)
        # 初始化窗口属性
        self.window_title = title
        self.border_color = border_color

        self.init_ui(geometry)

    def init_ui(self, geometry):
        # 初始窗口样式（默认无标题栏）
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        # 设置窗口背景透明开启，这个当窗口是FramelessWindowHint时才生效
        # 一个不知道的原因，必须要这个开启后才能让鼠标穿透窗口点击
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 设置窗口半透明
        self.setWindowOpacity(0.5)

        # 标志位：是否显示标题栏
        self.is_title_bar_show = False

        self.setGeometry(geometry)

        self.show()

    # 重写paintEvent绘制事件，专门绘制红色边框
    def paintEvent(self, event):
        if self.is_title_bar_show:
            # 创建绘制对象
            painter = QPainter(self)
            # 抗锯齿设置（让边框更平滑）
            painter.setRenderHint(QPainter.Antialiasing, True)

            # 创建红色画笔，设置边框宽度（可自行调整，如5）
            pen = QPen(self.border_color, 5)  # 第一个参数：颜色（Qt.red/Qt.darkRed等），第二个参数：边框宽度
            # 将画笔绑定到绘制对象
            painter.setPen(pen)

            # 绘制矩形边框（窗口客户区范围）
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))  # 微调矩形，避免边框被窗口边缘裁剪

    @pyqtSlot()
    def show_title_bar(self):
        old_geometry = self.geometry()

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

        self.setGeometry(old_geometry)
        self.is_title_bar_show = True
        self.show()

    @pyqtSlot()
    def hide_title_bar(self):
        old_geometry = self.geometry()

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )

        self.setGeometry(old_geometry)
        self.is_title_bar_show = False
        self.show()

    def get_frameless_screenshot(self):
        """
        获取当前组件不包含标题栏的窗口截图
        返回：QPixmap对象，可保存为图片或进一步处理
        """
        screen = QApplication.primaryScreen()
        window_geo = self.geometry()
        screenshot = screen.grabWindow(0, window_geo.x(), window_geo.y(), window_geo.width(), window_geo.height())

        return screenshot

    def subscribe_screenshot_trigger(self, req_event: GlobalEvents, res_event: GlobalEvents):
        """
        新增：订阅指定的GlobalEvents信号，当信号触发时自动获取无标题栏截图并附带perf_counter高精度时间戳
        :param target_event: GlobalEvents枚举中的某个信号，作为截图触发的触发器
        """
        # 定义信号回调函数，接收信号传递的参数
        def on_trigger_signal_received(*args, **kwargs):
            """
            信号触发后的回调逻辑：
            1. 获取信号触发时刻的perf_counter时间戳（高精度，不受系统时间修改影响）
            2. 调用截图方法获取无标题栏截图
            3. 可按需将截图和时间戳发布到事件总线，方便其他模块获取
            """

            # 自动获取无标题栏截图
            frameless_screenshot = self.get_frameless_screenshot()
            # 获取信号触发时的高精度时间戳
            trigger_perf_time = time.perf_counter()

            # 发布截图和时间戳到事件总线，其他模块可订阅获取
            # EventBusInstance.publish(res_event, (frameless_screenshot, trigger_perf_time))
            EventBusInstance.shared_data[res_event] = (frameless_screenshot, trigger_perf_time)

            # 日志提示截图已获取
            logger.info(
                f"接收到触发信号：{req_event.name} | "
                f"发布响应信号：{res_event.name} | "
                f"截图触发时间戳（perf_counter）：{trigger_perf_time:.6f} | "
                f"截图尺寸：{frameless_screenshot.width()}x{frameless_screenshot.height()}"
            )

            # 返回截图和时间戳（方便直接调用回调时获取结果）
            return frameless_screenshot, trigger_perf_time

        # 订阅目标GlobalEvents信号，绑定回调函数
        EventBusInstance.subscribe(req_event, on_trigger_signal_received)
        logger.info(f"已成功订阅截图触发信号：{req_event.name}，等待信号触发自动截图")

# 测试代码（可选，可直接运行验证功能）
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout

    # 初始化日志（测试用）
    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Screenshot Test")
    window.resize(400, 300)

    # 创建Screenshot实例
    screenshot_widget = Screenshot(title="测试截图窗口", border_color=Qt.blue, geometry=QRect(200, 200, 200, 150))

    # 创建控制按钮
    show_title_btn = QPushButton("显示标题栏")
    hide_title_btn = QPushButton("隐藏标题栏")
    screenshot_btn = QPushButton("手动获取无标题栏截图并保存")
    trigger_signal_btn = QPushButton("发送测试信号触发自动截图")

    # 绑定信号槽
    show_title_btn.clicked.connect(screenshot_widget.show_title_bar)
    hide_title_btn.clicked.connect(screenshot_widget.hide_title_bar)

    def pixmap_to_numpy_rgb(pixmap: QPixmap) -> np.ndarray:
        """
        简化版：QPixmap 转 RGB 格式 numpy 数组（适用于截图等常规场景）
        :param pixmap: 输入 QPixmap
        :return: (height, width, 3) 形状的 numpy 数组（RGB 通道）
        """
        qimage = pixmap.toImage()
        # 先转换为 RGB888 格式（兼容所有 QPixmap 格式）
        qimage_rgb = qimage.convertToFormat(QImage.Format_RGB888)
        width, height = qimage_rgb.width(), qimage_rgb.height()
        # 提取像素数据并重塑
        ptr = qimage_rgb.bits()
        ptr.setsize(qimage_rgb.byteCount())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 3))
        return arr

    def save_screenshot():
        pixmap = screenshot_widget.get_frameless_screenshot()
        pixmap.save("manual_frameless_screenshot.png")
        print(f"手动截图已保存为：manual_frameless_screenshot.png，尺寸：{pixmap.width()}x{pixmap.height()}")

    # 订阅测试信号，触发自动截图
    screenshot_widget.subscribe_screenshot_trigger(GlobalEvents.REQ_GAMETIME_SCREENSHOT)

    # 定义截图响应回调（验证自动截图结果）
    # def on_screenshot_captured(response_data):
    #     pixmap = response_data["screenshot_pixmap"]
    #     perf_time = response_data["trigger_perf_time"]
    #     # 保存自动截图
    #     auto_save_path = f"auto_screenshot_{perf_time:.6f}.png"
    #     pixmap.save(auto_save_path)
    #     print(f"自动截图已保存为：{auto_save_path}，触发时间戳：{perf_time:.6f}")

    # # 订阅截图响应信号
    # EventBusInstance.subscribe(GlobalEvents.RES_GAMETIME_SCREENSHOT, on_screenshot_captured)

    # 发送测试信号触发自动截图
    def send_trigger_signal():
        print("已发送测试触发信号，等待自动截图...")
        EventBusInstance.publish(GlobalEvents.REQ_GAMETIME_SCREENSHOT)

    # 绑定按钮点击事件
    screenshot_btn.clicked.connect(save_screenshot)
    trigger_signal_btn.clicked.connect(send_trigger_signal)

    # 布局
    layout = QVBoxLayout(window)
    layout.addWidget(show_title_btn)
    layout.addWidget(hide_title_btn)
    layout.addWidget(screenshot_btn)
    layout.addWidget(trigger_signal_btn)

    window.show()
    sys.exit(app.exec_())