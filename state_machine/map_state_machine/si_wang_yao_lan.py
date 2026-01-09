from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class SiWangYaoLan(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.now_target = [1]
        self.now_time = None

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.23, 0.22),
            "B" : (0.85, 0.26),
            "C" : (0.47, 0.77),
            "D" : (0.54, 0.77),
        }

        _MAIN_TARGET_POINT = {
            # "1" : (0.435, 0.31),
            "2" : (0.15, 0.35),
            "3" : (0.91, 0.47),
            "4" : (0.475, 0.775),
            "5" : (0.89, 0.83),
        }

        self.map_process_table = [
            ("4:00", "红点"),
            ("6:00", "红点"),
            ("9:30", "红点"),
            ("12:00", "红点"),
            ("15:00", "红点"),
            ("18:00", "红点"),
            ("21:00", "红点"),
            ("25:00", "红点"),
            ("29:00", "红点"),
            ("33:00", "红点"),
        ]
        point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"]),
            ("C", *_RED_POINTS["C"]),
            ("D", *_RED_POINTS["D"]),
        ]

        def map_process_table_func():
            map_process_table = []
            for i in range(len(self.map_process_table)):
                map_process_table.append((self.map_process_table[i][0], self.map_process_table[i][1] + "A/B"))
            return map_process_table

        def check_func():
            return True

        self.add_sequential_state(
            map_process_table=map_process_table_func,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 判断第二个任务目标
        # =====================================

        def map_process_table_func():
            map_process_table = [
                (self.calculate_time_str(str(self.now_time), 150, add=True), "骚扰卡车"),
                (self.calculate_time_str(str(self.now_time), 270, add=True), "骚扰卡车")
            ]
            if self.now_target[1] == 2:
                map_process_table.append((self.calculate_time_str(str(self.now_time), 45, add=True), "左上奖励1|右下奖励2"))
                for i in range(len(self.map_process_table)):
                    map_process_table.append((self.map_process_table[i][0], self.map_process_table[i][1] + "B"))
            elif self.now_target[1] == 3:
                map_process_table.append((self.calculate_time_str(str(self.now_time), 45, add=True), "右上奖励1|左下奖励2"))
                for i in range(len(self.map_process_table)):
                    map_process_table.append((self.map_process_table[i][0], self.map_process_table[i][1] + "A"))
            return map_process_table

        def check_func():
            # 拿小地图截图
            EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
            mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]

            result_2 = self.judge_green_label3_in_img(mini_map_pixmap, *_MAIN_TARGET_POINT["2"])
            result_3 = self.judge_green_label3_in_img(mini_map_pixmap, *_MAIN_TARGET_POINT["3"])
            if result_3 and not result_2:
                self.now_target.append(3)
                self.now_target.append(2)
                self.now_time = self.gametime_timer()
                logger.debug(f"【死亡摇篮】检测到目标列表{self.now_target}")
                return True
            elif result_2 and not result_3:
                self.now_target.append(2)
                self.now_target.append(3)
                self.now_time = self.gametime_timer()
                logger.debug(f"【死亡摇篮】检测到目标列表{self.now_target}")
                return True

            logger.debug(f"【死亡摇篮】检测结果result_2:{result_2} result_3:{result_3}")
            return False

        self.add_sequential_state(
            map_process_table=map_process_table_func,
            check_func=check_func
        )

        # =====================================
        # 检测第三个任务目标触发了没有
        # =====================================
        def map_process_table_func():
            map_process_table = [
                (self.calculate_time_str(str(self.now_time), 90, add=True), "骚扰卡车"),
                (self.calculate_time_str(str(self.now_time), 150, add=True), "骚扰卡车"),
                (self.calculate_time_str(str(self.now_time), 270, add=True), "骚扰卡车")
            ]
            if self.now_target[2] == 2:
                for i in range(len(self.map_process_table)):
                    map_process_table.append((self.map_process_table[i][0], self.map_process_table[i][1] + "D"))
            elif self.now_target[2] == 3:
                for i in range(len(self.map_process_table)):
                    map_process_table.append((self.map_process_table[i][0], self.map_process_table[i][1] + "C"))
            return map_process_table

        def check_func():
            # 拿小地图截图
            EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
            mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]

            result = self.judge_green_label3_in_img(mini_map_pixmap, *_MAIN_TARGET_POINT[str(self.now_target[2])])
            if result:
                self.now_target.append(self.now_target[2])
                self.now_time = self.gametime_timer()
                logger.debug(f"【死亡摇篮】检测到第三个任务目标被触发")
                return True
            return False


        self.add_sequential_state(
            map_process_table=map_process_table_func,
            check_func=check_func
        )

        # =====================================
        # 判断第四个任务目标
        # =====================================

        def map_process_table_func():
            map_process_table = [
                (self.calculate_time_str(str(self.now_time), 120, add=True), "骚扰卡车"),
                (self.calculate_time_str(str(self.now_time), 180, add=True), "骚扰卡车"),
                (self.calculate_time_str(str(self.now_time), 240, add=True), "骚扰卡车")
            ]
            if self.now_target[3] == 4:
                for i in range(len(self.map_process_table)):
                    map_process_table.append((self.map_process_table[i][0], self.map_process_table[i][1] + "D"))
            elif self.now_target[3] == 5:
                for i in range(len(self.map_process_table)):
                    map_process_table.append((self.map_process_table[i][0], self.map_process_table[i][1] + "C"))
            return map_process_table

        def check_func():
            # 拿小地图截图
            EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
            mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]

            result_4 = self.judge_green_label3_in_img(mini_map_pixmap, *_MAIN_TARGET_POINT["4"])
            result_5 = self.judge_green_label3_in_img(mini_map_pixmap, *_MAIN_TARGET_POINT["5"])
            if result_4 and not result_5:
                self.now_target.append(4)
                self.now_time = self.gametime_timer()
                logger.debug(f"【死亡摇篮】检测到目标列表{self.now_target}")
                return True
            elif result_5 and not result_4:
                self.now_target.append(5)
                self.now_time = self.gametime_timer()
                logger.debug(f"【死亡摇篮】检测到目标列表{self.now_target}")
                return True

            logger.debug(f"【死亡摇篮】检测结果result_4:{result_4} result_5:{result_5}")
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