from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class TianJieFengSuo(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.27, 0.17),
            "B" : (0.83, 0.71)
        }

        map_process_table = [
            ("4:00", "红点A\n中"),
            ("6:00", "奖励"),
            ("8:00", "红点B\n中"),
            ("11:00", "红点A\n中"),
            ("11:00", "红点B\n右->下->中"),
            ("14:00", "红点A\n右->下->中"),
            ("14:00", "红点B\n下->中"),
            ("17:00", "红点A\n下->中"),
            ("17:00", "红点B\n右->下"),

            ("19:00", "红点A\n右->下"),
            ("19:00", "红点B\n左"),
            ("21:00", "红点A\n左"),
            ("21:00", "红点B\n右->中"),
            ("23:00", "红点A\n右->中"),
            ("23:00", "红点B\n右->上"),
            ("25:00", "红点A\n右->上"),
            ("25:00", "红点B\n右->下"),

            # 重复+8分钟
            ("27:00", "红点A\n右->下"),
            ("27:00", "红点B\n左"),
            ("29:00", "红点A\n左"),
            ("29:00", "红点B\n右->中"),
            ("31:00", "红点A\n右->中"),
            ("31:00", "红点B\n右->上"),
            ("33:00", "红点A\n右->上"),
            ("33:00", "红点B\n右->下"),

            # 重复+8分钟
            ("35:00", "红点A\n右->下"),
            ("35:00", "红点B\n左"),
            ("37:00", "红点A\n左"),
            ("37:00", "红点B\n右->中"),
            ("39:00", "红点A\n右->中"),
            ("39:00", "红点B\n右->上"),
            ("41:00", "红点A\n右->上"),
            ("41:00", "红点B\n右->下"),

            # 重复+8分钟
            ("43:00", "红点A\n右->下"),
            ("43:00", "红点B\n左"),
            ("45:00", "红点A\n左"),
            ("45:00", "红点B\n右->中"),
            ("47:00", "红点A\n右->中"),
            ("47:00", "红点B\n右->上"),
            ("49:00", "红点A\n右->上"),
            ("49:00", "红点B\n右->下"),

            # 重复+8分钟
            ("51:00", "红点A\n右->下"),
            ("51:00", "红点B\n左"),
            ("53:00", "红点A\n左"),
            ("53:00", "红点B\n右->中"),
            ("55:00", "红点A\n右->中"),
            ("55:00", "红点B\n右->上"),
            ("57:00", "红点A\n右->上"),
            ("57:00", "红点B\n右->下"),

        ]
        point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"])
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