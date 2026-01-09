from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class ShengGeZhiLian(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        self.type = None
        self.find_time = None
        self.all_map_process_table = None

        super().__init__(parent)

    def _init_states(self):

        # 混合体1 混合体2 前节点 混合体3 后节点|混合体4
        # 9分钟前的先补上
        _RED_POINTS = {
            "A" : (0.27, 0.71),
            "B" : (0.82, 0.48),
            "C" : (0.9, 0.78),
        }

        _HU_WEI_DUI_POINTS = {
            "1" : (0.33, 0.69),
            "2" : (0.74, 0.57),
            "3" : (0.9, 0.78),
        }

        _HUN_HE_TI_POINTS = {
            "a" : (0.15, 0.58),
            "b" : (0.63, 0.24),
            "c" : (0.28, 0.72),
            "d" : (0.9, 0.78),
        }

        self.all_map_process_table = [
            ("2:00", "该地图特殊提示：\n\n若红点A/B位置附近没有建筑，则红点位置变为C\n\n护卫队位置（1->2->C）随吉娜拉到达过的最远位置变化\n\n提前触发混合体会将护卫队和红点波次延后两分钟"),

            ("3:00", "\n"),

            # ==============

            ("3:30", "红点A/B"), #2
            ("7:00", "红点B/A"), #3

            ("3:30", "护卫队"), #4
            ("5:00", "护卫队"), #5
            ("7:00", "护卫队"), #6

            ("9:00", "混合体a"),#7

            # ==============

            ("13:00", "红点A/B"), #8

            ("9:00", "护卫队"), #9
            ("13:00", "护卫队"), #10
            ("14:00", "护卫队"), #11

            ("15:00", "混合体b"), #12

            # ==============

            ("18:00", "红点B/A"),#13
            ("22:00", "红点A"),#14
            ("22:00", "红点B"),#15

            ("15:00", "护卫队"), #16
            ("19:00", "护卫队"), #17
            ("20:00", "护卫队"), #18
            ("20:30", "护卫队"), #19
            ("21:30", "护卫队"), #20
            ("22:30", "护卫队"), #21

            ("23:00", "混合体c"),#22

            # ==============

            ("27:30", "红点A"),#23
            ("27:30", "红点B"),#24

            ("23:00", "护卫队"),#25
            ("26:00", "护卫队"),#26
            ("26:30", "护卫队"),#27
            ("27:30", "护卫队"),#28
            ("28:00", "护卫队"),#29
            ("29:00", "护卫队"),#30

            ("30:00", "混合体d"),#31

            # ==============

            ("33:30", "红点A"),#32
            ("33:30", "红点B"),#33

            ("30:00", "护卫队"),#34
            ("33:00", "护卫队"),#35
            ("33:30", "护卫队"),#36
            ("34:00", "护卫队"),#37
            ("35:00", "护卫队"),#38


            # ==============
            ("10:00", "奖励1"),
            ("18:00", "奖励2")

        ]
        point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"]),
            ("C", *_RED_POINTS["C"]),
            ("1", *_HU_WEI_DUI_POINTS["1"]),
            ("2", *_HU_WEI_DUI_POINTS["2"]),
            # ("3", *_HU_WEI_DUI_POINTS["3"])
            ("a", *_HUN_HE_TI_POINTS["a"]),
            ("b", *_HUN_HE_TI_POINTS["b"]),
            ("c", *_HUN_HE_TI_POINTS["c"]),
            # ("d", *_HUN_HE_TI_POINTS["d"]),
        ]

        def check_func():
            return True

        self.add_sequential_state(
            map_process_table=self.all_map_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 判断第一波红点位置
        # =====================================
        def map_process_table_func():
            if self.type != None:
                self.all_map_process_table[2] = ("3:30", "红点" + "A" if self.type == "A" else "B")#2
                self.all_map_process_table[3] = ("7:00", "红点" + "B" if self.type == "A" else "A")#3
                self.all_map_process_table[8] = ("13:00", "红点" + "A" if self.type == "A" else "B")#8
                self.all_map_process_table[13] = ("22:00", "红点" + "B" if self.type == "A" else "B")#13
                return self.all_map_process_table
            else:
                return None
        map_process_table = map_process_table_func
        point_on_minimap = None

        def check_func():
            if "4:00" >= self.gametime_timer() >= "3:30":
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_A = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["A"])
                result_B = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["B"])
                if result_A and not result_B:
                    logger.debug(f"【升格之链】第一波红点来自A")
                    self.type = "A"
                    return True
                elif result_B and not result_A:
                    logger.debug(f"【升格之链】第一波红点来自B")
                    self.type = "B"
                    return True
                logger.debug(f"【升格之链】第一波红点未判断出来A:{result_A} B:{result_B}")
            elif self.gametime_timer() > "4:00":
                logger.debug(f"【升格之链】第一波红点未判断出来，进入下一状态")
                return True
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 判断混合体a出现没，出现了就比较时间
        # =====================================

        def map_process_table_func():
            # 7分钟之前的才需要改
            # ("3:30", "红点A/B"), #2
            # ("7:00", "红点B/A"), #3
            # ("3:30", "护卫队"), #4
            # ("5:00", "护卫队"), #5
            # ("7:00", "护卫队"), #6
            if self.find_time is None or self.find_time >= "7:00":
                return None
            else:
                for idx in [2,3,4,5,6]:
                    self.all_map_process_table[idx] = (self.calculate_time_str(self.all_map_process_table[idx][0], seconds = 120, add=True), self.all_map_process_table[idx][1] + "(延后)") if self.find_time < self.all_map_process_table[idx][0] else self.all_map_process_table[idx]
                return self.all_map_process_table
        map_process_table = map_process_table_func

        def check_func():
            if "9:00" > self.gametime_timer():
                # 拿小地图截图，判断混合体a出现了没
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_a = self.judge_red_label_in_img(mini_map_pixmap, *_HUN_HE_TI_POINTS["a"])
                if result_a:
                    logger.debug(f"【升格之链】提前发现混合体a")
                    self.all_map_process_table[7] = ("59:59", "混合体a")
                    self.find_time = self.gametime_timer()
                    return True
                logger.debug(f"【升格之链】未提前发现混合体a")
            elif self.gametime_timer() >= "9:00":
                    self.find_time = None
                    return True
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            check_func=check_func
        )

        # =====================================
        # 判断混合体b出现没，出现了就比较时间
        # =====================================

        def map_process_table_func():
            # 14分钟之前的才需要改
            # ("13:00", "红点A/B"), #8

            # ("9:00", "护卫队"), #9
            # ("13:00", "护卫队"), #10
            # ("14:00", "护卫队"), #11
            if self.find_time is None or self.find_time >= "14:00":
                return None
            else:
                for idx in [8,9,10,11] + [2,3,4,5,6]:
                    self.all_map_process_table[idx] = (self.calculate_time_str(self.all_map_process_table[idx][0], seconds = 120, add=True), self.all_map_process_table[idx][1] + "(延后)") if self.find_time < self.all_map_process_table[idx][0] else self.all_map_process_table[idx]
                return self.all_map_process_table
        map_process_table = map_process_table_func

        def check_func():
            if "15:00" > self.gametime_timer():
                # 拿小地图截图，判断混合体b出现了没
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_b = self.judge_red_label_in_img(mini_map_pixmap, *_HUN_HE_TI_POINTS["b"])
                if result_b:
                    logger.debug(f"【升格之链】提前发现混合体b")
                    self.all_map_process_table[12] = ("59:59", "混合体b")
                    self.find_time = self.gametime_timer()
                    return True
                logger.debug(f"【升格之链】未提前发现混合体b")
            elif self.gametime_timer() >= "15:00":
                    self.find_time = None
                    return True
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            check_func=check_func
        )

        # =====================================
        # 判断混合体c出现没，出现了就比较时间
        # =====================================

        def map_process_table_func():
            # ("18:00", "红点B/A"),#13
            # ("22:00", "红点A"),#14
            # ("22:00", "红点B"),#15

            # ("15:00", "护卫队"), #16
            # ("19:00", "护卫队"), #17
            # ("20:00", "护卫队"), #18
            # ("20:30", "护卫队"), #19
            # ("21:30", "护卫队"), #20
            # ("22:30", "护卫队"), #21
            if self.find_time is None or self.find_time >= "22:30":
                return None
            else:
                for idx in [13,14,15,16,17,18,19,20,21] + [8,9,10,11] + [2,3,4,5,6]:
                    self.all_map_process_table[idx] = (self.calculate_time_str(self.all_map_process_table[idx][0], seconds = 120, add=True), self.all_map_process_table[idx][1] + "(延后)") if self.find_time < self.all_map_process_table[idx][0] else self.all_map_process_table[idx]
                return self.all_map_process_table
        map_process_table = map_process_table_func

        def check_func():
            if "23:00" > self.gametime_timer():
                # 拿小地图截图，判断混合体c出现了没
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_c = self.judge_red_label_in_img(mini_map_pixmap, *_HUN_HE_TI_POINTS["c"])
                if result_c:
                    logger.debug(f"【升格之链】提前发现混合体c")
                    self.find_time = self.gametime_timer()
                    self.all_map_process_table[22] = ("59:59", "混合体c")
                    return True
                logger.debug(f"【升格之链】未提前发现混合体c")
            elif self.gametime_timer() >= "23:00":
                    self.find_time = None
                    return True
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            check_func=check_func
        )

        # =====================================
        # 判断混合体d出现没，出现了就比较时间
        # =====================================

        def map_process_table_func():
            # ("27:30", "红点A"),#23
            # ("27:30", "红点B"),#24

            # ("23:00", "护卫队"),#25
            # ("26:00", "护卫队"),#26
            # ("26:30", "护卫队"),#27
            # ("27:30", "护卫队"),#28
            # ("28:00", "护卫队"),#29
            # ("29:00", "护卫队"),#30
            if self.find_time is None or self.find_time >= "29:00":
                return None
            else:
                for idx in [23,24,25,26,27,28,29,30]:
                    self.all_map_process_table[idx] = (self.calculate_time_str(self.all_map_process_table[idx][0], seconds = 120, add=True), self.all_map_process_table[idx][1] + "(延后)") if self.find_time < self.all_map_process_table[idx][0] else self.all_map_process_table[idx]
                return self.all_map_process_table
        map_process_table = map_process_table_func

        def check_func():
            if "30:00" > self.gametime_timer():
                # 拿小地图截图，判断混合体d出现了没
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_d = self.judge_red_label_in_img(mini_map_pixmap, *_HUN_HE_TI_POINTS["d"])
                if result_d:
                    logger.debug(f"【升格之链】提前发现混合体d")
                    self.all_map_process_table[31] = ("59:59", "混合体d")
                    self.find_time = self.gametime_timer()
                    return True
                logger.debug(f"【升格之链】未提前发现混合体d")
            elif self.gametime_timer() >= "30:00":
                    self.find_time = None
                    return True
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            check_func=check_func
        )

        # =====================================
        # 最终状态等待外部状态机切换
        # =====================================

        self.add_sequential_state(
            check_func= lambda: False
        )