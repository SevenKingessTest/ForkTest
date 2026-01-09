# 导入所需模块
import re
import time
import logging
import numpy as np
from PyQt5.QtCore import QObject, QTimer, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage
import easyocr

# 导入事件总线单例和全局事件枚举
from core.global_event_enums import GlobalEvents
from core.event_bus import EventBusInstance

# 配置日志
logger = logging.getLogger(__name__)

class TasktimeCountdownTimer(QObject):
    """
    任务倒计时计时器
    独立Qt组件运行，支持自定义时间流速（默认1.4倍），内置状态管理与自动校准功能

    状态说明：
        State = 0：关闭状态
        State = 1：运行状态
        State = 2：暂停状态

    核心功能：
    1.  订阅EventBus REQ开头信号，响应开启、状态查询、时间闭包获取请求
    2.  开启时采用QTimer非阻塞轮询校准，直到首次检测到时间并校准，切换为运行状态
    3.  运行状态下周期性自动校准，根据识别结果（时间/暂停）执行对应状态切换
    4.  支持暂停/恢复/停止操作，同步发布对应RES开头信号并携带计时闭包
    5.  计时归零时自动切换为关闭状态，发布停止响应信号
    6.  利用screenshot_perf_time（截图生成时间）修正信号传输损耗，提升校准精度
    7.  支持多启动请求过滤，避免重复校准流程
    """
    # 状态常量（0=关闭、1=运行、2=暂停）
    STATE_STOPPED = 0
    STATE_RUNNING = 1
    STATE_PAUSED = 2

    def __init__(self, time_speed=1.4, calibration_interval=1000, first_calib_poll_interval=2000):
        """
        初始化任务倒计时计时器

        Parameters:
            time_speed (float): 时间流速，默认1.4倍正常时间流速
            calibration_interval (int): 常规自动校准间隔时间，单位毫秒，默认1000ms
            first_calib_poll_interval (int): 首次校准轮询间隔（非阻塞），单位毫秒，默认500ms
        """
        super().__init__()

        # 核心状态变量
        self.State = self.STATE_STOPPED  # 初始状态：关闭
        self._is_first_calibrating = False  # 【新增】首次校准中标志位，防止多请求重复触发

        # 基础配置属性
        self._time_speed = time_speed  # 时间流速
        self._calibration_interval = calibration_interval  # 常规校准间隔
        self._first_calib_poll_interval = first_calib_poll_interval  # 首次校准轮询间隔
        self._calibration_threshold = 1.0  # 校准误差阈值（秒）

        # 计时核心属性
        self._base_perf_time = 0.0  # 高精度基准时间
        self._calibration_offset = 0.0  # 校准偏移量
        self._paused_fixed_seconds = 0.0  # 暂停时的固定剩余时间（闭包返回用）
        self._current_recognized_seconds = None  # 最新识别到的时间秒数

        # 组件初始化
        self._calibration_timer = None  # 常规校准定时器
        self._first_calibration_timer = None  # 【新增】首次校准专用定时器（非阻塞轮询）
        self.reader = None  # EasyOCR识别器
        self._init_calibration_timer()
        self._init_first_calibration_timer()  # 【新增】初始化首次校准定时器
        self._init_easyocr()
        self._subscribe_event_bus_signals()

        logger.info(
            "任务倒计时计时器初始化完成 | 时间流速：%.1fx | 常规校准间隔：%dms | 首次校准轮询间隔：%dms",
            self._time_speed, self._calibration_interval, self._first_calib_poll_interval
        )

    def _init_calibration_timer(self):
        """
        初始化常规校准定时器，绑定超时槽函数
        """
        self._calibration_timer = QTimer(self)
        self._calibration_timer.setInterval(self._calibration_interval)
        self._calibration_timer.timeout.connect(self._on_calibration_timeout)
        logger.debug("常规校准定时器初始化完成 | 超时间隔：%dms", self._calibration_interval)

    def _init_first_calibration_timer(self):
        """
        【新增】初始化首次校准专用定时器（非阻塞轮询），绑定单次校准槽函数
        """
        self._first_calibration_timer = QTimer(self)
        self._first_calibration_timer.setInterval(self._first_calib_poll_interval)
        self._first_calibration_timer.timeout.connect(self._perform_single_first_calibration)
        self._first_calibration_timer.setSingleShot(False)  # 非单次触发，循环轮询
        logger.debug("首次校准定时器初始化完成 | 轮询间隔：%dms", self._first_calib_poll_interval)

    def _init_easyocr(self):
        """
        初始化EasyOCR识别器
        """
        try:
            self.reader = easyocr.Reader(['ch_sim'], gpu=True)
            logger.info("EasyOCR识别器初始化成功（使用GPU加速）")
        except Exception as e:
            self.reader = easyocr.Reader(['ch_sim'], gpu=False)
            logger.warning(f"EasyOCR GPU初始化失败，降级为CPU模式 | 异常信息：{str(e)}")

    def _subscribe_event_bus_signals(self):
        """
        统一订阅EventBus所有REQ开头的任务时间计时器请求信号
        """
        # 订阅开启请求信号
        EventBusInstance.subscribe(
            GlobalEvents.REQ_TASKTIME_TIMER_START,
            self._on_req_timer_start
        )
        # 订阅状态查询请求信号
        EventBusInstance.subscribe(
            GlobalEvents.REQ_TASKTIME_TIMER_STATUS,
            self._on_req_timer_status
        )
        # 订阅时间闭包获取请求信号
        EventBusInstance.subscribe(
            GlobalEvents.REQ_TASKTIME_TIMER_GETTIME,
            self._on_req_timer_gettime
        )

        logger.info(
            "已订阅EventBus请求信号：%s、%s、%s",
            GlobalEvents.REQ_TASKTIME_TIMER_START,
            GlobalEvents.REQ_TASKTIME_TIMER_STATUS,
            GlobalEvents.REQ_TASKTIME_TIMER_GETTIME
        )

    @pyqtSlot()
    def _on_req_timer_start(self, *args, **kwargs):
        """
        【修改】响应REQ_TASKTIME_TIMER_START信号：开启计时器（支持多请求过滤）
        双层条件判断：非运行状态 + 非首次校准中，避免重复触发
        """
        # 第一层：过滤运行状态请求；第二层：过滤校准中请求（处理多启动信号）
        if self.State != self.STATE_RUNNING and not self._is_first_calibrating:
            logger.info("接收到计时器开启请求，启动首次校准非阻塞轮询")
            # 标记校准中状态，防止重复请求
            self._is_first_calibrating = True
            # 启动首次校准定时器（非阻塞轮询）
            self._first_calibration_timer.start()
        elif self.State == self.STATE_RUNNING:
            logger.warning("计时器已处于运行状态（State=1），忽略开启请求")
        elif self._is_first_calibrating:
            logger.warning("正在执行首次校准流程，忽略重复开启请求")

    @pyqtSlot()
    def _on_req_timer_status(self, *args, **kwargs):
        """
        响应REQ_TASKTIME_TIMER_STATUS信号：返回当前状态State
        """
        logger.debug("接收到状态查询请求，当前State：%d，是否首次校准中：%s", self.State, self._is_first_calibrating)
        return self.State

    @pyqtSlot()
    def _on_req_timer_gettime(self, *args, **kwargs):
        """
        响应REQ_TASKTIME_TIMER_GETTIME信号：返回当前计时闭包
        """
        result = {
            "time_closure": self._generate_time_closure(),
        }
        EventBusInstance.shared_data[GlobalEvents.RES_TASKTIME_TIMER_GETTIME] = result
        logger.debug("接收到时间闭包获取请求，已生成对应闭包")
        return result

    def _perform_single_first_calibration(self):
        """
        【新增】单次首次校准尝试（非阻塞）：作为首次校准定时器的槽函数，每次触发仅执行一次校准
        校准成功：停止轮询、切换状态、启动常规校准；校准失败：不处理，定时器继续轮询
        """
        # 阻塞获取截图及截图生成时的精确时间（单次尝试，无循环）

        EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_SCREENSHOT)
        screenshot_pixmap, screenshot_perf_time = EventBusInstance.shared_data[GlobalEvents.RES_TASKTIME_SCREENSHOT]

        # OCR识别
        recognize_result = self._ocr_recognize(screenshot_pixmap)
        # 判断是否为有效时间
        if recognize_result is not None and ":" in recognize_result:
            # 解析截图中的时间为秒数
            recognized_screenshot_seconds = self._parse_time_str_to_seconds(recognize_result)
            if recognized_screenshot_seconds is not None and recognized_screenshot_seconds > 0:
                # 核心校准逻辑：修正信号传输损耗，计算真实当前时间
                current_perf_time = time.perf_counter()
                perf_time_diff = current_perf_time - screenshot_perf_time
                timer_time_diff = perf_time_diff * self._time_speed
                real_current_time = recognized_screenshot_seconds - timer_time_diff

                # 初始化计时参数，完成首次校准
                self._current_recognized_seconds = recognized_screenshot_seconds
                self._base_perf_time = current_perf_time
                self._calibration_offset = real_current_time

                # 校准成功：停止首次校准定时器
                self._first_calibration_timer.stop()
                # 重置校准中标志位
                self._is_first_calibrating = False
                # 切换为运行状态
                self.State = self.STATE_RUNNING
                # 启动常规校准定时器
                self._calibration_timer.start()
                # 生成计时闭包
                time_closure = self._generate_time_closure()
                # 发布开启成功响应信号
                response_data = {
                    "state": self.State,
                    "time_closure": time_closure,
                    "time_speed": self._time_speed
                }
                EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_START, response_data)

                logger.info(
                    f"首次校准成功 | 截图时间：{recognize_result}（{recognized_screenshot_seconds}s）| "
                    f"传输耗时：{perf_time_diff:.3f}s | 真实当前时间：{real_current_time:.3f}s | "
                    f"已切换为运行状态（State=1），启动常规校准"
                )
                return

        # 校准失败：日志提示，定时器继续下一轮轮询
        logger.debug("未识别到有效时间，单次首次校准失败，等待下一轮轮询")

    def _on_calibration_timeout(self):
        """
        常规校准定时器超时槽函数：仅运行状态下和暂停状态下执行常规校准
        """
        if self.State == self.STATE_RUNNING or self.State == self.STATE_PAUSED:
            self._perform_regular_calibration()

    def _perform_regular_calibration(self):
        """
        常规自动校准：利用screenshot_perf_time修正传输损耗，处理识别结果并执行状态切换
        """
        # 获取截图及截图生成时的精确时间

        EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_SCREENSHOT)
        screenshot_pixmap, screenshot_perf_time = EventBusInstance.shared_data[GlobalEvents.RES_TASKTIME_SCREENSHOT]

        # OCR识别
        recognize_result = self._ocr_recognize(screenshot_pixmap)

        # 场景1：识别到时间
        if recognize_result is not None and ":" in recognize_result:
            recognized_screenshot_seconds = self._parse_time_str_to_seconds(recognize_result)
            if recognized_screenshot_seconds is None or recognized_screenshot_seconds < 0:
                logger.warning("识别到无效时间格式，常规校准失败")
                return

            # 核心校准逻辑：修正信号传输损耗，计算真实当前时间
            current_perf_time = time.perf_counter()
            perf_time_diff = current_perf_time - screenshot_perf_time
            timer_time_diff = perf_time_diff * self._time_speed
            real_current_time = recognized_screenshot_seconds - timer_time_diff

            self._current_recognized_seconds = recognized_screenshot_seconds
            # 子场景a：当前为运行状态
            if self.State == self.STATE_RUNNING:
                self._calibrate_running_state(recognized_screenshot_seconds, screenshot_perf_time, real_current_time)
            # 子场景b：当前为暂停状态
            elif self.State == self.STATE_PAUSED:
                self._calibrate_paused_state(recognized_screenshot_seconds, screenshot_perf_time, real_current_time)

        # 场景2：识别到暂停
        elif recognize_result == "暂停":
            # 子场景a：当前为运行状态
            if self.State == self.STATE_RUNNING:
                self._switch_to_paused_state()
            # 子场景b：当前为暂停状态，不处理
            elif self.State == self.STATE_PAUSED:
                logger.debug("已处于暂停状态，识别到暂停信号，不执行操作")
                return

        # 场景3：未识别到有效内容
        else:
            logger.warning("未识别到时间或暂停信号，常规校准无操作")
            return

    def _calibrate_running_state(self, recognized_screenshot_seconds, screenshot_perf_time, real_current_time):
        """
        运行状态下的校准逻辑：利用真实当前时间判断误差，按需重新校准并发布信号
        """
        # 计算本地当前计时时间
        current_perf_time = time.perf_counter()
        elapsed_perf_time = current_perf_time - self._base_perf_time
        local_calculated_seconds = self._calibration_offset - (elapsed_perf_time * self._time_speed)
        # 计算真实误差（真实当前时间 vs 本地计时时间）
        time_offset = abs(real_current_time - local_calculated_seconds)

        # 误差超过阈值，重新校准
        if time_offset > self._calibration_threshold:
            # 更新校准参数，基于真实当前时间重置
            self._base_perf_time = current_perf_time
            self._calibration_offset = real_current_time
            logger.info(
                f"运行状态校准 | 误差：{time_offset:.3f}s（超过阈值{self._calibration_threshold}s）| "
                f"截图时间：{recognized_screenshot_seconds}s | 真实当前时间：{real_current_time:.3f}s | 重新校准完成"
            )
            # 生成计时闭包
            time_closure = self._generate_time_closure()
            # 发布校准响应信号
            response_data = {
                "state": self.State,
                "time_offset": time_offset,
                "recognized_screenshot_seconds": recognized_screenshot_seconds,
                "real_current_time": real_current_time,
                "time_closure": time_closure
            }
            EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_CALIBRATE, response_data)
        else:
            logger.info(
                f"运行状态校准 | 误差：{time_offset:.3f}s（未超过阈值）| "
                f"截图时间：{recognized_screenshot_seconds}s | 真实当前时间：{real_current_time:.3f}s | 无需重新校准"
            )

        # 检查是否计时归零
        if real_current_time <= 3 or local_calculated_seconds <= 3:
            self.stop()

    def _calibrate_paused_state(self, recognized_screenshot_seconds, screenshot_perf_time, real_current_time):
        """
        暂停状态下的校准逻辑：利用真实当前时间恢复运行状态并发布信号
        """
        # 更新校准参数，基于真实当前时间重置
        current_perf_time = time.perf_counter()
        self._base_perf_time = current_perf_time
        self._calibration_offset = real_current_time
        # 切换为运行状态
        self.State = self.STATE_RUNNING
        # 启动校准定时器
        self._calibration_timer.start()
        # 生成计时闭包
        time_closure = self._generate_time_closure()
        # 发布恢复响应信号
        response_data = {
            "state": self.State,
            "recognized_screenshot_seconds": recognized_screenshot_seconds,
            "real_current_time": real_current_time,
            "time_closure": time_closure
        }
        EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_RESUME, response_data)
        logger.info(
            f"暂停状态校准 | 截图时间：{recognized_screenshot_seconds}s | 真实当前时间：{real_current_time:.3f}s | "
            f"已切换为运行状态（State=1）"
        )

    def _switch_to_paused_state(self):
        """
        从运行状态切换为暂停状态：记录固定时间，停止定时器，发布信号
        """
        # 计算当前剩余时间并保存为固定值
        self._paused_fixed_seconds = self._get_remaining_seconds()
        # 切换为暂停状态
        self.State = self.STATE_PAUSED
        # 停止常规校准定时器
        # self._calibration_timer.stop()
        # 生成固定时间闭包
        time_closure = self._generate_time_closure()
        # 发布暂停响应信号
        response_data = {
            "state": self.State,
            "fixed_seconds": self._paused_fixed_seconds,
            "time_closure": time_closure
        }
        EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_PAUSE, response_data)
        logger.info(f"已切换为暂停状态（State=2）| 固定剩余时间：{self._paused_fixed_seconds:.3f}s")

    def stop(self):
        """
        【修改】停止计时器：切换为关闭状态，停止所有定时器，重置标志位和参数，发布停止信号
        """
        if self.State != self.STATE_STOPPED:
            # 停止常规校准定时器
            if self._calibration_timer.isActive():
                self._calibration_timer.stop()
            # 停止首次校准定时器（防止残留轮询）
            if self._first_calibration_timer.isActive():
                self._first_calibration_timer.stop()
            # 重置首次校准中标志位
            self._is_first_calibrating = False
            # 切换为关闭状态
            self.State = self.STATE_STOPPED
            # 重置计时参数
            self._base_perf_time = 0.0
            self._calibration_offset = 0.0
            self._paused_fixed_seconds = 0.0
            self._current_recognized_seconds = None
            # 发布停止响应信号
            response_data = {
                "state": self.State,
                "time_closure": lambda: None
            }
            EventBusInstance.publish(GlobalEvents.RES_TASKTIME_TIMER_STOP, response_data)
            logger.info("计时器已停止，切换为关闭状态（State=0），所有定时器已停止，标志位已重置")
        else:
            logger.warning("计时器已处于关闭状态（State=0），忽略停止请求")

    def _generate_time_closure(self):
        """
        生成计时闭包：根据当前状态返回对应剩余时间
        """
        # 关闭状态：闭包返回None
        if self.State == self.STATE_STOPPED:
            def stopped_closure():
                return None
            logger.debug("生成关闭状态计时闭包（返回None）")
            return stopped_closure

        # 暂停状态：闭包返回固定剩余时间
        elif self.State == self.STATE_PAUSED:
            fixed_seconds = self._paused_fixed_seconds
            def paused_closure():
                return fixed_seconds
            logger.debug(f"生成暂停状态计时闭包（返回固定值：{fixed_seconds:.3f}s）")
            return paused_closure

        # 运行状态：闭包返回实时剩余时间
        elif self.State == self.STATE_RUNNING:
            base_perf_time = self._base_perf_time
            time_speed = self._time_speed
            calibration_offset = self._calibration_offset

            def running_closure():
                elapsed_perf_time = time.perf_counter() - base_perf_time
                local_calculated_seconds = calibration_offset - (elapsed_perf_time * time_speed)
                # 剩余时间不小于0
                return max(0.0, local_calculated_seconds)

            logger.debug("生成运行状态计时闭包（返回实时计算值）")
            return running_closure

    def _get_remaining_seconds(self):
        """
        获取当前剩余时间（内部辅助方法）
        """
        if self.State == self.STATE_STOPPED:
            return None
        elif self.State == self.STATE_PAUSED:
            return self._paused_fixed_seconds
        elif self.State == self.STATE_RUNNING:
            elapsed_perf_time = time.perf_counter() - self._base_perf_time
            local_calculated_seconds = self._calibration_offset - (elapsed_perf_time * self._time_speed)
            return max(0.0, local_calculated_seconds)

    def _ocr_recognize(self, pixmap):
        """
        OCR识别：将QPixmap转为numpy数组，识别时间或暂停信号
        """
        # 转换QPixmap为numpy数组
        img = self._pixmap_to_numpy(pixmap)
        # OCR识别
        try:
            result = self.reader.readtext(img, detail=0, allowlist="()在后净化0123456789:暂停")
            logger.debug(f"OCR识别结果：{result}")
        except Exception as e:
            logger.error(f"OCR识别失败 | 异常信息：{str(e)}")
            return None

        # 匹配暂停或时间格式
        for item in result:
            if "暂停" in item:
                return "暂停"

            pattern = r'\(在(\d+:\d+)后净化\)'
            match_result = re.fullmatch(pattern, item)
            if match_result:
                return match_result.group(1)

            pattern = r'\(在(\d+)后净化\)'
            match_result = re.fullmatch(pattern, item)
            if match_result:
                if len(match_result.group(1)) == 3:
                    logger.debug(f"未识别到分号，直接解析：{item}")
                    m = match_result.group(1)[0]
                    s = match_result.group(1)[1:]
                    return f"{m}:{s}"
        return None

    def _parse_time_str_to_seconds(self, time_str):
        """
        时间字符串转秒数：解析mm:ss格式为总秒数
        """
        try:
            minute, second = time_str.split(":")
            return int(minute) * 60 + int(second)
        except (ValueError, AttributeError):
            logger.warning(f"无效时间字符串：{time_str}，解析失败")
            return None

    def _pixmap_to_numpy(self, pixmap):
        """
        QPixmap转numpy数组：适配EasyOCR识别格式
        """
        h, w = pixmap.height(), pixmap.width()
        qimage = QImage(pixmap)
        buffer = qimage.constBits()
        buffer.setsize(h * w * 4)
        arr = np.frombuffer(buffer, dtype=np.uint8).reshape((h, w, 4))
        return arr