from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class XuKongJiangLin(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.type = None

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.435, 0.31),
            "B" : (0.65, 0.4),
        }

        map_process_table = [
            ("3:00", "红点B"),
            ("5:00", "红点A"),
            ("7:30", "红点A/B\n(看二矿建筑数，谁多打谁，相等打右边的)"),
            ("10:00", "红点B"),
            ("11:00", "红点A"),
            ("14:00", "红点A/B\n(看最左右两侧的航道附近建筑数，谁少打谁，相等打右边的)"),
            ("16:48", "红点A"),
            ("19:18", "红点B"),
            ("21:48", "红点B"),
            ("24:18", "红点B"),

            ("10:00", "反奖励红点B"),
            ("16:20", "反奖励红点B"),
            ("21:40", "反奖励红点A"),

            ("6:15", "穿梭机\n中->中"),
            ("9:00", "穿梭机\n中->左/右"),
            ("12:30", "穿梭机\n中->左/右"),
            ("15:30", "穿梭机\n左->左/中"),
            ("15:30", "穿梭机\n右->中 / 中->右"),
            ("18:00", "穿梭机\n左中右->中"),
            ("20:30", "穿梭机\n左->右 / 右->左"),
            ("23:00", "穿梭机\n中中/左右/中右"),
            ("23:35", "穿梭机（可能）\n左->中\n右->中"),
            ("23:45", "穿梭机（可能）\n中->中\n左->左"),
            ("23:40", "穿梭机（可能）\n左->左\n右->右"),
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
        # 等到23分钟判断最后一波的波形
        # =====================================

        def map_process_table_func():
            result = None
            if self.type == "A":
                result = [
                    ("23:00", "穿梭机\n中->中\n右->右"),
                    ("23:45", "穿梭机\n中->中\n左->左"),
                    ("24:18", "红点B"),
                ]
            elif self.type == "B":
                result = [
                    ("23:00", "穿梭机\n中->左\n中->右"),
                    ("23:35", "穿梭机\n左->中\n右->中"),
                    ("24:18", "红点B"),
                ]
            elif self.type == "C":
                result = [
                    ("23:00", "穿梭机\n左->中\n右->中"),
                    ("23:40", "穿梭机\n左->左\n右->右"),
                    ("24:18", "红点B"),
                ]
            return result
        map_process_table = map_process_table_func
        point_on_minimap = None

        def check_func():
            if "23:30" >= self.gametime_timer() >= "23:00":
                # 拿小地图截图
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_left = self.judge_green_label_in_img(mini_map_pixmap, 0.325, 0.1)
                result_middle = self.judge_green_label_in_img(mini_map_pixmap, 0.622, 0.06)
                result_right = self.judge_green_label_in_img(mini_map_pixmap, 0.835, 0.17)
                if result_middle and result_right and not result_left:
                    self.type = "A"
                    logger.debug(f"【虚空降临】{self.type}")
                    return True
                if result_middle and not result_right and not result_left:
                    self.type = "B"
                    logger.debug(f"【虚空降临】{self.type}")
                    return True
                if result_left and result_right and not result_middle:
                    self.type = "C"
                    logger.debug(f"【虚空降临】{self.type}")
                    return True
                logger.debug(f"【虚空降临】检测结果{result_left, result_middle, result_right}")
            if self.gametime_timer() > "23:30":
                return True
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