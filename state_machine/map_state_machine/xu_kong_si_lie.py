from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class XuKongSiLie(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.type = None

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.58, 0.07),
            "B" : (0.95, 0.55),
        }

        map_process_table = [
            ("3:00", "红点B（可能）"),
            ("4:00", "红点A（可能）"),
        ]
        point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"])
        ]

        self.add_sequential_state(
            map_process_table=map_process_table,
            point_on_minimap=point_on_minimap,
            check_func=lambda: True
        )

        # =====================================
        # 等待红点判断
        # =====================================

        def map_process_table_func():
            result = None
            if self.type == "A":
                result = [
                    ("3:00", "红点B"),
                    ("6:00", "红点B"),
                    ("9:00", "红点A"),
                    ("12:00", "红点A"),
                    ("15:00", "红点B"),
                    ("18:00", "红点B"),
                    ("21:00", "红点A"),
                    ("24:00", "红点B"),

                    ("27:00", "红点A"),
                    ("27:00", "红点B"),

                    ("30:00", "红点A"),
                    ("30:00", "红点B"),

                    ("33:00", "红点A"),
                    ("33:00", "红点B"),

                    ("36:00", "红点A"),
                    ("36:00", "红点B"),

                    ("39:00", "红点A"),
                    ("39:00", "红点B"),

                    ("42:00", "红点A"),
                    ("42:00", "红点B"),

                    ("45:00", "红点A"),
                    ("45:00", "红点B"),

                    ("48:00", "红点A"),
                    ("48:00", "红点B"),

                    ("51:00", "红点A"),
                    ("51:00", "红点B"),

                    ("54:00", "红点A"),
                    ("54:00", "红点B"),

                    ("57:00", "红点A"),
                    ("57:00", "红点B")
                ]
            elif self.type == "B":
                result = [
                    ("4:00", "红点A"),
                    ("8:00", "红点B"),
                    ("10:00", "红点A"),
                    ("14:00", "红点A"),
                    ("16:00", "红点B"),
                    ("20:00", "红点A"),
                    ("22:00", "红点B"),
                    ("26:00", "红点A"),

                    ("29:00", "红点A"),
                    ("29:00", "红点B"),

                    ("32:00", "红点A"),
                    ("32:00", "红点B"),

                    ("35:00", "红点A"),
                    ("35:00", "红点B"),

                    ("38:00", "红点A"),
                    ("38:00", "红点B"),

                    ("41:00", "红点A"),
                    ("41:00", "红点B"),

                    ("44:00", "红点A"),
                    ("44:00", "红点B"),

                    ("47:00", "红点A"),
                    ("47:00", "红点B"),

                    ("50:00", "红点A"),
                    ("50:00", "红点B"),

                    ("53:00", "红点A"),
                    ("53:00", "红点B"),

                    ("57:00", "红点A"),
                    ("57:00", "红点B"),
                ]
            return result
        map_process_table = map_process_table_func

        point_on_minimap = None

        def check_func():
            if "3:30" >= self.gametime_timer() >= "3:00":
                # 拿小地图截图
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_B = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["B"])
                if result_B:
                    # 说明红点来自B
                    # 设置红点波形为A，来自NGA
                    self.type = "A"
                    logger.debug(f"【虚空撕裂】三分钟检测到第一波红点来自B，设置波形为A，进入下一状态")
                    return True
            if self.gametime_timer() >= "3:30":
                self.type = "B"
                logger.debug(f"【虚空撕裂】三分钟未检测到第一波红点来自B，设置波形为B，进入下一状态")
                return True
            # if "4:30" >= self.gametime_timer() >= "4:00":
            #     # 拿小地图截图
            #     EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
            #     mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
            #     result_A = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["A"])
            #     if result_A:
            #         # 说明红点来自A
            #         # 设置红点波形为B，来自NGA
            #         self.type = "B"
            #         logger.debug(f"【虚空撕裂】三分钟检测到第一波红点来自A，设置波形为B，进入下一状态")
            #         return True
            return False

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