from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class YanMieKuaiChe(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.1, 0.26),
            "B" : (0.9, 0.76),
        }

        map_process_table = [
            ("4:00", "红点A"),
            ("6:00", "红点B"),
            ("7:00", "红点A"),
            ("10:00", "红点B"),
            ("13:00", "红点A"),
            ("16:00", "红点A"),
            ("19:00", "红点B"),
            ("22:00", "红点A"),
            ("24:00", "红点B"),

            ("5:00", "上列车"),
            ("8:00", "下列车"),
            ("11:00", "上列车"),
            ("12:00", "奖励列车"),
            ("14:00", "上列车"),
            ("14:00", "下列车"),
            ("17:00", "下列车"),
            ("20:00", "上列车"),
            ("20:00", "下列车"),
            ("21:00", "奖励列车"),
            ("23:00", "下列车"),
            ("25:00", "上/下列车"),

        ]
        point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"]),
        ]

        def check_func():
            return True

        self.add_sequential_state(
            map_process_table=map_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )


        # =====================================
        # 最终状态等待外部状态机切换
        # =====================================

        self.add_sequential_state(
            check_func= lambda: False
        )