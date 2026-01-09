from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class JiHuiMiaoMang(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.38, 0.19),
            "B" : (0.615, 0.095),
        }

        _SAORAO_POINTS = {
            1 : [
                ("2", 0.6, 0.45),
                ("1", 0.33, 0.43),
            ],
            2 : [
                ("1", 0.15, 0.62),
                ("2", 0.34, 0.38),
                ("3", 0.56, 0.47),
            ],
            3 : [
                ("1", 0.37, 0.15),
                ("2", 0.7, 0.18),
                ("3", 0.4, 0.32),
                ("4", 0.45, 0.4),
                ("5", 0.76, 0.31),
                ("6", 0.72, 0.4),
            ],
            4 : [
                ("1", 0.23, 0.18),
                ("2", 0.38, 0.14),
                ("3", 0.69, 0.35),
                ("4", 0.22, 0.6),
            ],
            5 : [
                ("1", 0.38, 0.14),
                ("2", 0.62, 0.08),
                ("3", 0.89, 0.06),
                ("4", 0.85, 0.53),
            ],
        }

        self.map_process_table = [
            ("1:00", "本图提醒：\n骚扰波次实际会比描述晚几秒到十几秒"),

            ("3:00", "红点B"),
            ("10:00", "红点A"),
            ("15:30", "红点B"),
            ("21:15", "红点A"),
            ("28:06", "红点A"),

            ("11:18", "奖励1"),
            ("23:09", "奖励2"),

            # 1
            ("5:00", "骚扰1/2"),
            ("5:25", "骚扰1/2"),

            # 2
            ("8:15", "骚扰2/3"),
            ("8:35", "骚扰1/2/3"),
            ("8:55", "骚扰1/2/3"),
            ("9:15", "骚扰1/2/3"),

            # 3
            ("12:25", "骚扰1/2/3"),
            ("12:45", "骚扰1/2/3"),
            ("13:05", "骚扰2/3/4/5"),
            ("13:25", "骚扰2/3/4/5"),
            ("13:45", "骚扰2/3/4/5"),
            ("14:05", "骚扰6"),

            # 4
            ("18:38", "骚扰1/4"),
            ("19:08", "骚扰2/3/4"),
            ("19:38", "骚扰2/3/4"),
            ("19:38", "骚扰1/4"),
            ("20:08", "骚扰2/3/4"),
            ("20:38", "骚扰2/3/4"),

            # 5
            ("25:08", "骚扰1/3"),
            ("25:23", "骚扰4"),
            ("25:38", "骚扰2/3"),
            ("25:53", "骚扰1/2/3/4"),
            ("26:23", "骚扰1/3"),
            ("26:53", "骚扰1/2/3/4"),
            ("27:23", "骚扰4"),
            ("27:53", "骚扰1/2/3/4"),
            ("28:23", "骚扰2/3"),

        ]
        self.point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"]),
        ]


        def check_func():
            return True

        self.add_sequential_state(
            map_process_table=self.map_process_table,
            point_on_minimap=self.point_on_minimap + _SAORAO_POINTS[1],
            check_func=check_func
        )

        # =====================================
        # 5分55切换骚扰2的点位
        # =====================================
        def check_func():
            if self.gametime_timer() >= "5:55":
                return True
            return False

        self.add_sequential_state(
            point_on_minimap=self.point_on_minimap + _SAORAO_POINTS[2],
            check_func=check_func
        )


        # =====================================
        # 9分45切换骚扰3的点位
        # =====================================

        def check_func():
            if self.gametime_timer() >= "9:45":
                return True
            return False

        self.add_sequential_state(
            point_on_minimap=self.point_on_minimap + _SAORAO_POINTS[3],
            check_func=check_func
        )

        # =====================================
        # 14分35切换骚扰4的点位
        # =====================================

        def check_func():
            if self.gametime_timer() >= "14:35":
                return True
            return False

        self.add_sequential_state(
            point_on_minimap=self.point_on_minimap + _SAORAO_POINTS[4],
            check_func=check_func
        )

        # =====================================
        # 21分08切换骚扰5的点位
        # =====================================

        def check_func():
            if self.gametime_timer() >= "21:08":
                return True
            return False

        self.add_sequential_state(
            point_on_minimap=self.point_on_minimap + _SAORAO_POINTS[5],
            check_func=check_func
        )


        # =====================================
        # 最终状态等待外部状态机切换
        # =====================================

        self.add_sequential_state(
            check_func= lambda: False
        )