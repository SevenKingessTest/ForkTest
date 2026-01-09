from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class KeHaLieHen(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.83, 0.49)
        }

        map_process_table = [
            ("2:00", "红点A"),
            ("5:00", "红点A"),
            ("8:00", "红点A"),
            ("11:00", "红点A"),
            ("14:00", "红点A"),
            ("17:00", "红点A"),
            ("20:30", "红点A"),
            ("24:30", "红点A"),
            ("26:30", "红点A"),
            ("28:30", "红点A"),
            ("30:00", "红点A"),
            ("11:40", "奖励目标1"),
            ("18:50", "奖励目标2"),
        ]
        task_process_table = None
        point_on_minimap = [
            ("A", *_RED_POINTS["A"])
        ]

        def check_func():
            return True

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )


        # =====================================
        # 最终状态等待外部状态机切换
        # =====================================

        self.add_sequential_state(
            check_func= lambda: False
        )