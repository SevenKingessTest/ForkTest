from PyQt5.QtCore import QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot
from state_machine.map_state_machine.base import BaseSequentialStateMachine
from core.event_bus import EventBusInstance
from core.global_event_enums import GlobalEvents

import logging
logger = logging.getLogger(__name__)

class JingWangXingDong(BaseSequentialStateMachine):
    def __init__(self, parent=None):
        self.type = None
        self._tower_2_type = None
        self._tower_3_type = None
        self._tower_4_type = None

        self._next_start_task_time_timer = None

        super().__init__(parent)

    def _init_states(self):
        # 存一下所有点的标记
        _RED_POINTS = {
            "A" : (0.28, 0.24),
            "B" : (0.67, 0.18),
            "C" : (0.72, 0.42)
        }

        _TOWER_2 = {
            "a" : (0.54, 0.15),
            "b" : (0.66, 0.16),
            "c" : (0.595, 0.35)
        }
        _TOWER_2_RED_POINTS = {
            "1" : (0.52, 0.19),
            "2" : (0.56, 0.125),
            "3" : (0.62, 0.125),
            "4" : (0.81, 0.31),
            "5" : (0.775, 0.35)
        }

        _TOWER_3 = {
            "a" : (0.45, 0.55),
            "b" : (0.55, 0.4),
            "c" : (0.72, 0.45),
            "d" : (0.65, 0.6),
            "e" : (0.47, 0.71)
        }
        _TOWER_3_RED_POINTS = {
            "1" : (0.49, 0.72),
            "2" : (0.68, 0.57),
            "3" : (0.57, 0.75),
            "4" : (0.5, 0.8),
        }

        _TOWER_4 = {
            "a" : (0.55, 0.74),
            "b" : (0.75, 0.63),
            "c" : (0.83, 0.49),
            "d" : (0.88, 0.81),
            "e" : (0.66, 0.82)
        }
        _TOWER_4_RED_POINTS = {
            "1" : (0.62, 0.79),
            "2" : (0.87, 0.45),
            "3" : (0.93, 0.48),
            "4" : (0.89, 0.84),
        }

        # =====================================
        # 初始化状态，提交开局结果
        # 状态0
        # =====================================
        map_process_table = [
            ("0:30", "圈养神器：第一个传送门顶着凹槽，传送门下边左两格的下方2*2围起来"),
            ("3:36", "红点A/C")
        ]
        task_process_table = None
        point_on_minimap = [
            ("A", *_RED_POINTS["A"]),
            ("C", *_RED_POINTS["C"])
        ]

        def check_func():
            # 如果没拿到游戏时间闭包就一直拿
            if self.gametime_timer is None:
                status = self.get_gametime_timer()
                return status
            return True

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )


        # =====================================
        # 检验第一波红点位置
        # 状态1
        # =====================================
        map_process_table = []
        task_process_table = None
        point_on_minimap = []
        def check_func():
            if self.gametime_timer() >= "4:05":
                logger.debug(f"【净网行动】第一波红点未检测出来，进入下一状态")
                EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                return True
            if self.gametime_timer() >= "3:36":
                # 拿小地图截图
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_A = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["A"])
                result_C = self.judge_red_in_img(mini_map_pixmap, *_RED_POINTS["C"])
                if result_A and not result_C:
                    # 说明红点来自A，进入第下一个状态
                    # 设置红点波形为A，来自NGA
                    self.type = "A"
                    logger.debug(f"【净网行动】第一波红点来自A，已确定波型，进入下一状态")
                    EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                    return True
                elif not result_A and result_C:
                    # 说明红点来自C，进入第下一个状态
                    # 设置红点波形为B，来自NGA
                    self.type = "B"
                    logger.debug(f"【净网行动】第一波红点来自C，已确定波型，进入下一状态")
                    EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                    return True

                logger.debug(f"【净网行动】第一波红点未判断出来【A：{result_A}】【C：{result_C}】")
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 处理终端1
        # 等待拿到任务计时器
        # 状态2
        # =====================================
        map_process_table = []
        task_process_table = [
            ("2:25", "骚扰波次1/2/3（2:25）"),
            ("2:00", "骚扰波次1/2/3（2:00）"),
            ("1:35", "骚扰波次1/2/3（1:35）"),
            ("1:10", "骚扰波次1/2/3（1:10）"),
            ("1:00", "压制塔a/b（1:00）"),
            ("0:20", "骚扰波次1/2/3（0:20）"),
        ]
        point_on_minimap = [
            ("1", 0.12, 0.25),
            ("2", 0.41, 0.26),
            ("3", 0.41, 0.42),
            ("a", 0.29, 0.315),
            ("b", 0.38, 0.42),
        ]
        def check_func():
            # 如果没拿到任务时间闭包就一直触发
            if self.tasktime_timer() is None:
                status = self.get_tasktime_timer()
                if status:
                    logger.debug(f"【净网行动】任务计时器闭包已经拿到")
                    return True
                return False
            logger.debug(f"【净网行动】任务计时器闭包已经拿到")
            return True

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 处理终端1
        # 等待任务计时器结束
        # 状态3
        # =====================================
        if self.type == "A":
            map_process_table = lambda: [
                (self.calculate_time_str(str(self.gametime_timer()), 80,add=True),"红点C\n（奥罗娜走进触发区域时触发）"),
                (self.calculate_time_str(str(self.gametime_timer()), 90,add=True),"奖励任务1\n（奥罗娜走进触发区域时触发）")
            ]
            point_on_minimap = [
                ("C", *_RED_POINTS["C"]),
            ]
        elif self.type == "B":
            map_process_table = lambda: [
                (self.calculate_time_str(str(self.gametime_timer()), 80,add=True),"红点A\n（奥罗娜走进触发区域时触发）"),
                (self.calculate_time_str(str(self.gametime_timer()), 90,add=True),"奖励任务1\n（奥罗娜走进触发区域时触发）")
            ]
            point_on_minimap = [
                ("A", *_RED_POINTS["A"]),
            ]
        else:
            map_process_table = lambda: [
                (self.calculate_time_str(str(self.gametime_timer()), 80,add=True),"红点C\n（奥罗娜走进触发区域时触发）"),
                (self.calculate_time_str(str(self.gametime_timer()), 79,add=True),"奖励任务1\n（奥罗娜走进触发区域时触发）")
            ]
            point_on_minimap = [
                    ("A", *_RED_POINTS["A"]),
                    ("C", *_RED_POINTS["C"]),
            ]
        task_process_table = None

        def check_func():
            if self.tasktime_timer() is None or self.tasktime_timer() <= "0:0":
                logger.debug(f"【净网行动】任务计时器已结束")
                # 设置下一个任务计时器开始时间(1分钟后)
                self._next_start_task_time_timer = self.calculate_time_str(str(self.gametime_timer()), 60,add=True)
                return True
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 暂停一分钟然后发布任务计时器开始事件
        # 状态4
        # =====================================
        def check_func():
            if self._next_start_task_time_timer is None or self._next_start_task_time_timer <= str(self.gametime_timer()):
                EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                logger.debug(f"【净网行动】启动终端2的任务计时器")
                return True
            return False

        self.add_sequential_state(
            check_func=check_func
        )


        # =====================================
        # 处理终端2
        # 等待拿到任务计时器，然后发布骚扰任务
        # 状态5
        # =====================================
        map_process_table = []
        task_process_table = [
            ("2:30", "骚扰波次1~5（2:30）"),
            ("2:15", "骚扰波次1~5（2:15）"),
            ("1:55", "压制塔a/b（1:55）"),
            ("1:40", "骚扰波次1~5（1:40）"),
            ("1:20", "骚扰波次1~5（1:20）"),
            ("1:20", "压制塔b/c（1:20）"),
            ("1:00", "骚扰波次1~5（1:00）"),
            ("0:41", "骚扰波次1~5（0:41）"),
            ("0:20", "骚扰波次1~5（0:20）"),
        ]
        point_on_minimap = [
            ("1", *_TOWER_2_RED_POINTS["1"]),
            ("2", *_TOWER_2_RED_POINTS["2"]),
            ("3", *_TOWER_2_RED_POINTS["3"]),
            ("4", *_TOWER_2_RED_POINTS["4"]),
            ("5", *_TOWER_2_RED_POINTS["5"]),
            ("a", *_TOWER_2["a"]),
            ("b", *_TOWER_2["b"]),
            ("c", *_TOWER_2["c"]),
        ]

        def check_func():
            # 如果没拿到任务时间闭包就一直触发
            if self.tasktime_timer() is None:
                status = self.get_tasktime_timer()
                if status:
                    logger.debug(f"【净网行动】任务计时器闭包已经拿到")
                    return True
                return False
            logger.debug(f"【净网行动】任务计时器闭包已经拿到")
            return True

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 处理终端2
        # 判断压制塔波形
        # 状态6
        # =====================================

        def task_process_table_func():
            result = None
            if self._tower_2_type == "A":
                result = [
                    ("2:30", "骚扰波次1~5（2:30）"),
                    ("2:15", "骚扰波次1~5（2:15）"),
                    ("1:55", "压制塔b（1:55）"),
                    ("1:40", "骚扰波次1~5（1:40）"),
                    ("1:20", "骚扰波次1~5（1:20）"),
                    ("1:20", "压制塔c（1:20）"),
                    ("1:00", "骚扰波次1~5（1:00）"),
                    ("0:41", "骚扰波次1~5（0:41）"),
                    ("0:20", "骚扰波次1~5（0:20）"),
                ]
            elif self._tower_2_type == "B":
                result = [
                ("2:30", "骚扰波次1~5（2:30）"),
                ("2:15", "骚扰波次1~5（2:15）"),
                ("1:55", "压制塔a（1:55）"),
                ("1:40", "骚扰波次1~5（1:40）"),
                ("1:20", "骚扰波次1~5（1:20）"),
                ("1:20", "压制塔b（1:20）"),
                ("1:00", "骚扰波次1~5（1:00）"),
                ("0:41", "骚扰波次1~5（0:41）"),
                ("0:20", "骚扰波次1~5（0:20）"),
                ]
            return result
        task_process_table = task_process_table_func

        def point_on_minimap_func():
            result = None
            if self._tower_2_type == "A":
                result = [
                    ("1", *_TOWER_2_RED_POINTS["1"]),
                    ("2", *_TOWER_2_RED_POINTS["2"]),
                    ("3", *_TOWER_2_RED_POINTS["3"]),
                    ("4", *_TOWER_2_RED_POINTS["4"]),
                    ("5", *_TOWER_2_RED_POINTS["5"]),
                    ("b", *_TOWER_2["b"])
                    ("c", *_TOWER_2["c"]),
                ]
            elif self._tower_2_type == "B":
                result = [
                    ("1", *_TOWER_2_RED_POINTS["1"]),
                    ("2", *_TOWER_2_RED_POINTS["2"]),
                    ("3", *_TOWER_2_RED_POINTS["3"]),
                    ("4", *_TOWER_2_RED_POINTS["4"]),
                    ("5", *_TOWER_2_RED_POINTS["5"]),
                    ("a", *_TOWER_2["a"]),
                    ("b", *_TOWER_2["b"]),
                ]
            return result
        point_on_minimap = point_on_minimap_func

        def check_func():
            if self.tasktime_timer() < "1:40":
                logger.debug(f"【净网行动】第二波压制塔波形未判断出来，直接进入下一状态")
                return True
            if "1:40" <= self.tasktime_timer() <= "1:55":
                # 拿小地图截图
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                # mini_map_pixmap.save("mini_map.png")
                result_a = self.judge_red_label_in_img(mini_map_pixmap, *_TOWER_2["a"])
                result_b = self.judge_red_label_in_img(mini_map_pixmap, *_TOWER_2["b"])
                if result_b and not result_a:
                    # 说明压制塔来自b
                    # 设置_tower_2_type为A，来自NGA
                    self._tower_2_type = "A"
                    logger.debug(f"【净网行动】压制塔来自b，已确定波型A，进入下一状态")
                    return True
                elif not result_b and result_a:
                    # 说明压制塔来自a
                    # 设置_tower_2_type为B，来自NGA
                    self._tower_2_type = "B"
                    logger.debug(f"【净网行动】压制塔来自a，已确定波型B，进入下一状态")
                    return True

                logger.debug(f"【净网行动】第二波压制塔波形未判断出来【a：{result_a}】【b：{result_b}】")

            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 处理终端2
        # 等待任务计时器结束
        # 状态7
        # =====================================

        map_process_table = lambda: [
            (self.calculate_time_str(str(self.gametime_timer()), 80,add=True),"红点B\n（奥罗娜走进触发区域时触发）")
        ]
        point_on_minimap = [
            ("B", *_RED_POINTS["B"]),
        ]
        task_process_table = []

        def check_func():
            if self.tasktime_timer() is None or self.tasktime_timer() <= "0:0":
                logger.debug(f"【净网行动】处理终端2任务计时器已结束")
                # 设置下一个任务计时器时间为1分钟后
                self._next_start_task_time_timer = self.calculate_time_str(str(self.gametime_timer()), 60,add=True)
                return True
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 暂停一分钟然后发布任务计时器开始事件
        # 状态8
        # =====================================
        def check_func():
            if self._next_start_task_time_timer is None or self._next_start_task_time_timer <= str(self.gametime_timer()):
                logger.debug(f"【净网行动】启动终端3的任务计时器")
                EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                return True
            return False

        self.add_sequential_state(
            check_func=check_func
        )

        # =====================================
        # 处理终端3
        # 等待拿到任务计时器，然后发布骚扰任务
        # 状态9
        # =====================================
        map_process_table = []
        task_process_table = [
            ("2:25", "骚扰波次1~4（2:25）"),
            ("2:20", "压制塔a/e（2:20）"),
            ("1:40", "骚扰波次1~4（1:40）"),
            ("1:15", "压制塔d/c[卫队]（1:15）"),
            ("0:55", "骚扰波次1~4（0:55）"),
            ("0:33", "压制塔b[卫队]/a（0:33）"),
            ("0:15", "骚扰波次1~4（0:15）")
        ]
        point_on_minimap = [
            ("1", *_TOWER_3_RED_POINTS["1"]),
            ("2", *_TOWER_3_RED_POINTS["2"]),
            ("3", *_TOWER_3_RED_POINTS["3"]),
            ("4", *_TOWER_3_RED_POINTS["4"]),
            ("a", *_TOWER_3["a"]),
            ("b", *_TOWER_3["b"]),
            ("c", *_TOWER_3["c"]),
            ("d", *_TOWER_3["d"]),
            ("e", *_TOWER_3["e"]),
        ]

        def check_func():
            # 如果没拿到任务时间闭包就一直触发
            if self.tasktime_timer() is None:
                status = self.get_tasktime_timer()
                if status:
                    logger.debug(f"【净网行动】净化终端3任务计时器闭包已经拿到")
                    return True
                return False
            logger.debug(f"【净网行动】净化终端3任务计时器闭包已经拿到")
            return True

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )


        # =====================================
        # 处理终端3
        # 判断压制塔波形
        # 状态10
        # =====================================

        def task_process_table_func():
            result = None
            if self._tower_3_type == "A":
                result = [
                    ("2:25", "骚扰波次1~4（2:25）"),
                    ("2:20", "压制塔a（2:20）"),
                    ("1:40", "骚扰波次1~4（1:40）"),
                    ("1:15", "压制塔d（1:15）"),
                    ("0:55", "骚扰波次1~4（0:55）"),
                    ("0:33", "压制塔b（0:33）"),
                    ("0:28", "压制塔b左偏下方卫队（0:28）"),
                    ("0:15", "骚扰波次1~4（0:15）")
                ]
            elif self._tower_3_type == "B":
                result = [
                    ("2:25", "骚扰波次1~4（2:25）"),
                    ("2:20", "压制塔e（2:20）"),
                    ("1:40", "骚扰波次1~4（1:40）"),
                    ("1:15", "压制塔c（1:15）"),
                    ("1:10", "压制塔c左上方卫队（1:10）"),
                    ("0:55", "骚扰波次1~4（0:55）"),
                    ("0:33", "压制塔a（0:33）"),
                    ("0:15", "骚扰波次1~4（0:15）")
                ]
            return result
        task_process_table = task_process_table_func

        def point_on_minimap_func():
            result = None
            if self._tower_2_type == "A":
                result = [
                    ("1", *_TOWER_3_RED_POINTS["1"]),
                    ("2", *_TOWER_3_RED_POINTS["2"]),
                    ("3", *_TOWER_3_RED_POINTS["3"]),
                    ("4", *_TOWER_3_RED_POINTS["4"]),
                    ("a", *_TOWER_3["a"]),
                    ("b", *_TOWER_3["b"]),
                    ("d", *_TOWER_3["d"]),
                ]
            elif self._tower_2_type == "B":
                result = [
                    ("1", *_TOWER_3_RED_POINTS["1"]),
                    ("2", *_TOWER_3_RED_POINTS["2"]),
                    ("3", *_TOWER_3_RED_POINTS["3"]),
                    ("4", *_TOWER_3_RED_POINTS["4"]),
                    ("a", *_TOWER_3["a"]),
                    ("c", *_TOWER_3["c"]),
                    ("e", *_TOWER_3["e"]),
                ]
            return result
        point_on_minimap = point_on_minimap_func

        def check_func():
            if self.tasktime_timer() < "1:40":
                logger.debug(f"【净网行动】第三波压制塔波形未判断出来，直接进入下一状态")
                return True
            if "1:40" <= self.tasktime_timer() <= "2:20":
                # 拿小地图截图
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                # mini_map_pixmap.save("mini_map.png")
                result_a = self.judge_red_label_in_img(mini_map_pixmap, *_TOWER_3["a"])
                result_e = self.judge_red_label_in_img(mini_map_pixmap, *_TOWER_3["e"])
                if result_a and not result_e:
                    # 说明压制塔来自a
                    # 设置_tower_3_type为A，来自NGA
                    self._tower_3_type = "A"
                    logger.debug(f"【净网行动】压制塔来自a，已确定波型A，进入下一状态")
                    return True
                elif not result_a and result_e:
                    # 说明压制塔来自e
                    # 设置_tower_3_type为B，来自NGA
                    self._tower_3_type = "B"
                    logger.debug(f"【净网行动】压制塔来自e，已确定波型B，进入下一状态")
                    return True

                logger.debug(f"【净网行动】第三波压制塔波形未判断出来【a：{result_a}】【e：{result_e}】")

            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 处理终端3
        # 等待任务计时器结束
        # 状态11
        # =====================================

        map_process_table = lambda: [
            (self.calculate_time_str(str(self.gametime_timer()), 60,add=True),"奖励任务2\n（奥罗娜走进触发区域时触发）")
        ]
        point_on_minimap = []
        task_process_table = []

        def check_func():
            if self.tasktime_timer() is None or self.tasktime_timer() <= "0:0":
                logger.debug(f"【净网行动】处理终端3任务计时器已结束")
                # 设置_next_start_task_time_timer为下一分钟
                self._next_start_task_time_timer = self.calculate_time_str(str(self.gametime_timer()), 60,add=True)
                return True
            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 暂停一分钟然后发布任务计时器开始事件
        # 状态12
        # =====================================
        def check_func():
            if self._next_start_task_time_timer is None or self._next_start_task_time_timer <= str(self.gametime_timer()):
                logger.debug(f"【净网行动】启动终端4的任务计时器")
                EventBusInstance.publish(GlobalEvents.REQ_TASKTIME_TIMER_START)
                return True
            return False

        self.add_sequential_state(
            check_func=check_func
        )


        # =====================================
        # 处理终端4
        # 等待拿到任务计时器，然后发布骚扰任务
        # 状态13
        # =====================================
        map_process_table = []
        task_process_table = [
            ("2:30", "骚扰波次1~4（2:30）"),
            ("2:10", "压制塔d/c（2:10）"),
            ("1:55", "骚扰波次1~4（1:55）"),
            ("1:35", "压制塔a[卫队]/e[卫队]（1:35）"),
            ("1:22", "骚扰波次1~4（1:22）"),
            ("0:55", "压制塔b[卫队]（0:55）"),
            ("0:55", "压制塔e[卫队]/d[卫队]（0:55）"),
            ("0:30", "骚扰波次1~4（0:30）")
        ]
        point_on_minimap = [
            ("1", *_TOWER_4_RED_POINTS["1"]),
            ("2", *_TOWER_4_RED_POINTS["2"]),
            ("3", *_TOWER_4_RED_POINTS["3"]),
            ("4", *_TOWER_4_RED_POINTS["4"]),
            ("a", *_TOWER_4["a"]),
            ("b", *_TOWER_4["b"]),
            ("c", *_TOWER_4["c"]),
            ("d", *_TOWER_4["d"]),
            ("e", *_TOWER_4["e"]),
        ]

        def check_func():
            # 如果没拿到任务时间闭包就一直触发
            if self.tasktime_timer() is None:
                status = self.get_tasktime_timer()
                if status:
                    logger.debug(f"【净网行动】处理终端4任务计时器闭包已经拿到")
                    return True
                return False
            logger.debug(f"【净网行动】处理终端4任务计时器闭包已经拿到")
            return True

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )


        # =====================================
        # 处理终端4
        # 判断压制塔波形
        # 状态11
        # =====================================

        def task_process_table_func():
            result = None
            if self._tower_4_type == "A":
                result = [
                    ("2:30", "骚扰波次1~4（2:30）"),
                    ("2:10", "压制塔d（2:10）"),
                    ("1:55", "骚扰波次1~4（1:55）"),
                    ("1:35", "压制塔a（1:35）"),
                    ("1:30", "压制塔a上方卫队（1:30）"),
                    ("1:22", "骚扰波次1~4（1:22）"),
                    ("0:55", "压制塔b（0:55）"),
                    ("0:50", "压制塔b上方卫队（0:50）"),
                    ("0:55", "压制塔e（0:55）"),
                    ("0:50", "压制塔e左上方卫队（0:50）"),
                    ("0:30", "骚扰波次1~4（0:30）")
                ]
            elif self._tower_4_type == "B":
                result = [
                    ("2:30", "骚扰波次1~4（2:30）"),
                    ("2:10", "压制塔c（2:10）"),
                    ("1:55", "骚扰波次1~4（1:55）"),
                    ("1:35", "压制塔e（1:35）"),
                    ("1:30", "压制塔e左上方卫队（1:30）"),
                    ("1:22", "骚扰波次1~4（1:22）"),
                    ("0:55", "压制塔b（0:55）"),
                    ("0:50", "压制塔b上方卫队（0:50）"),
                    ("0:55", "压制塔d（0:55）"),
                    ("0:50", "压制塔d下方卫队（0:50）"),
                    ("0:30", "骚扰波次1~4（0:30）")
                ]
            return result
        task_process_table = task_process_table_func

        def point_on_minimap_func():
            result = None
            if self._tower_4_type == "A":
                result = [
                    ("1", *_TOWER_4_RED_POINTS["1"]),
                    ("2", *_TOWER_4_RED_POINTS["2"]),
                    ("3", *_TOWER_4_RED_POINTS["3"]),
                    ("4", *_TOWER_4_RED_POINTS["4"]),
                    ("a", *_TOWER_4["a"]),
                    ("b", *_TOWER_4["b"]),
                    ("e", *_TOWER_4["e"]),
                    ("d", *_TOWER_4["d"]),
                ]
            elif self._tower_4_type == "B":
                result = [
                    ("1", *_TOWER_4_RED_POINTS["1"]),
                    ("2", *_TOWER_4_RED_POINTS["2"]),
                    ("3", *_TOWER_4_RED_POINTS["3"]),
                    ("4", *_TOWER_4_RED_POINTS["4"]),
                    ("b", *_TOWER_4["b"]),
                    ("c", *_TOWER_4["c"]),
                    ("d", *_TOWER_4["d"]),
                    ("e", *_TOWER_4["e"]),
                ]
            return result
        point_on_minimap = point_on_minimap_func

        def check_func():
            if self.tasktime_timer() < "1:55":
                logger.debug(f"【净网行动】第四波压制塔波形未判断出来，直接进入下一状态")
                return True
            if "1:55" <= self.tasktime_timer() <= "2:10":
                # 拿小地图截图
                EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_SCREENSHOT)
                mini_map_pixmap = EventBusInstance.shared_data[GlobalEvents.RES_MINIMAP_SCREENSHOT]
                result_d = self.judge_red_label_in_img(mini_map_pixmap, *_TOWER_4["d"])
                result_c = self.judge_red_label_in_img(mini_map_pixmap, *_TOWER_4["c"])
                if result_d and not result_c:
                    # 说明压制塔来自d
                    # 设置_tower_4_type为A，来自NGA
                    self._tower_4_type = "A"
                    logger.debug(f"【净网行动】压制塔来自d，已确定波型A，进入下一状态")
                    return True
                elif not result_d and result_c:
                    # 说明压制塔来自c
                    # 设置_tower_4_type为B，来自NGA
                    self._tower_4_type = "B"
                    logger.debug(f"【净网行动】压制塔来自c，已确定波型B，进入下一状态")
                    return True

                logger.debug(f"【净网行动】第四波压制塔波形未判断出来【d：{result_d}】【c：{result_c}】")

            return False

        self.add_sequential_state(
            map_process_table=map_process_table,
            task_process_table=task_process_table,
            point_on_minimap=point_on_minimap,
            check_func=check_func
        )

        # =====================================
        # 处理终端4
        # 等待任务计时器结束
        # 状态12
        # =====================================

        map_process_table = None
        point_on_minimap = None
        task_process_table = None

        def check_func():
            if self.tasktime_timer() is None or self.tasktime_timer() <= "0:0":
                logger.debug(f"【净网行动】处理终端4任务计时器已结束")
                return True
            return False

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