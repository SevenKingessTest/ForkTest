import sys
import numpy as np
from PyQt5.QtWidgets import (QWidget, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QApplication, QHeaderView, QSizePolicy)
from PyQt5.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect,
                          pyqtSlot, QPointF)
from PyQt5.QtGui import QFont, QPainter, QPolygonF, QColor, QBrush

# 导入用户指定的事件总线和全局事件枚举
from core.global_event_enums import GlobalEvents
from core.event_bus import EventBusInstance

import logging
logger = logging.getLogger(__name__)



# 独立的指针绘制组件（层级置顶，避免被表格遮挡）
class ArrowWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 指针样式配置（可自定义）
        self.arrow_length = 25  # 指针向内侧延伸长度（尖端长度）
        self.arrow_height = 16  # 指针根部宽度（贴边界的宽端高度）
        self.arrow_color = QColor(30, 30, 30)  # 黑色指针

    # 重写指针绘制方法
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿

        # 计算指针坐标（根部贴紧右边界，宽端在右，尖端在左）
        window_width = self.width() - 1  # 右边界x坐标（微调1像素，避免超出可视区）
        window_height_30 = self.height() * 0.3  # 指针中心y坐标（窗口高度30%）

        # 定义三角形顶点
        point1 = QPointF(window_width, window_height_30 - self.arrow_height // 2)
        point2 = QPointF(window_width, window_height_30 + self.arrow_height // 2)
        point3 = QPointF(window_width - self.arrow_length, window_height_30)

        # 构建三角形
        arrow_polygon = QPolygonF([point1, point2, point3])

        # 设置指针样式
        painter.setBrush(QBrush(self.arrow_color))
        painter.setPen(Qt.NoPen)  # 隐藏轮廓
        painter.drawPolygon(arrow_polygon)
        painter.end()

class ProcessTable(QWidget):
    '''
    整体流程表的执行必须处于RES_GAMETIME_TIMER_START下
    任务流程表的正常执行状态必须处在RES_GAMETIME_TIMER_STAR和RES_TASKTIME_TIMER_START下

    订阅RES_GAMETIME_TIMER_START信号，当收到信号时设置self.game_time_timer_runing为True,并且接收参数【time_closure】为self.game_time_timer_closure
    订阅RES_TASKTIME_TIMER_START信号，当收到信号时设置self.task_time_timer_runing为True,并且接收参数【time_closure】为self.task_time_timer_closure
    订阅RES_TASKTIME_TIMER_PAUSE信号，当收到信号时设置self.task_time_timer_runing为False,触发一次流程表更新方法,并且接收参数【time_closure】为self.task_time_timer_closure
    订阅RES_TASKTIME_TIMER_RESUME信号，当收到信号时设置self.task_time_timer_runing为True,触发一次流程表更新方法，并且接收参数【time_closure】为self.task_time_timer_closure

    订阅RES_GAMETIME_TIMER_CALIBRATE和RES_TASKTIME_TIMER_CALIBRATE，收到信号时更新参数【time_closure】为对应的self.game_time_timer_closure或self.task_time_timer_closure,触发一次流程表更新方法

    订阅REQ_GAMETIME_TIMER_STOP和RES_TASKTIME_TIMER_STOP信号，收到信号时设置self.game_time_timer_runing和self.task_time_timer_runing为False,触发一次流程表更新方法

    订阅信号：
        REQ_BASEPROCESSTABLE_UPDATE：基础流程表内容更新_请求
        REQ_MAPPROCESSTABLE_UPDATE：地图流程表内容更新_请求
        REQ_TASKPROCESSTABLE_UPDATE：任务流程表内容更新_请求
        这三个都会携带一个参数[(字符串时间，内容文字)]

        当REQ_BASEPROCESSTABLE_UPDATE或REQ_MAPPROCESSTABLE_UPDATE被触发时，把对应的参数处理成[(整数分钟，整数秒，内容文字)]存进self.base_process_list或self.map_process_list
        如果self.game_time_timer_runing为True，则触发流程表更新方法

        当触发REQ_TASKPROCESSTABLE_UPDATE时，把对应的参数处理成[(整数分钟，整数秒，内容文字)]存进self.task_process_list
        如果self.game_time_timer_runing和self.task_time_timer_runing都为True，则触发流程表更新方法

    流程表更新方法：
        if self.game_time_timer_runing == False
            展示内容未获取游戏时间
        else:
            if self.task_time_timer_runing == False
                直接合并self.base_process_list和self.map_process_list，并按照时为主值，秒为辅值排序
            else:
                处理self.task_process_list,根据当前获得的游戏时间和任务时间闭包，可以获得当前时间
                每一项的时间按照 当前游戏时间 + 当前任务时间 - 项目时间 处理，然后再与self.base_process_list和self.map_process_list合并，依旧排序
            合并后的数据按照当前的滚动逻辑和颜色逻辑设置
    '''
    def __init__(self, parent=None, geometry: QRect = QRect(100, 600, 300, 400), column_ratio: float = 0.7):
        super().__init__(parent)

        # ===================== 1. 状态标志变量（控制流程开关） =====================
        self.game_time_timer_runing = False  # 游戏时间定时器运行状态
        self.task_time_timer_runing = False  # 任务时间定时器运行状态

        # ===================== 2. 流程数据存储变量（按要求格式） =====================
        self.base_process_list = []  # [(整数分钟, 整数秒, 内容文字), ...]
        self.map_process_list = []   # [(整数分钟, 整数秒, 内容文字), ...]
        self.task_process_list = []  # [(整数分钟, 整数秒, 内容文字), ...]

        # ===================== 3. 时间闭包变量（从事件字典中获取） =====================
        self.game_time_timer_closure = None  # 游戏时间闭包（返回浮点数秒）
        self.task_time_timer_closure = None  # 任务时间闭包（返回浮点数秒）

        # ===================== 4. 原有复用变量（保留旧代码核心） =====================
        self.merge_time_value_list = []
        self.ordered_time_list = []
        self.time_ratio_list = np.array([])
        self.merge_ratio_list = np.array([])
        self.column_ratio = column_ratio
        self.window_title = "流程表（想放在哪就放在哪）"
        self.time_row_dict = {}  # 时间与表格行索引映射

        # 窗口样式
        self.setStyleSheet("background-color: rgba(128, 128, 128, 0.5);")
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # ===================== 5. 组件初始化 =====================
        self.init_table()  # 初始化表格
        self.init_event_subscription()  # 初始化事件订阅

        # 添加独立指针组件
        self.arrow_widget = ArrowWidget(self)
        self.arrow_widget.setGeometry(0, 0, self.width(), self.height())
        self.arrow_widget.raise_()  # 强制置顶

        # 窗口位置和大小
        self.setGeometry(geometry)

        # 初始化线性滚动动画对象（移除虚拟时间依赖）
        self.scroll_animation = QPropertyAnimation(self.table_widget.verticalScrollBar(), b"value")
        self.custom_curve = QEasingCurve()
        self.custom_curve.setCustomType(self.custom_easing)

        # 初始化时默认不显示标题栏
        self.hide_title_bar()

        # 颜色更新定时器（移除虚拟时间更新，仅保留颜色更新）
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(16)  # 60帧/秒，视觉无卡顿
        self.update_timer.timeout.connect(self.update_row_colors)  # 仅更新颜色
        self.update_timer.start()  # 启动定时器

    def init_table(self):
        """初始化表格组件（复用旧代码，优化列宽适配）"""
        # 创建QTableWidget表格
        self.table_widget = QTableWidget()
        self.table_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 基础设置
        self.table_widget.setRowCount(0)
        self.table_widget.setColumnCount(2)

        # 字体参数
        self.table_font = QFont()
        self.table_font.setPointSize(17)
        self.table_widget.setFont(self.table_font)
        self.table_widget.setStyleSheet("")  # 清空全局文字样式，确保动态设置生效

        # 隐藏表头和滚动条
        self.table_widget.horizontalHeader().setVisible(False)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table_widget.setVerticalScrollMode(QTableWidget.ScrollPerPixel)

        # 列宽按比例设置
        self.set_column_width_by_ratio()

        # 布局：表格填满窗口
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.table_widget)
        self.setLayout(layout)

    def init_event_subscription(self):
        """统一订阅所有全局事件（核心方法）"""
        # 1. 时间定时器启动事件
        EventBusInstance.subscribe(GlobalEvents.RES_GAMETIME_TIMER_START, self.on_game_time_timer_start)
        EventBusInstance.subscribe(GlobalEvents.RES_TASKTIME_TIMER_START, self.on_task_time_timer_start)

        # 2. 任务时间暂停/恢复事件
        EventBusInstance.subscribe(GlobalEvents.RES_TASKTIME_TIMER_PAUSE, self.on_task_time_timer_pause)
        EventBusInstance.subscribe(GlobalEvents.RES_TASKTIME_TIMER_RESUME, self.on_task_time_timer_resume)

        # 3. 时间校准事件
        EventBusInstance.subscribe(GlobalEvents.RES_GAMETIME_TIMER_CALIBRATE, self.on_game_time_calibrate)
        EventBusInstance.subscribe(GlobalEvents.RES_TASKTIME_TIMER_CALIBRATE, self.on_task_time_calibrate)

        # 4. 时间定时器停止事件
        EventBusInstance.subscribe(GlobalEvents.RES_GAMETIME_TIMER_STOP, self.on_game_time_timer_stop)
        EventBusInstance.subscribe(GlobalEvents.RES_TASKTIME_TIMER_STOP, self.on_task_time_timer_stop)

        # 5. 流程表数据更新事件
        EventBusInstance.subscribe(GlobalEvents.REQ_BASEPROCESSTABLE_UPDATE, self.on_base_process_update)
        EventBusInstance.subscribe(GlobalEvents.REQ_MAPPROCESSTABLE_UPDATE, self.on_map_process_update)
        EventBusInstance.subscribe(GlobalEvents.REQ_TASKPROCESSTABLE_UPDATE, self.on_task_process_update)

    # ===================== 事件回调方法（闭包从字典获取） =====================
    def on_game_time_timer_start(self, params_dict):
        """响应RES_GAMETIME_TIMER_START"""
        self.game_time_timer_runing = True
        self.game_time_timer_closure = params_dict.get("time_closure")
        self.update_process_table()  # 触发流程表更新

    def on_task_time_timer_start(self, params_dict):
        """响应RES_TASKTIME_TIMER_START"""
        self.task_time_timer_runing = True
        self.task_time_timer_closure = params_dict.get("time_closure")
        self.update_process_table()  # 触发流程表更新

    def on_task_time_timer_pause(self, params_dict):
        """响应RES_TASKTIME_TIMER_PAUSE"""
        self.task_time_timer_runing = False
        self.task_time_timer_closure = params_dict.get("time_closure")
        self.update_process_table()  # 触发流程表更新

    def on_task_time_timer_resume(self, params_dict):
        """响应RES_TASKTIME_TIMER_RESUME"""
        self.task_time_timer_runing = True
        self.task_time_timer_closure = params_dict.get("time_closure")
        self.update_process_table()  # 触发流程表更新

    def on_game_time_calibrate(self, params_dict):
        """响应RES_GAMETIME_TIMER_CALIBRATE"""
        self.game_time_timer_closure = params_dict.get("time_closure")
        self.update_process_table()  # 触发流程表更新

    def on_task_time_calibrate(self, params_dict):
        """响应RES_TASKTIME_TIMER_CALIBRATE"""
        self.task_time_timer_closure = params_dict.get("time_closure")
        self.update_process_table()  # 触发流程表更新

    def on_game_time_timer_stop(self, params_dict=None):
        """响应RES_GAMETIME_TIMER_STOP"""
        self.game_time_timer_runing = False
        self.update_process_table()  # 触发流程表更新

    def on_task_time_timer_stop(self, data_dict=None):
        """响应RES_TASKTIME_TIMER_STOP"""
        self.task_time_timer_runing = False
        self.update_process_table()  # 触发流程表更新

    # ===================== 数据更新回调方法 =====================
    def on_base_process_update(self, data_list):
        """响应REQ_BASEPROCESSTABLE_UPDATE"""
        # 转换数据格式：[(字符串时间, 内容) -> (整数分钟, 整数秒, 内容)]
        self.base_process_list = [self.convert_time_str_to_int(item[0]) + (item[1],) for item in data_list]
        # 若游戏时间定时器运行，触发更新
        if self.game_time_timer_runing:
            self.update_process_table()

    def on_map_process_update(self, data_list):
        """响应REQ_MAPPROCESSTABLE_UPDATE"""
        # 转换数据格式
        self.map_process_list = [self.convert_time_str_to_int(item[0]) + (item[1],) for item in data_list]
        # 若游戏时间定时器运行，触发更新
        if self.game_time_timer_runing:
            self.update_process_table()

    def on_task_process_update(self, data_list):
        """响应REQ_TASKPROCESSTABLE_UPDATE"""
        # 转换数据格式
        self.task_process_list = [self.convert_time_str_to_int(item[0]) + (item[1],) for item in data_list]
        # 若游戏时间和任务时间定时器均运行，触发更新
        if self.game_time_timer_runing and self.task_time_timer_runing:
            self.update_process_table()

    # ===================== 辅助工具方法 =====================
    def convert_time_str_to_int(self, time_str):
        """将字符串时间（如"0:10"）转换为(整数分钟, 整数秒)，异常返回(0,0)"""
        try:
            minute_str, second_str = time_str.split(":")
            minute = int(float(minute_str))
            second = int(float(second_str))
            return (minute, second)
        except (ValueError, AttributeError):
            return (0, 0)

    def convert_int_time_to_total_seconds(self, minute, second):
        """将(整数分钟, 整数秒)转换为总秒数"""
        return minute * 60 + second

    def get_current_real_time(self):
        """获取当前真实游戏时间（浮点数秒），替代虚拟时间"""
        if not self.game_time_timer_closure:
            return 0.0
        try:
            return self.game_time_timer_closure()  # 闭包返回浮点数秒
        except:
            return 0.0

    def get_current_task_time(self):
        """获取当前真实任务时间（浮点数秒）"""
        if not self.task_time_timer_closure:
            return 0.0
        try:
            return self.task_time_timer_closure()  # 闭包返回浮点数秒
        except:
            return 0.0

    # ===================== 核心业务方法：流程表更新 =====================
    def update_process_table(self):
        """流程表更新入口"""
        # 场景1：未获取游戏时间
        if not self.game_time_timer_runing:
            self.load_data([["", "未获取游戏时间"]])
            logger.info("【流程表更新】未获取游戏时间")
            return

        # 场景2：仅游戏时间运行，任务时间未运行
        if not self.task_time_timer_runing:
            # 合并基础流程表和地图流程表
            merge_list = self.base_process_list + self.map_process_list
            # 按分钟为主，秒为辅排序
            merge_list.sort(key=lambda x: (x[0], x[1]))
            # 转换为load_data所需格式：[(时间字符串, 内容), ...]
            display_data = []
            for item in merge_list:
                minute, second, content = item
                time_str = f"{minute}:{second:02d}"
                display_data.append((time_str, content))
            # 加载数据并启动滚动
            self.load_data(display_data)
            self.start_scroll(curr_time=self.get_current_real_time())
            logger.info("【流程表更新】仅游戏时间运行，任务时间未运行")
            return

        # 场景3：游戏时间和任务时间均运行
        current_game_time = self.get_current_real_time()
        current_task_time = self.get_current_task_time()

        # 处理任务流程表：每项时间 = 当前游戏时间 + 当前任务时间 - 项目总秒数
        processed_task_list = []
        for item in self.task_process_list:
            minute, second, content = item
            item_total_seconds = self.convert_int_time_to_total_seconds(minute, second)
            # 计算处理后的总秒数
            processed_total_seconds = current_game_time + current_task_time - item_total_seconds
            # 转换为分钟和秒（用于排序）
            processed_minute = int(processed_total_seconds // 60)
            processed_second = int(processed_total_seconds % 60)
            # 转换为显示用时间字符串
            processed_time_str = f"{processed_minute}:{processed_second:02d}"
            processed_task_list.append((processed_minute, processed_second, processed_time_str, content))

        # 合并任务流程表（处理后）、基础流程表、地图流程表
        base_map_merge = self.base_process_list + self.map_process_list
        # 转换base_map_merge格式，统一为(分钟, 秒, 时间字符串, 内容)
        base_map_display = []
        for item in base_map_merge:
            minute, second, content = item
            time_str = f"{minute}:{second:02d}"
            base_map_display.append((minute, second, time_str, content))
        # 合并所有数据
        total_merge_list = base_map_display + processed_task_list
        # 按分钟为主，秒为辅排序
        total_merge_list.sort(key=lambda x: (x[0], x[1]))
        # 转换为load_data所需格式
        final_display_data = [(item[2], item[3]) for item in total_merge_list]
        # 加载数据并启动滚动
        self.load_data(final_display_data)
        self.start_scroll(curr_time=current_game_time)
        logger.info("【流程表更新】游戏时间和任务时间均运行")

    # ===================== 原有复用方法（仅移除虚拟时间依赖） =====================
    def time_ruler(self, time_str: str) -> float:
        """时间字符串转数值（分钟+秒）"""
        time_parts = time_str.split(":")
        if len(time_parts) != 2:
            return 0.0
        try:
            return float(time_parts[0]) * 60 + float(time_parts[1])
        except:
            return 0.0

    def load_data(self, data):
        """
        data格式是先时间再内容
        复用旧代码，优化抗闪烁
        """
        self.table_widget.setUpdatesEnabled(False)
        self.table_widget.blockSignals(True)

        self.table_widget.setRowCount(0)
        self.merge_time_value_list = []
        self.time_row_dict = {}
        self.ordered_time_list = []

        if not isinstance(data, list) or len(data) == 0:
            self.table_widget.blockSignals(False)
            self.table_widget.setUpdatesEnabled(True)
            return

        total_rows = len(data) + 2
        self.table_widget.setRowCount(total_rows)
        col_count = self.table_widget.columnCount()

        # 顶部/底部空白行
        top_blank_row_idx = 0
        bottom_blank_row_idx = total_rows - 1
        self.table_widget.setSpan(top_blank_row_idx, 0, 1, col_count)
        self.table_widget.setSpan(bottom_blank_row_idx, 0, 1, col_count)

        for blank_row in [top_blank_row_idx, bottom_blank_row_idx]:
            blank_item = QTableWidgetItem("\n" * 30)
            blank_item.setFlags(Qt.ItemIsEnabled)
            self.table_widget.setItem(blank_row, 0, blank_item)

        # 填充数据
        for data_idx, row_data in enumerate(data):
            table_row_idx = data_idx + 1
            time_str, content_str = str(row_data[0]), str(row_data[1])

            content_item = QTableWidgetItem(content_str)
            content_item.setTextAlignment(Qt.AlignCenter)
            content_item.setFlags(Qt.ItemIsEnabled)
            time_item = QTableWidgetItem(time_str)
            time_item.setTextAlignment(Qt.AlignCenter)
            time_item.setFlags(Qt.ItemIsEnabled)

            self.table_widget.setItem(table_row_idx, 0, content_item)
            self.table_widget.setItem(table_row_idx, 1, time_item)

            if time_str not in self.time_row_dict:
                self.time_row_dict[time_str] = []
                self.ordered_time_list.append(time_str)
            self.time_row_dict[time_str].append(table_row_idx)

        # 合并相同时间单元格
        for time_str, row_idx_list in self.time_row_dict.items():
            if len(row_idx_list) == 1:
                continue
            start_row = row_idx_list[0]
            merge_row_count = len(row_idx_list)
            self.table_widget.setSpan(start_row, 1, merge_row_count, 1)

        # 计算合并时间value
        for idx, time_str in enumerate(self.ordered_time_list):
            row_idx_list = self.time_row_dict[time_str]
            start_row = row_idx_list[0]
            merge_row_count = len(row_idx_list)

            top_value = 0
            for r in range(start_row):
                row_h = self.table_widget.rowHeight(r) if self.table_widget.rowHeight(r) > 0 else 0
                top_value += row_h

            bottom_value = top_value
            for r in range(start_row, start_row + merge_row_count):
                row_h = self.table_widget.rowHeight(r) if self.table_widget.rowHeight(r) > 0 else 0
                bottom_value += row_h

            if idx == 0:
                self.merge_time_value_list.append(top_value)
                self.merge_time_value_list.append(bottom_value)
            else:
                self.merge_time_value_list.append(bottom_value)

        # 时间格式化
        self.ordered_time_list = [self.time_ruler(time_str) for time_str in self.ordered_time_list]
        if self.ordered_time_list:
            self.ordered_time_list += [self.ordered_time_list[-1] + 30]
        else:
            self.ordered_time_list = []

        self.table_widget.blockSignals(False)
        self.table_widget.setUpdatesEnabled(True)
        self.show()

    def start_scroll(self, curr_time: float = 0.0, time_speed: float = 1.4):
        """
        滚动逻辑：移除虚拟时间依赖，使用真实时间
        """
        time_ratio_list = []
        merge_ratio_list = []

        if len(self.ordered_time_list) == 0 or len(self.merge_time_value_list) == 0:
            return

        if curr_time <= self.ordered_time_list[0]:
            start_scroll = self.merge_time_value_list[0] - self.height() * 0.3
            time_ratio_list = np.array(self.ordered_time_list) - curr_time
            time_ratio_list = time_ratio_list / time_ratio_list[-1] if time_ratio_list[-1] != 0 else np.array([1.0])
            merge_ratio_list = np.array(self.merge_time_value_list) - self.merge_time_value_list[0]
            merge_ratio_list = merge_ratio_list / merge_ratio_list[-1] if merge_ratio_list[-1] != 0 else np.array([1.0])
        elif curr_time > self.ordered_time_list[-1]:
            start_scroll = self.merge_time_value_list[-1] - self.height() * 0.3
            time_ratio_list = np.array([1.0])
            merge_ratio_list = np.array([1.0])
        else:
            for idx, time in enumerate(self.ordered_time_list):
                if time > curr_time:
                    break
            prior_time = self.ordered_time_list[idx - 1]
            next_time = self.ordered_time_list[idx]
            progress = (curr_time - prior_time) / (next_time - prior_time)
            start_scroll = self.merge_time_value_list[idx - 1] + (self.merge_time_value_list[idx] - self.merge_time_value_list[idx - 1]) * progress - self.height() * 0.3
            time_ratio_list = np.array(self.ordered_time_list[idx:]) - curr_time
            time_ratio_list = time_ratio_list / time_ratio_list[-1] if time_ratio_list[-1] != 0 else np.array([1.0])
            merge_ratio_list = np.array(self.merge_time_value_list[idx:]) - start_scroll - self.height() * 0.3
            merge_ratio_list = merge_ratio_list / merge_ratio_list[-1] if merge_ratio_list[-1] != 0 else np.array([1.0])

        self.time_ratio_list = np.insert(time_ratio_list, 0, 0.0)
        self.merge_ratio_list = np.insert(merge_ratio_list, 0, 0.0)

        end_scroll = self.merge_time_value_list[-1] - self.height() * 0.3
        # 用真实时间差计算滚动时长
        time_diff = (self.ordered_time_list[-1] - curr_time) if self.ordered_time_list else 10
        scroll_time = max(100, int(time_diff * 1000 // time_speed))

        self.scroll_animation.stop()
        self.scroll_animation.setStartValue(start_scroll)
        self.scroll_animation.setEndValue(end_scroll)
        self.scroll_animation.setDuration(scroll_time)
        self.scroll_animation.setEasingCurve(self.custom_curve)
        self.scroll_animation.start()

    def update_row_colors(self):
        """周期性更新表格行颜色：使用真实时间替代虚拟时间"""
        if not hasattr(self, 'time_row_dict') or len(self.time_row_dict) == 0:
            return
        if len(self.ordered_time_list) == 0:
            return
        if not self.game_time_timer_runing:
            return

        # 颜色渐变临界值
        RED_THRESHOLD = 10
        YELLOW_THRESHOLD = 30
        EXPIRE_FADE_TIME = 10
        MAX_BRIGHTNESS = 180
        BLACK_TEXT_COLOR = QColor(0, 0, 0)

        # 使用真实时间计算时间差
        current_real_time = self.get_current_real_time()

        # 遍历所有时间对应的表格行
        for time_str, row_idx_list in self.time_row_dict.items():
            row_time = self.time_ruler(time_str)
            time_diff = current_real_time - row_time
            abs_time_diff = abs(time_diff)
            row_color = QColor(0, MAX_BRIGHTNESS, 0)

            # 已过期：红色渐变
            if time_diff > 0:
                fade_progress = min(time_diff / EXPIRE_FADE_TIME, 1.0)
                alpha = int(MAX_BRIGHTNESS * (1 - fade_progress))
                row_color = QColor(MAX_BRIGHTNESS, 0, 0, alpha)
            # 未过期：绿→黄→红渐变
            else:
                r, g, b, alpha = 0, MAX_BRIGHTNESS, 0, 150
                if abs_time_diff >= YELLOW_THRESHOLD:
                    alpha = 50
                    pass
                elif abs_time_diff <= RED_THRESHOLD:
                    progress = 1 - (abs_time_diff / RED_THRESHOLD)
                    r = MAX_BRIGHTNESS
                    g = int(MAX_BRIGHTNESS * (1 - progress))
                else:
                    yellow_progress = (YELLOW_THRESHOLD - abs_time_diff) / (YELLOW_THRESHOLD - RED_THRESHOLD)
                    r = int(MAX_BRIGHTNESS * yellow_progress)
                row_color = QColor(r, g, b, alpha)

            # 更新单元格样式
            for row_idx in row_idx_list:
                for col in range(self.table_widget.columnCount()):
                    item = self.table_widget.item(row_idx, col)
                    if item is not None:
                        item.setBackground(row_color)
                        item.setForeground(BLACK_TEXT_COLOR)

    def custom_easing(self, time: float) -> float:
        if len(self.time_ratio_list) == 0 or len(self.merge_ratio_list) == 0:
            return 0.0
        return np.interp(time, self.time_ratio_list, self.merge_ratio_list)

    def set_column_width_by_ratio(self):
        """按比例设置列宽"""
        table_width = self.table_widget.viewport().width()
        if table_width <= 0:
            return
        left_width = int(table_width * self.column_ratio)
        right_width = table_width - left_width
        left_width = max(10, left_width)
        right_width = max(10, right_width)
        self.table_widget.setColumnWidth(0, left_width)
        self.table_widget.setColumnWidth(1, right_width)

    def resizeEvent(self, event):
        """窗口缩放时同步更新"""
        super().resizeEvent(event)
        QTimer.singleShot(10, self.set_column_width_by_ratio)
        if hasattr(self, 'arrow_widget'):
            self.arrow_widget.setGeometry(0, 0, self.width(), self.height())
            self.arrow_widget.update()
        event.accept()

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
        self.set_column_width_by_ratio()
        if hasattr(self, 'arrow_widget'):
            self.arrow_widget.raise_()
            self.arrow_widget.update()
        self.show()

    @pyqtSlot()
    def hide_title_bar(self):
        old_geometry = self.geometry()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowTransparentForInput
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setGeometry(old_geometry)
        self.set_column_width_by_ratio()
        if hasattr(self, 'arrow_widget'):
            self.arrow_widget.raise_()
            self.arrow_widget.update()
        self.show()

    def closeEvent(self, event):
        """窗口关闭时停止定时器"""
        self.update_timer.stop()
        super().closeEvent(event)

# 测试代码

if __name__ == "__main__":

    import sys
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QPushButton,
        QLineEdit, QLabel, QGridLayout, QTextEdit, QVBoxLayout
    )
    from PyQt5.QtCore import Qt, QTimer
    class TestProcessTableWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("流程表信号测试工具（动态时间）")
            self.setGeometry(100, 100, 800, 700)

            # ===== 新增：动态时间相关变量 =====
            self.dynamic_game_time = 0.0  # 游戏动态时间当前值
            self.dynamic_task_time = 60.0 # 任务动态时间当前值
            self.game_time_step = 0.016   # 游戏时间递增步长（16ms递增0.016秒，每秒+1秒）
            self.task_time_step = 0.016   # 任务时间递增步长
            self.time_update_timer = QTimer(self)  # 时间更新定时器
            self.time_update_timer.setInterval(16) # 和流程表更新频率一致
            self.time_update_timer.timeout.connect(self.update_dynamic_time)
            self.time_update_timer.start() # 启动动态时间更新

            # 1. 实例化流程表（业务窗口）
            try:
                self.process_table = ProcessTable()
                self.process_table.show()
            except:
                self.process_table = None
                print("请先导入ProcessTable类再运行")

            # 2. 创建中心部件和布局
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            grid_layout = QGridLayout()

            # ===== 第一部分：自定义动态时间配置（初始值 + 递增步长） =====
            # 游戏时间配置
            self.game_time_init_input = QLineEdit(self)
            self.game_time_init_input.setPlaceholderText("游戏时间初始值（如：0.0）")
            self.game_time_init_input.setText("0.0")
            self.game_time_step_input = QLineEdit(self)
            self.game_time_step_input.setPlaceholderText("游戏时间步长（如：0.016）")
            self.game_time_step_input.setText("0.016")
            # 任务时间配置
            self.task_time_init_input = QLineEdit(self)
            self.task_time_init_input.setPlaceholderText("任务时间初始值（如：60.0）")
            self.task_time_init_input.setText("60.0")
            self.task_time_step_input = QLineEdit(self)
            self.task_time_step_input.setPlaceholderText("任务时间步长（如：0.016）")
            self.task_time_step_input.setText("0.016")
            # 重置时间按钮
            self.btn_reset_time = QPushButton("重置动态时间", self)

            # 添加到网格布局
            grid_layout.addWidget(QLabel("游戏时间初始值："), 0, 0)
            grid_layout.addWidget(self.game_time_init_input, 0, 1)
            grid_layout.addWidget(QLabel("游戏时间递增步长："), 0, 2)
            grid_layout.addWidget(self.game_time_step_input, 0, 3)

            grid_layout.addWidget(QLabel("任务时间初始值："), 1, 0)
            grid_layout.addWidget(self.task_time_init_input, 1, 1)
            grid_layout.addWidget(QLabel("任务时间递增步长："), 1, 2)
            grid_layout.addWidget(self.task_time_step_input, 1, 3)

            grid_layout.addWidget(self.btn_reset_time, 2, 0, 1, 4) # 跨4列

            # ===== 第二部分：流程表数据输入（自定义） =====
            # 基础流程表数据
            self.base_data_input = QTextEdit(self)
            self.base_data_input.setPlaceholderText("格式：时间,内容;时间,内容（如：0:10,基础初始化;0:20,加载资源）")
            self.base_data_input.setText("0:10,基础流程-初始化;0:20,基础流程-加载资源")
            # 地图流程表数据
            self.map_data_input = QTextEdit(self)
            self.map_data_input.setPlaceholderText("格式同上（如：0:15,地图1;0:25,地图2）")
            self.map_data_input.setText("0:15,地图流程-进入地图1;0:25,地图流程-进入地图2")
            # 任务流程表数据
            self.task_data_input = QTextEdit(self)
            self.task_data_input.setPlaceholderText("格式同上（如：0:05,收集道具;0:10,击败BOSS）")
            self.task_data_input.setText("0:05,任务流程-收集道具;0:10,任务流程-击败BOSS")

            # 添加到网格布局
            grid_layout.addWidget(QLabel("基础流程表数据："), 3, 0)
            grid_layout.addWidget(self.base_data_input, 3, 1, 1, 3)
            grid_layout.addWidget(QLabel("地图流程表数据："), 4, 0)
            grid_layout.addWidget(self.map_data_input, 4, 1, 1, 3)
            grid_layout.addWidget(QLabel("任务流程表数据："), 5, 0)
            grid_layout.addWidget(self.task_data_input, 5, 1, 1, 3)

            # ===== 第三部分：功能按钮（发布各种信号） =====
            # 1. 启动信号按钮
            self.btn_start_game_time = QPushButton("发布-游戏时间定时器启动", self)
            self.btn_start_task_time = QPushButton("发布-任务时间定时器启动", self)
            # 2. 暂停/恢复信号按钮
            self.btn_pause_task_time = QPushButton("发布-任务时间暂停", self)
            self.btn_resume_task_time = QPushButton("发布-任务时间恢复", self)
            # 3. 校准信号按钮
            self.btn_calibrate_game_time = QPushButton("发布-游戏时间校准", self)
            self.btn_calibrate_task_time = QPushButton("发布-任务时间校准", self)
            # 4. 停止信号按钮
            self.btn_stop_game_time = QPushButton("发布-游戏时间定时器停止", self)
            self.btn_stop_task_time = QPushButton("发布-任务时间定时器停止", self)
            # 5. 流程表更新信号按钮
            self.btn_update_base = QPushButton("更新-基础流程表", self)
            self.btn_update_map = QPushButton("更新-地图流程表", self)
            self.btn_update_task = QPushButton("更新-任务流程表", self)
            # 6. 启动滚动按钮
            self.btn_start_scroll = QPushButton("启动流程表滚动", self)

            # 添加按钮到网格布局
            btn_row = 6
            grid_layout.addWidget(self.btn_start_game_time, btn_row, 0)
            grid_layout.addWidget(self.btn_start_task_time, btn_row, 1)
            grid_layout.addWidget(self.btn_pause_task_time, btn_row, 2)
            grid_layout.addWidget(self.btn_resume_task_time, btn_row, 3)
            btn_row += 1
            grid_layout.addWidget(self.btn_calibrate_game_time, btn_row, 0)
            grid_layout.addWidget(self.btn_calibrate_task_time, btn_row, 1)
            grid_layout.addWidget(self.btn_stop_game_time, btn_row, 2)
            grid_layout.addWidget(self.btn_stop_task_time, btn_row, 3)
            btn_row += 1
            grid_layout.addWidget(self.btn_update_base, btn_row, 0)
            grid_layout.addWidget(self.btn_update_map, btn_row, 1)
            grid_layout.addWidget(self.btn_update_task, btn_row, 2)
            grid_layout.addWidget(self.btn_start_scroll, btn_row, 3)

            # ===== 绑定按钮点击事件 =====
            self.btn_reset_time.clicked.connect(self.reset_dynamic_time)
            self.btn_start_game_time.clicked.connect(self.publish_game_time_start)
            self.btn_start_task_time.clicked.connect(self.publish_task_time_start)
            self.btn_pause_task_time.clicked.connect(self.publish_task_time_pause)
            self.btn_resume_task_time.clicked.connect(self.publish_task_time_resume)
            self.btn_calibrate_game_time.clicked.connect(self.publish_game_time_calibrate)
            self.btn_calibrate_task_time.clicked.connect(self.publish_task_time_calibrate)
            self.btn_stop_game_time.clicked.connect(self.publish_game_time_stop)
            self.btn_stop_task_time.clicked.connect(self.publish_task_time_stop)
            self.btn_update_base.clicked.connect(self.publish_update_base)
            self.btn_update_map.clicked.connect(self.publish_update_map)
            self.btn_update_task.clicked.connect(self.publish_update_task)
            self.btn_start_scroll.clicked.connect(self.start_process_table_scroll)

            # 添加网格布局到主布局
            main_layout.addLayout(grid_layout)

            # 初始化动态时间
            self.reset_dynamic_time()

        # ===== 新增：动态时间更新逻辑 =====
        def update_dynamic_time(self):
            """定时器驱动，动态更新游戏时间和任务时间"""
            # 游戏时间持续递增（不受任务暂停影响，模拟真实时间流逝）
            self.dynamic_game_time += self.game_time_step
            # 任务时间仅在非暂停状态下递增（可通过信号控制）
            # 这里通过流程表的状态判断是否递增（如果流程表已实例化）
            if self.process_table and hasattr(self.process_table, 'task_time_timer_runing'):
                if self.process_table.task_time_timer_runing:
                    self.dynamic_task_time += self.task_time_step
            else:
                # 未实例化流程表时，默认递增
                self.dynamic_task_time += self.task_time_step

        def reset_dynamic_time(self):
            """重置动态时间为输入框的初始值"""
            try:
                self.dynamic_game_time = float(self.game_time_init_input.text().strip())
                self.game_time_step = float(self.game_time_step_input.text().strip())
            except:
                self.dynamic_game_time = 0.0
                self.game_time_step = 0.016

            try:
                self.dynamic_task_time = float(self.task_time_init_input.text().strip())
                self.task_time_step = float(self.task_time_step_input.text().strip())
            except:
                self.dynamic_task_time = 60.0
                self.task_time_step = 0.016

        # ===== 修改：闭包返回动态时间（不再返回定值） =====
        def get_game_time_closure(self):
            """获取自定义游戏时间闭包（返回动态递增时间）"""
            def closure():
                # 每次调用都返回当前的动态游戏时间
                return self.dynamic_game_time
            return closure

        def get_task_time_closure(self):
            """获取自定义任务时间闭包（返回动态递增时间）"""
            def closure():
                # 每次调用都返回当前的动态任务时间
                return self.dynamic_task_time
            return closure

        def parse_data_input(self, text):
            """解析文本框数据为 [(时间, 内容)] 格式"""
            data_list = []
            items = text.strip().split(";")
            for item in items:
                if "," not in item:
                    continue
                time_str, content = item.split(",", 1)
                data_list.append((time_str.strip(), content.strip()))
            return data_list

        # ===== 信号发布逻辑（无修改，复用原有逻辑） =====
        def publish_game_time_start(self):
            """发布游戏时间定时器启动信号"""
            params = {"time_closure": self.get_game_time_closure()}
            EventBusInstance.publish(GlobalEvents.RES_GAMETIME_TIMER_START, params)

        def publish_task_time_start(self):
            """发布任务时间定时器启动信号"""
            params = {"time_closure": self.get_task_time_closure()}
            EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_START, params)

        def publish_task_time_pause(self):
            """发布任务时间暂停信号"""
            params = {"time_closure": self.get_task_time_closure()}
            EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_PAUSE, params)

        def publish_task_time_resume(self):
            """发布任务时间恢复信号"""
            params = {"time_closure": self.get_task_time_closure()}
            EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_RESUME, params)

        def publish_game_time_calibrate(self):
            """发布游戏时间校准信号"""
            params = {"time_closure": self.get_game_time_closure()}
            EventBusInstance.publish(GlobalEvents.RES_GAMETIME_TIMER_CALIBRATE, params)

        def publish_task_time_calibrate(self):
            """发布任务时间校准信号"""
            params = {"time_closure": self.get_task_time_closure()}
            EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_CALIBRATE, params)

        def publish_game_time_stop(self):
            """发布游戏时间定时器停止信号"""
            EventBusInstance.publish(GlobalEvents.REQ_GAMETIME_TIMER_STOP)

        def publish_task_time_stop(self):
            """发布任务时间定时器停止信号"""
            EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_STOP)

        def publish_update_base(self):
            """发布基础流程表更新信号"""
            data = self.parse_data_input(self.base_data_input.toPlainText())
            EventBusInstance.publish(GlobalEvents.REQ_BASEPROCESSTABLE_UPDATE, data)

        def publish_update_map(self):
            """发布地图流程表更新信号"""
            data = self.parse_data_input(self.map_data_input.toPlainText())
            EventBusInstance.publish(GlobalEvents.REQ_MAPPROCESSTABLE_UPDATE, data)

        def publish_update_task(self):
            """发布任务流程表更新信号"""
            data = self.parse_data_input(self.task_data_input.toPlainText())
            EventBusInstance.publish(GlobalEvents.REQ_TASKPROCESSTABLE_UPDATE, data)

        def start_process_table_scroll(self):
            """启动流程表滚动"""
            if self.process_table:
                curr_time = self.get_game_time_closure()()
                self.process_table.start_scroll(curr_time=curr_time)


    app = QApplication(sys.argv)
    # 创建测试窗口
    test_window = TestProcessTableWindow()
    test_window.show()
    sys.exit(app.exec_())