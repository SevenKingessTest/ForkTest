from PyQt5.QtCore import QObject, QThread, Qt, QMetaObject, Q_RETURN_ARG
from global_event_enums import GlobalEvents
from core.event_bus import EventBus
import queue
import logging


# ==========================================
# 通用业务管线
# ==========================================
class BusinessPipeline(QObject):
    """
    通用业务管线类：封装「事件订阅→队列→QThread→invokeMethod跨线程调用→结果发布」的完整逻辑
    初始化参数：
        event_bus: 全局事件总线实例
        req_event: 订阅的请求事件类型（如GlobalEvents.REQ_SCREENSHOT_A）
        res_event: 发布的结果事件类型（如GlobalEvents.RES_SCREENSHOT_A）
        process_func: 任务处理函数（如window_a.capture_a，需是窗口的方法）
        queue_size: 队列最大容量（默认10）
    """
    def __init__(self, event_bus: EventBus, req_event: GlobalEvents, res_event: GlobalEvents, process_func, queue_size=10, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.req_event = req_event
        self.res_event = res_event
        self.process_func = process_func  # 格式：window.capture_a（实例方法）
        self._is_running = True

        # 1. 专属队列
        self._task_queue = queue.Queue(maxsize=queue_size)

        # 2. Qt QThread（简化版：直接绑定任务循环）
        self._worker_thread = QThread()
        self._worker_thread.setObjectName(f"Pipeline-{req_event.value}")
        # 线程启动后执行任务循环，线程结束后清理
        self._worker_thread.started.connect(self._process_tasks)
        self._worker_thread.finished.connect(self._on_thread_finished)

        # 3. 订阅请求事件
        self.event_bus.subscribe(self.req_event, self._on_task_req)

        # 提取实例和方法名（用于invokeMethod调用）
        self._process_obj = self.process_func.__self__  # 截图窗口实例（如window_a）
        self._process_method_name = self.process_func.__name__  # 方法名（如"capture_a"）

    def start(self):
        """启动管线线程"""
        if not self._worker_thread.isRunning():
            self._worker_thread.start()
            logging.debug(f"管线[{self.req_event.value}]：启动成功（线程：{self._worker_thread.objectName()}）")

    def _on_task_req(self, task_data):
        """任务入队"""
        try:
            self._task_queue.put(task_data, block=True, timeout=0.5)
            logging.debug(f"管线[{self.req_event.value}]：任务入队，剩余{self._task_queue.qsize()}个")
        except queue.Full:
            logging.warning(f"管线[{self.req_event.value}]：队列满，丢弃任务")

    def _process_tasks(self):
        """QThread任务循环（运行在子线程）"""
        while self._is_running:
            try:
                # 阻塞取任务
                task_data = self._task_queue.get(block=True, timeout=0.2)
                logging.debug(f"管线[{self.req_event.value}]：开始处理任务")

                # 关键：直接使用invokeMethod实现阻塞跨线程调用（替代PipelineWorker）
                task_result = None
                # 判断是否需要传递task_data
                if task_data is None:
                    # 无参数调用：BlockingQueuedConnection（阻塞，线程安全）
                    success = QMetaObject.invokeMethod(
                        self._process_obj,  # 截图窗口实例
                        self._process_method_name,  # 截图方法名
                        Qt.BlockingQueuedConnection,
                        Q_RETURN_ARG(type(self.process_func()))  # 返回值类型（如QPixmap）
                    )
                    if success:
                        task_result = self.process_func()  # 无参时直接获取返回值
                else:
                    # 有参数调用：需确保process_func支持接收task_data
                    success = QMetaObject.invokeMethod(
                        self._process_obj,
                        self._process_method_name,
                        Qt.BlockingQueuedConnection,
                        Q_RETURN_ARG(type(self.process_func(task_data))),
                        task_data  # 传入任务数据
                    )
                    if success:
                        task_result = self.process_func(task_data)

                # 发布结果事件
                if task_result is not None:
                    self.event_bus.publish(self.res_event, task_result)
                    logging.debug(f"管线[{self.req_event.value}]：任务处理完成，已发布结果")
                else:
                    logging.warning(f"管线[{self.req_event.value}]：任务处理无结果")

                self._task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"管线[{self.req_event.value}]：任务处理失败：{e}")
                try:
                    self._task_queue.task_done()
                except:
                    pass

    def _on_thread_finished(self):
        """线程结束回调"""
        logging.debug(f"管线[{self.req_event.value}]：线程已结束")

    def stop(self):
        """停止管线"""
        self._is_running = False
        self._task_queue.join()
        if self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(1000)  # 超时1秒强制终止
        logging.debug(f"管线[{self.req_event.value}]：已停止")