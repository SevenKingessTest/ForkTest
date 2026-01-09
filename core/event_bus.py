from PyQt5.QtCore import QObject, pyqtSignal
from core.global_event_enums import GlobalEvents

import logging

logger = logging.getLogger(__name__)

#==================
# 事件总线（单例）
#==================
class _EventBus(QObject):
    """内部EventBus类，不对外暴露"""
    _signal = pyqtSignal(GlobalEvents, object)

    def __init__(self):
        super().__init__()

        self.shared_data = {}

    def subscribe(self, event_type: GlobalEvents, handler):
        # 包装器仅保留事件类型匹配和处理器执行的核心逻辑
        def wrapper(e_type, e_data):
            # 仅当事件类型匹配时，执行处理器
            if e_type == event_type:
                try:
                    # 根据是否有事件数据，调用处理器
                    if e_data is not None:
                        handler(e_data)
                    else:
                        handler()
                except Exception as e:
                    # 保留异常抛出逻辑（按需可调整，如日志记录）
                    raise e

        # 无需加锁，直接注册事件回调
        self._signal.connect(wrapper)

    def publish(self, event_type: GlobalEvents, e_data=None):
        logger.debug(f"发布事件：{event_type}，数据：{e_data}")
        self._signal.emit(event_type, e_data)

# 模块级别创建唯一实例，对外暴露此实例（天然单例）
EventBusInstance = _EventBus()