from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class HeiAnShaXing(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.type = None

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.04, 0.74),
            "B" : (0.555, 0.07),
            "a" : (0.25, 0.74),
            "b" : (0.602, 0.185)
        }

        map_process_table = [
            ("2:48", "红点B/A"),
            ("7:00", "红点A/B"),
            ("9:00", "红点A"),
            ("12:30", "红点B"),
            ("16:00", "红点A/B"),
            ("19:00", "红点A/B"),
            ("22:00", "红点A/B"),
            ("24:00", "红点A/B"),
            ("26:00", "红点A/B"),
        ]
        point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"]),
            ("a", *_RED_POINTS["a"]),
            ("b", *_RED_POINTS["b"]),
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
                    ("2:48", "红点B/A"),
                    ("7:00", "红点A/B"),
                    ("9:00", "红点A"),
                    ("12:30", "红点B"),
                    ("16:00", "红点A/B"),
                    ("19:00", "红点A/B"),
                    ("22:00", "红点A/B"),
                    ("24:00", "红点A/B"),
                    ("26:00", "红点A/B"),
                ]
            if self.type == "A":
                map_process_table = [
                    ("2:48", "红点B"),
                    ("7:00", "红点A"),
                    ("9:00", "红点A"),
                    ("12:30", "红点B"),
                    ("16:00", "红点A/B"),
                    ("19:00", "红点A/B"),
                    ("22:00", "红点A/B"),
                    ("24:00", "红点A/B"),
                    ("26:00", "红点A/B"),
                ]
            elif self.type == "B":
                map_process_table = [
                    ("2:48", "红点A"),
                    ("7:00", "红点B"),
                    ("9:00", "红点A"),
                    ("12:30", "红点B"),
                    ("16:00", "红点A/B"),
                    ("19:00", "红点A/B"),
                    ("22:00", "红点A/B"),
                    ("24:00", "红点A/B"),
                    ("26:00", "红点A/B"),
                ]
            return map_process_table
        def check_func():
            if self.gametime_timer() >= "3:20":
                logger.debug(f"【黑暗杀星】第一波红点未检测出来，进入下一状态")
                EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                return True
            if self.gametime_timer() >= "2:48":
                # 拿小地图截图
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_A = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["A"])
                result_B = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["B"])
                if result_B and not result_A:
                    # 说明红点来自B，进入第下一个状态
                    # 设置红点波形为A，来自NGA
                    self.type = "A"
                    logger.debug(f"【黑暗杀星】第一波红点来自B，已确定波型，进入下一状态")
                    EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                    return True
                elif not result_B and result_A:
                    # 说明红点来自A，进入第下一个状态
                    # 设置红点波形为B，来自NGA
                    self.type = "B"
                    logger.debug(f"【黑暗杀星】第一波红点来自A，已确定波型，进入下一状态")
                    EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                    return True

                logger.debug(f"【黑暗杀星】第一波红点未判断出来【A：{result_A}】【B：{result_B}】")
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