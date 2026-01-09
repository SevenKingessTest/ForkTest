from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class JuTieChengBing(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.type = None

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.05,0.05),
            "a" : (0.15,0.2),

            "B" : (0.33,0.03),
            "b" : (0.33,0.08),

            "C" : (0.92,0.62),
            "c" : (0.92,0.72),

            "D" : (0.82,0.95),
            "d" : (0.8,0.75),
        }

        map_process_table = [
            ("3:45", "红点B/C"),
            ("6:30", "红点C/B"),
            ("10:00", "红点A/D"),
            ("14:06", "红点B/C"),
            ("17:12", "红点A/D"),
            ("20:00", "红点B/C"),
            ("24:00", "红点B/C"),
            ("27:00", "红点B/C"),
            ("30:00", "红点B/C"),

            ("8:00", "奖励"),
            ("15:00", "奖励"),
        ]
        point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"]),
            ("C", *_RED_POINTS["C"]),
            ("D", *_RED_POINTS["D"]),
            ("a", *_RED_POINTS["a"]),
            ("b", *_RED_POINTS["b"]),
            ("c", *_RED_POINTS["c"]),
            ("d", *_RED_POINTS["d"]),
        ]

        def check_func():
            return True

        self.add_sequential_state(
            map_process_table=map_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 检验第一波红点位置
        # =====================================
        def map_process_table_func():
            map_process_table = [
                ("3:45", "红点B/C"),
                ("6:30", "红点C/B"),
                ("10:00", "红点A/D"),
                ("14:06", "红点B/C"),
                ("17:12", "红点A/D"),
                ("20:00", "红点B/C"),
                ("24:00", "红点B/C"),
                ("27:00", "红点B/C"),
                ("30:00", "红点B/C"),

                ("8:00", "奖励"),
                ("15:00", "奖励"),
            ]
            if self.type == "A":
                map_process_table = [
                    ("3:45", "红点B"),
                    ("6:30", "红点C"),
                    ("10:00", "红点A/D"),
                    ("14:06", "红点B/C"),
                    ("17:12", "红点A/D"),
                    ("20:00", "红点B/C"),
                    ("24:00", "红点B/C"),
                    ("27:00", "红点B/C"),
                    ("30:00", "红点B/C"),

                    ("8:00", "奖励"),
                    ("15:00", "奖励"),
                ]
            elif self.type == "B":
                map_process_table = [
                    ("3:45", "红点C"),
                    ("6:30", "红点B"),
                    ("10:00", "红点A/D"),
                    ("14:06", "红点B/C"),
                    ("17:12", "红点A/D"),
                    ("20:00", "红点B/C"),
                    ("24:00", "红点B/C"),
                    ("27:00", "红点B/C"),
                    ("30:00", "红点B/C"),

                    ("8:00", "奖励"),
                    ("15:00", "奖励"),
                ]
            return map_process_table
        def check_func():
            if self.gametime_timer() >= "4:00":
                logger.debug(f"【聚铁成兵】第一波红点未检测出来，进入下一状态")
                EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                return True
            if self.gametime_timer() >= "3:45":
                # 拿小地图截图
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_C = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["C"])
                result_B = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["B"])
                if result_B and not result_C:
                    # 说明红点来自B，进入第下一个状态
                    # 设置红点波形为A，来自NGA
                    self.type = "A"
                    logger.debug(f"【聚铁成兵】第一波红点来自B，已确定波型，进入下一状态")
                    EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                    return True
                elif not result_B and result_C:
                    # 说明红点来自C，进入第下一个状态
                    # 设置红点波形为B，来自NGA
                    self.type = "B"
                    logger.debug(f"【聚铁成兵】第一波红点来自C，已确定波型，进入下一状态")
                    EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                    return True

                logger.debug(f"【聚铁成兵】第一波红点未判断出来【B：{result_B}】【C：{result_C}】")
            return False

        self.add_sequential_state(
            map_process_table=map_process_table_func,
            check_func=check_func
        )


        # =====================================
        # 最终状态等待外部状态机切换
        # =====================================

        self.add_sequential_state(
            check_func= lambda: False
        )