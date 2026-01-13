from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class YingJiuKuangGong(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.CHUAN = [2,3,4,5,6,7,8,9]
        self.CHUAN_now = []
        self.WAVE_number = 0

        # 5秒一次检测
        self.timer.setInterval(5000)

    def _init_states(self):
        _RED_POINTS = {
            "A" : (0.08, 0.08),
            "B" : (0.53, 0.08),
            "C" : (0.95, 0.6),
        }

        _FEI_CHUAN_POINTS = {
            "2" : (0.25, 0.4),
            "3" : (0.39, 0.52),
            "4" : (0.28, 0.17),
            "5" : (0.55, 0.78),
            "6" : (0.565, 0.52),
            "7" : (0.7, 0.25),
            "8" : (0.42, 0.17),
            "9" : (0.92, 0.3),
        }

        _WHITE_POINTS = {
            "2" : (0.7, 0.1),
            "3" : (0.5, 0.88),
            "4" : (0.05, 0.4),
            "5" : (0.95, 0.47),
            "6" : (0.9, 0.1),
            "7" : (0.95, 0.68),
            "8" : (0.95, 0.64),
            "9" : (0.65, 0.88),
        }


        self.map_process_table = [
            ("0:30", "圈养神器：两个基地中间有个草占2*2，下边两格的下方2*2就是神器位置"),
            ("6:30", "红点A/C"),
            ("13:00", "红点B"),
            ("17:30", "红点C/A"),
            ("23:00", "红点A/C"),
            ("26:30", "红点C/A"),
            ("28:00", "红点A/C"),
            ("32:00", "红点A/C"),

            ("9:00", "奖励"),
            ("15:00", "奖励"),

            ("3:45", "恐慌发射"),
            ("12:00", "恐慌发射"),
            ("16:30", "恐慌发射"),
            ("23:30", "恐慌发射"),
            ("27:00", "恐慌发射"),
            ("29:00", "恐慌发射"),
            ("29:00", "恐慌发射"),

            ("8:00", "白点"),
            ("15:12", "白点"),
            ("19:18", "白点"),
            ("26:00", "白点"),
        ]

        self.point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("B", *_RED_POINTS["B"]),
            ("C", *_RED_POINTS["C"]),
            # ("2", *_WHITE_POINTS["2"]),
            # ("3", *_WHITE_POINTS["3"]),
            # ("4", *_WHITE_POINTS["4"]),
            # ("5", *_WHITE_POINTS["5"]),
            # ("6", *_WHITE_POINTS["6"]),
            # ("7", *_WHITE_POINTS["7"]),
            # ("8", *_WHITE_POINTS["8"]),
            # ("9", *_WHITE_POINTS["9"]),
        ]

        def check_func():
            return True

        self.add_sequential_state(
            map_process_table=self.map_process_table,
            point_on_minimap=self.point_on_minimap,
            check_func=check_func
        )

        # # =====================================
        # # 公用任务处理表和图标表还有判断函数
        # # =====================================
        # def map_process_table_1to4():
        #     for i in [-4, -3, -2, -1]:
        #         self.map_process_table[i] = (self.map_process_table[i][0], f"白点{', '.join(map(str, self.CHUAN_now))}")
        #     return self.map_process_table

        # # def point_on_minimap_1to4():
        # #     return self.point_on_minimap + [(f"{self.CHUAN_now}", *_WHITE_POINTS[str(self.CHUAN_now)])]

        # def check_func_1to4():
        #     # 拿小地图截图
        #     EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
        #     mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]

        #     # 统计有几个地方判断出来了，只有一个地方判断出来了，才是正确的
        #     # 如果判断出来了2个或者以上，那么就是错误的
        #     self.CHUAN_now = []
        #     for idx in self.CHUAN:
        #         if self.judge_green_label_in_img(mini_map_pixmap, *_FEI_CHUAN_POINTS[str(idx)]):
        #             self.CHUAN_now.append(idx)
        #             if len(self.CHUAN_now) >= 2:
        #                 logger.debug(f"【营救矿工】第一种判断出来了{self.CHUAN_now}")
        #                 # 使用第二种图像判断
        #                 self.CHUAN_now = []
        #                 for idx in self.CHUAN:
        #                     if self.judge_green_label2_in_img(mini_map_pixmap, *_FEI_CHUAN_POINTS[str(idx)]):
        #                         self.CHUAN_now.append(idx)
        #                         if len(self.CHUAN_now) >= 2:
        #                             logger.debug(f"【营救矿工】第二种判断出来了{self.CHUAN_now}")
        #                             return False
        #                 break

        #     if len(self.CHUAN_now) == 1:
        #         # 去掉判断出来的那个
        #         self.CHUAN.remove(self.CHUAN_now[0])
        #         self.WAVE_number += 1
        #         logger.debug(f"【营救矿工】第{self.WAVE_number}艘发射飞船是{self.CHUAN_now}")
        #         return True

        #     return False

        # # =====================================
        # # 第一艘发射飞船
        # # =====================================

        # self.add_sequential_state(
        #     map_process_table=map_process_table_1to4,
        #     check_func=check_func_1to4
        # )

        # # =====================================
        # # 第二艘发射飞船
        # # =====================================

        # self.add_sequential_state(
        #     map_process_table=map_process_table_1to4,
        #     check_func=check_func_1to4
        # )

        # # =====================================
        # # 第三艘发射飞船
        # # =====================================

        # self.add_sequential_state(
        #     map_process_table=map_process_table_1to4,
        #     check_func=check_func_1to4
        # )

        # # =====================================
        # # 第四艘发射飞船
        # # =====================================

        # self.add_sequential_state(
        #     map_process_table=map_process_table_1to4,
        #     check_func=check_func_1to4
        # )

        # # =====================================
        # # 第五艘发射飞船
        # # =====================================

        # self.add_sequential_state(
        #     map_process_table=map_process_table_1to4,
        #     check_func=check_func_1to4
        # )


        # # =====================================
        # # 第六和第七艘发射飞船
        # # =====================================
        # def map_process_table_6to7():
        #     for i in range(4):
        #         self.map_process_table[i] = (self.map_process_table[i][0], f"白点{', '.join(map(str, self.CHUAN_now))}")
        #     return self.map_process_table

        # # def point_on_minimap_6to7():
        # #     return self.point_on_minimap + [(f"{self.CHUAN_now}", *_WHITE_POINTS[str(self.CHUAN_now)])]

        # def check_func_6to7():
        #     # 拿小地图截图
        #     EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
        #     mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]

        #     # 统计有几个地方判断出来了，必须是两个地方判断出来了，才是正确的
        #     # 如果判断出来了3个或者以上，那么就是错误的
        #     for idx in self.CHUAN:
        #         if self.judge_green_label_in_img(mini_map_pixmap, *_FEI_CHUAN_POINTS[str(idx)]):
        #             self.CHUAN_now.append(idx)
        #             if len(self.CHUAN_now) >= 3:
        #                 logger.debug(f"【营救矿工】第一种判断出来了{self.CHUAN_now}")
        #                 # 使用第二种图像判断
        #                 self.CHUAN_now = []
        #                 for idx in self.CHUAN:
        #                     if self.judge_green_label2_in_img(mini_map_pixmap, *_FEI_CHUAN_POINTS[str(idx)]):
        #                         self.CHUAN_now.append(idx)
        #                         if len(self.CHUAN_now) >= 3:
        #                             logger.debug(f"【营救矿工】第二种判断出来了{self.CHUAN_now}")
        #                             return False
        #     if len(self.CHUAN_now) == 2:
        #         self.WAVE_number += 1
        #         logger.debug(f"【营救矿工】第6和7艘发射飞船是{self.CHUAN_now}")
        #         return True
        #     return False

        # self.add_sequential_state(
        #     map_process_table=map_process_table_6to7,
        #     check_func=check_func_6to7
        # )


        # =====================================
        # 最终状态等待外部状态机切换
        # =====================================

        self.add_sequential_state(
            check_func= lambda: False
        )