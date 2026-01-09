# 导入所需模块
import time
import logging
import numpy as np
from PyQt5.QtCore import QObject, QTimer, pyqtSlot
from PyQt5.QtGui import QPixmap, QImage
import easyocr

from core.event_bus import EventBusInstance  # 统一为EventBusInstance单例
from core.global_event_enums import GlobalEvents

# 配置日志
logger = logging.getLogger(__name__)

class GametimeTimer(QObject):
    """
    游戏时间计时器
    独立Qt组件运行，支持自定义时间流速（默认1.4倍），内置状态管理与自动校准功能

    状态说明：
        State = 0：关闭状态
        State = 1：运行状态
        State = 2：异常状态

    核心功能：
    1.  订阅EventBusInstance请求信号，响应开启、关闭、时间获取操作
    2.  启动时持续阻塞截图识别，直到首次检测到时间并校准，切换为运行状态
    3.  运行/异常状态下周期性自动校准，异常状态识别成功自动恢复运行状态
    4.  异常状态累计超时后自动停止（仅切换状态+暂停定时器，不销毁资源）
    5.  停止后可重新启动，所有资源保留无需重新初始化
    6.  所有关键操作（启动、校准）均携带时间闭包，保证时间获取精度

    信号订阅与发布：
        订阅信号：
            REQ_GAMETIME_TIMER_START：开启计时器请求
            REQ_GAMETIME_TIMER_STOP：关闭计时器请求
            REQ_GAMETIME_TIMER_GETTIME：时间闭包获取请求
        发布信号：
            RES_GAMETIME_TIMER_START：启动成功响应（携带时间闭包）
            RES_GAMETIME_TIMER_CALIBRATE：校准成功响应（携带时间闭包）
            RES_GAMETIME_TIMER_STOP：停止/超时关闭响应
    """
    # 状态常量
    STATE_STOPPED = 0    # 关闭状态
    STATE_RUNNING = 1    # 运行状态
    STATE_EXCEPTION = 2  # 异常状态

    def __init__(self, time_speed=1.4, calibration_interval=1000, exception_threshold=20.0):
        """
        初始化游戏时间计时器（Qt独立组件）

        Parameters:
            time_speed (float): 时间流速，默认1.4倍正常时间流速，1.0为正常流速
            calibration_interval (int): 内置QTimer校准循环间隔，单位毫秒，默认1000ms
            exception_threshold (float): 异常状态持续时间阈值，单位秒，默认20.0秒
        """
        super().__init__()

        # 核心状态变量
        self.State = self.STATE_STOPPED  # 初始状态：关闭

        # 校准核心属性
        self._calibration_offset = 0.0  # 校准偏移量（用于对齐实际时间）
        self._base_perf_time = time.perf_counter()  # 高精度基准时间
        self._time_speed = time_speed  # 时间流速
        self._calibration_threshold = 1.0  # 校准误差阈值（秒）

        # 连续超阈值保护相关属性
        self._continuous_calibrate_threshold = 3  # 连续超阈值次数阈值
        self._continuous_over_threshold_count = 0  # 连续超阈值计数器，初始化为0

        # 异常状态核心属性
        self._exception_threshold = exception_threshold  # 异常超时阈值
        self._exception_start_time = None  # 异常状态开始时间
        self._exception_duration = 0.0  # 异常状态累计持续时间

        # 内置QTimer（校准循环核心）
        self.calibration_interval = calibration_interval
        self._calibration_timer = QTimer(self)
        self._calibration_timer.timeout.connect(self._on_calibration_timeout)

        # 初始化EasyOCR阅读器（英文识别，优先GPU加速）
        self.reader = easyocr.Reader(['en'], gpu=True)

        # 订阅事件总线的指定请求信号
        self._subscribe_event_bus_signals()

        logger.info(
            "游戏时间计时器初始化完成 | 时间流速：%.1fx | 校准间隔：%dms | 异常超时阈值：%.1fs",
            self._time_speed, self.calibration_interval, self._exception_threshold
        )

    def _subscribe_event_bus_signals(self):
        """
        统一订阅EventBusInstance的3个指定请求信号，绑定对应处理函数
        """
        # 1. 订阅「游戏时间计时器_开启_请求」信号
        EventBusInstance.subscribe(
            GlobalEvents.REQ_GAMETIME_TIMER_START,
            self._on_timer_start_request
        )
        # 2. 订阅「游戏时间计时器_关闭_请求」信号
        EventBusInstance.subscribe(
            GlobalEvents.REQ_GAMETIME_TIMER_STOP,
            self._on_timer_stop_request
        )
        # 3. 订阅「游戏时间计时器_时间获取_请求」信号
        EventBusInstance.subscribe(
            GlobalEvents.REQ_GAMETIME_TIMER_GETTIME,
            self._on_timer_gettime_request
        )
        logger.info(
            "已订阅事件总线游戏时间计时器请求信号：%s、%s、%s",
            GlobalEvents.REQ_GAMETIME_TIMER_START,
            GlobalEvents.REQ_GAMETIME_TIMER_STOP,
            GlobalEvents.REQ_GAMETIME_TIMER_GETTIME
        )

    @pyqtSlot()
    def _on_timer_start_request(self, *args, **kwargs):
        """
        响应EventBusInstance的「游戏时间计时器_开启_请求」信号
        停止状态下可重新启动，无需重新初始化资源
        """
        if self.State != self.STATE_RUNNING:
            logger.info("接收到事件总线开启请求，执行首次阻塞校准")
            # 执行首次阻塞校准，直到识别到有效时间
            calibration_success = self._perform_first_blocking_calibration()
            if calibration_success:
                # 设置为运行状态
                self.State = self.STATE_RUNNING
                # 启动校准定时器（停止后重新启动时，timer可直接复用）
                self._calibration_timer.start(self.calibration_interval)
                # 生成时间闭包
                time_closure = self.get_current_time_func()
                # 发布启动成功响应信号
                start_response = {
                    "state": self.State,
                    "time_speed": self._time_speed,
                    "time_closure": time_closure
                }
                EventBusInstance.publish(GlobalEvents.RES_GAMETIME_TIMER_START, start_response)
                logger.info("计时器启动成功，已切换为运行状态（State=1），并发布启动响应信号")
            else:
                logger.error("首次阻塞校准失败，计时器启动失败")
        else:
            logger.warning("接收到事件总线开启请求，但计时器已处于运行状态，无需重复启动")

    @pyqtSlot()
    def _on_timer_stop_request(self, *args, **kwargs):
        """
        响应EventBusInstance的「游戏时间计时器_关闭_请求」信号
        """
        if self.State != self.STATE_STOPPED:
            self.stop()
            logger.info("接收到事件总线关闭请求，已停止计时器")
        else:
            logger.warning("接收到事件总线关闭请求，但计时器已处于停止状态，无需重复停止")

    @pyqtSlot()
    def _on_timer_gettime_request(self, *args, **kwargs):
        """
        响应EventBusInstance的「游戏时间计时器_时间获取_请求」信号
        严格返回当前时间闭包函数
        """
        time_closure = self.get_current_time_func()
        result = {
            "time_closure": time_closure,
        }
        EventBusInstance.shared_data[GlobalEvents.RES_GAMETIME_TIMER_GETTIME] = result
        logger.debug("接收到游戏时间计时器时间获取请求，已返回对应时间闭包")
        return time_closure

    def get_current_time_func(self):
        """
        生成并返回当前时间闭包函数
        1.  关闭状态：返回直接返回None的可调用函数
        2.  运行/异常状态：返回本地精准计算时间的闭包
        """
        # 关闭状态：返回返回None的匿名函数
        if self.State == self.STATE_STOPPED:
            logger.debug("计时器当前处于关闭状态，时间闭包将返回None")
            return lambda: None

        # 运行/异常状态：返回精准计算闭包
        base_perf_time = self._base_perf_time
        time_speed = self._time_speed
        calibration_offset = self._calibration_offset

        def calculate_current_time():
            """
            闭包内部函数：本地实时计算校准后的当前时间
            双重保障：执行时再次判断关闭状态，避免异常
            """
            if self.State == self.STATE_STOPPED:
                return None
            local_perf_time = time.perf_counter()
            elapsed_perf_time = local_perf_time - base_perf_time
            scaled_elapsed_time = elapsed_perf_time * time_speed
            return scaled_elapsed_time + calibration_offset

        logger.debug("生成时间闭包，当前状态：%d", self.State)
        return calculate_current_time

    def _on_calibration_timeout(self):
        """
        QTimer超时槽函数，触发定时校准流程
        【修改点1】：运行状态/异常状态均执行校准，实现异常状态持续检测
        """
        # 运行状态和异常状态都执行校准，仅停止状态跳过
        if self.State in [self.STATE_RUNNING, self.STATE_EXCEPTION]:
            self._perform_auto_calibration()
        else:
            logger.debug(f"当前状态为{self.State}（停止状态），跳过校准流程")

    def _perform_first_blocking_calibration(self):
        """
        首次阻塞校准：持续调用截图请求，直到检测到有效时间并完成校准
        停止后重新启动时，可正常执行该方法
        """
        logger.info("开始首次阻塞校准，将持续截图识别直到获取有效时间")
        while True:
            # 阻塞获取截图及截图生成时间
            try:
                EventBusInstance.publish(GlobalEvents.REQ_GAMETIME_SCREENSHOT)
                screenshot_pixmap, screenshot_perf_time = EventBusInstance.shared_data[GlobalEvents.RES_GAMETIME_SCREENSHOT]
                if not isinstance(screenshot_pixmap, QPixmap):
                    logger.warning("获取无效截图，重试首次阻塞校准")
                    time.sleep(0.5)
                    continue
            except Exception as e:
                logger.warning(f"获取截图失败，重试首次阻塞校准 | 异常信息：{str(e)}")
                time.sleep(0.5)
                continue

            # 转换为numpy数组并识别时间
            recognized_screenshot_time = self.recognize_time(screenshot_pixmap)
            if recognized_screenshot_time is not None:
                # 修正信号传输损耗，计算真实当前时间
                current_perf_time = time.perf_counter()
                perf_time_diff = current_perf_time - screenshot_perf_time
                timer_time_diff = perf_time_diff * self._time_speed
                real_current_time = recognized_screenshot_time + timer_time_diff

                # 初始化/重置校准参数（支持重新启动时更新参数）
                self._base_perf_time = current_perf_time
                self._calibration_offset = real_current_time
                logger.info(
                    f"首次阻塞校准成功 | 截图时间：{recognized_screenshot_time:.3f}s | "
                    f"传输耗时：{perf_time_diff:.3f}s | 真实当前时间：{real_current_time:.3f}s"
                )
                return True

            # 未识别到有效时间，短暂休眠后重试
            time.sleep(0.5)

    def _perform_auto_calibration(self):
        """
        自动校准核心逻辑：处理时间识别结果，执行校准或异常状态切换
        【修改点2】：识别到有效时间时，强制恢复运行状态并重置异常属性
        """
        # 重置本次校准的异常累计时间
        self._exception_duration = 0.0

        try:
            # 步骤1：阻塞获取截图和截图生成时间
            EventBusInstance.publish(GlobalEvents.REQ_GAMETIME_SCREENSHOT)
            screenshot_pixmap, screenshot_perf_time = EventBusInstance.shared_data[GlobalEvents.RES_GAMETIME_SCREENSHOT]
            if not isinstance(screenshot_pixmap, QPixmap):
                logger.error("获取的截图不是有效QPixmap对象，触发异常状态处理")
                self._handle_calibration_exception()
                return False
        except Exception as e:
            logger.error(f"从EventBus获取时间截图失败：{str(e)}，触发异常状态处理")
            self._handle_calibration_exception()
            return False

        # 步骤2：转换为numpy数组并识别时间
        recognized_screenshot_time = self.recognize_time(screenshot_pixmap)

        # 场景1：检测到有效时间 → 恢复运行状态并重置异常属性
        if recognized_screenshot_time is not None:
            # 【关键修改】：强制切换为运行状态，重置异常相关属性
            self.State = self.STATE_RUNNING
            self._exception_start_time = None
            self._exception_duration = 0.0

            # 修正信号传输损耗，计算真实当前时间
            current_perf_time = time.perf_counter()
            perf_time_diff = current_perf_time - screenshot_perf_time
            timer_time_diff = perf_time_diff * self._time_speed
            real_current_time = recognized_screenshot_time + timer_time_diff

            # 计算本地当前计时时间和误差
            current_timer_time = self._get_immediate_current_time()
            time_offset = abs(real_current_time - current_timer_time)

            # 生成时间闭包
            time_closure = self.get_current_time_func()

            # 误差未超过阈值，校准检验通过
            if time_offset <= self._calibration_threshold:
                # 重置连续超阈值计数器
                self._continuous_over_threshold_count = 0
                logger.info(
                    f"校准检验通过 | 当前偏移量{time_offset:.3f}秒（≤阈值{self._calibration_threshold}秒）"
                )
                # 发布校准通过响应信号
                # calibration_response = {
                #     "calibration_result": "pass",
                #     "time_offset": time_offset,
                #     "real_current_time": real_current_time,
                #     "time_closure": time_closure
                # }
                # EventBusInstance.publish(GlobalEvents.RES_GAMETIME_TIMER_CALIBRATE, calibration_response)
                return True
        
            # 子场景1.2：误差超过阈值 → 累加连续超阈值计数器
            self._continuous_over_threshold_count += 1
            logger.warning(
                f"误差超过阈值 | 当前偏移量{time_offset:.3f}秒（>阈值{self._calibration_threshold}秒）| 连续超阈值次数：{self._continuous_over_threshold_count}/{self._continuous_calibrate_threshold}"
            )

            # 仅当连续超阈值次数达到配置阈值时，才执行校准
            if self._continuous_over_threshold_count >= self._continuous_calibrate_threshold:
                # 执行校准
                current_elapsed_perf = current_perf_time - self._base_perf_time
                current_scaled_time = current_elapsed_perf * self._time_speed
                self._calibration_offset = real_current_time - current_scaled_time

                logger.info(
                    f"计时器校准成功 | 偏移量：{time_offset:.3f}秒 | 真实当前时间：{real_current_time:.3f}秒 "
                    f"| 校准后计时器时间：{self._get_immediate_current_time():.3f}秒"
                )

                # 发布校准成功响应信号
                calibration_response = {
                    "calibration_result": "success",
                    "time_offset": time_offset,
                    "new_calibration_offset": self._calibration_offset,
                    "real_current_time": real_current_time,
                    "time_closure": self.get_current_time_func()
                }
                EventBusInstance.publish(GlobalEvents.RES_GAMETIME_TIMER_CALIBRATE, calibration_response)

                # 重置连续超阈值计数器
                self._continuous_over_threshold_count = 0
                return True
            else:
                # 连续次数未达标，不执行校准
                logger.info(
                    f"连续超阈值次数未达标，暂不校准 | 当前次数：{self._continuous_over_threshold_count}/{self._continuous_calibrate_threshold}"
                )
                return False

        # 场景2：未检测到有效时间，处理异常状态
        else:
            logger.warning("未从截图中识别到有效时间格式，触发异常状态处理")
            self._handle_calibration_exception()
            return False

    def _handle_calibration_exception(self):
        """
        处理校准异常（未检测到时间）：切换异常状态、累计异常时间、超时停止
        仅切换状态，不销毁任何资源，支持后续重新启动
        """
        current_perf_time = time.perf_counter()

        # 子场景a：当前为运行状态，切换为异常状态并记录开始时间
        if self.State == self.STATE_RUNNING:
            self.State = self.STATE_EXCEPTION
            self._exception_start_time = current_perf_time
            self._exception_duration = 0.0
            logger.info("计时器切换为异常状态（State=2），开始累计异常时间")

        # 子场景b：当前为异常状态，累计异常持续时间
        elif self.State == self.STATE_EXCEPTION:
            if self._exception_start_time is not None:
                self._exception_duration = current_perf_time - self._exception_start_time
                logger.debug(
                    f"异常状态持续时间：{self._exception_duration:.3f}s（阈值：{self._exception_threshold}s）"
                )

        # 判断异常持续时间是否超过阈值，超过则停止计时器（仅切换状态+暂停timer）
        if self._exception_duration >= self._exception_threshold:
            logger.warning(
                f"异常状态持续时间{self._exception_duration:.3f}s超过阈值{self._exception_threshold}s，自动停止计时器"
            )
            self.stop()

    def _get_immediate_current_time(self):
        """
        内部辅助方法：直接获取当前计时器时间（仅用于内部校准）
        """
        if self.State == self.STATE_STOPPED:
            return None
        elapsed_perf_time = time.perf_counter() - self._base_perf_time
        scaled_elapsed_time = elapsed_perf_time * self._time_speed
        return scaled_elapsed_time + self._calibration_offset

    def recognize_time(self, img):
        img = self.pixmap_to_numpy(img)
        # OCR识别文本（仅保留数字、:、.）
        result = self.reader.readtext(img, detail=0, allowlist="0123456789:")
        sep = ':'
        minute = None
        second = None
        # 筛选并处理时间格式
        for text in result:
            text = text.strip().replace(" ", "")
            logger.debug(f"OCR识别到文本：{text}")
            if sep in text:
                # 按分隔符分割为分钟和秒两部分
                time_parts = text.split(sep)
                # 确保分割后仅包含两部分
                if len(time_parts) == 2:
                    m_part, s_part = time_parts
                    try:
                        minute = int(m_part)
                        second = int(s_part)
                        # 秒数需小于60，保证时间有效性
                        if second <= 59 and minute <= 59:
                            break
                    except (ValueError, TypeError):
                        continue
            elif len(text) == 3 or len(text) == 4:
                minute = int(text[:-2])
                second = int(text[-2:])
                if second > 59:
                    second = None
                if minute > 59:
                    minute = None
        # 若成功提取分钟和秒，转换为总秒数返回
        if minute is not None and second is not None:
            total_seconds = minute * 60 + second
            logger.debug(f"识别到有效时间：{minute}分{second}秒，总秒数{total_seconds:.3f}")
            return total_seconds
        # 未识别到有效时间格式
        return None

    def pixmap_to_numpy(self, pixmap: QPixmap) -> np.ndarray:
        """
        将QPixmap对象转换为numpy数组（RGBA格式）
        """
        h, w = pixmap.height(), pixmap.width()
        # 将QPixmap转换为QImage，获取原始字节缓冲区
        qimage = QImage(pixmap)
        buffer = qimage.constBits()
        # 设置缓冲区大小（h*w*4：RGBA四通道）
        buffer.setsize(h * w * 4)
        # 转换为numpy数组并重塑形状
        arr = np.frombuffer(buffer, dtype=np.uint8).reshape((h, w, 4))
        return arr

    def start(self):
        """
        手动启动计时器（内部调用，外部通过事件总线触发）
        停止后可直接调用该方法重新启动，无需重新初始化
        """
        calibration_success = self._perform_first_blocking_calibration()
        if calibration_success:
            self.State = self.STATE_RUNNING
            self._calibration_timer.start(self.calibration_interval)
            logger.info("计时器手动启动成功，已切换为运行状态（State=1）")
        else:
            logger.error("计时器手动启动失败，首次阻塞校准未通过")

    def stop(self):
        """
        【修改点3】：停止计时器（仅切换状态+暂停定时器，不销毁资源，支持重新启动）
        1.  暂停校准定时器（不销毁，后续可直接start()）
        2.  切换状态为关闭（State=0）
        3.  重置异常相关属性
        4.  发布停止响应信号
        """
        # 暂停校准定时器（仅停止触发，不销毁对象）
        if self._calibration_timer.isActive():
            self._calibration_timer.stop()
            logger.debug("校准定时器已暂停")

        # 切换为关闭状态
        self.State = self.STATE_STOPPED

        # 重置异常相关属性（不影响其他核心资源：reader、_calibration_timer等）
        self._exception_start_time = None
        self._exception_duration = 0.0
        self._continuous_over_threshold_count = 0

        # 发布停止响应信号
        stop_response = {
            "state": self.State,
            "stop_reason": "manual" if self._exception_duration < self._exception_threshold else "exception_timeout"
        }
        EventBusInstance.publish(GlobalEvents.RES_GAMETIME_TIMER_STOP, stop_response)
        logger.info("计时器已停止，切换为关闭状态（State=0），并发布停止响应信号")