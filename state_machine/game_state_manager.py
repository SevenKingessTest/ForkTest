from PyQt5.QtCore import (QObject, QStateMachine, QState, QSignalTransition, pyqtSignal, pyqtSlot, QTimer)
from PyQt5.QtGui import QPixmap, QImage
from core.global_event_enums import GlobalEvents
from core.event_bus import EventBusInstance
import logging
logger = logging.getLogger(__name__)

import easyocr
import numpy as np

from state_machine.map_state_machine.jing_wang_xing_dong import JingWangXingDong
from state_machine.map_state_machine.ke_ha_lie_hen import KeHaLieHen
from state_machine.map_state_machine.tian_jie_feng_suo import TianJieFengSuo
from state_machine.map_state_machine.xu_kong_jiang_lin import XuKongJiangLin
from state_machine.map_state_machine.xu_kong_si_lie import XuKongSiLie
from state_machine.map_state_machine.yan_mie_kuai_che import YanMieKuaiChe
from state_machine.map_state_machine.si_wang_yao_lan import SiWangYaoLan
from state_machine.map_state_machine.ji_hui_miao_mang import JiHuiMiaoMang
from state_machine.map_state_machine.wang_zhe_zhi_ye import WangZheZhiYe
from state_machine.map_state_machine.hei_an_sha_xing import HeiAnShaXing
from state_machine.map_state_machine.ju_tie_cheng_bing import JuTieChengBing
from state_machine.map_state_machine.wang_ri_shen_miao import WangRiShenMiao
from state_machine.map_state_machine.ying_jiu_kuang_gong import YingJiuKuangGong
from state_machine.map_state_machine.rong_huo_wei_ji import RongHuoWeiJi
from state_machine.map_state_machine.sheng_ge_zhi_lian import ShengGeZhiLian



ALL_MAP_NAMES = [
    '克哈裂痕',
    '湮灭快车',
    '虚空撕裂',
    '虚空降临',
    '往日神庙',
    '天界封锁',
    '升格之链',
    '熔火危机',
    '机会渺茫',
    '营救矿工',
    '亡者之夜',
    '黑暗杀星',
    '净网行动',
    '聚铁成兵',
    '死亡摇篮'
]

ALLOW_MAP_NAMES = "".join(ALL_MAP_NAMES)

class OCR:
    def __init__(self):
        self.reader = easyocr.Reader(['ch_sim'], gpu=True)

    def recognize_time(self, img):
        img = self.pixmap_to_numpy(img)
        # OCR识别文本（仅保留数字、:、.）
        result = self.reader.readtext(img, detail=0, allowlist="0123456789:")
        sep = ':'
        minute = None
        second = None
        # 筛选并处理时间格式
        for text in result:
            text = text.strip().replace(" ", "")
            if sep in text:
                # 按分隔符分割为分钟和秒两部分
                time_parts = text.split(sep)
                # 确保分割后仅包含两部分
                if len(time_parts) == 2:
                    m_part, s_part = time_parts
                    try:
                        minute = int(m_part)
                        second = int(s_part)
                        # 秒数需小于60，保证时间有效性
                        if second <= 59 and minute <= 59:
                            break
                    except (ValueError, TypeError):
                        continue
            elif len(text) == 3 or len(text) == 4:
                minute = int(text[:-2])
                second = int(text[-2:])
                if second > 59:
                    second = None
                if minute > 59:
                    minute = None
        # 若成功提取分钟和秒，转换为总秒数返回
        if minute is not None and second is not None:
            total_seconds = minute * 60 + second
            logger.debug(f"识别到有效时间：{minute}分{second}秒，总秒数{total_seconds:.3f}")
            return total_seconds
        # 未识别到有效时间格式
        return None
    def recognize_map_name(self, img):
        img = self.pixmap_to_numpy(img)
        result = self.reader.readtext(img, detail=0, allowlist=ALLOW_MAP_NAMES)
        if len(result) > 0:
            return str(result[0])
        else:
            return None

    def recognize_chatbox(self, img):
        img = self.pixmap_to_numpy(img)
        result = self.reader.readtext(img, detail=0)
        # 有信息就是True
        if len(result) > 0:
            return True
        else:
            return False

    def pixmap_to_numpy(self, pixmap: QPixmap) -> np.ndarray:
        h,w = pixmap.height(),pixmap.width()
        buffer = QImage(pixmap).constBits()
        buffer.setsize(h*w*4)
        arr = np.frombuffer(buffer, dtype=np.uint8).reshape((h,w,4))

        return arr

class GameStateManager(QObject):
    # 自定义信号
    sig_valid_map_detected = pyqtSignal()
    sig_time_detected = pyqtSignal()
    sig_time_lost_timeout = pyqtSignal()

    sig_hezuo_mode_true = pyqtSignal()
    sig_hezuo_mode_false = pyqtSignal()

    def __init__(self, parent=None, hezuo_mode=True):
        super().__init__(parent)

        self.outer_state_machine = QStateMachine(self)
        self.ocr = OCR()
        self.map_name = None

        # 合作模式
        self.hezuo_mode = hezuo_mode
        # 订阅信号合作模式切换
        EventBusInstance.subscribe(GlobalEvents.REQ_SET_HEZUO_MODE, self.on_set_hezuo_mode)
        # 订阅信号游戏时间计时器关闭
        EventBusInstance.subscribe(GlobalEvents.RES_GAMETIME_TIMER_STOP, self.on_gametime_timer_stopped)

        # 合作模式状态
        self.state_game_out = QState(self.outer_state_machine)
        self.state_loading = QState(self.outer_state_machine)
        self.state_in_game = QState(self.outer_state_machine)
        # 非合作模式状态
        self.state_notin_hezuo_game_out = QState(self.outer_state_machine)
        self.state_notin_hezuo_game_in = QState(self.outer_state_machine)

        self.outer_state_machine.setInitialState(self.state_game_out)
        self._setup_state_transitions()
        self._setup_state_behaviors()  # 统一初始化状态行为

        self.timer = QTimer(self)
        self.timer.setInterval(1000)

        # 内部状态机，先占位
        self.inner_map_state_machine = None

        # 启动状态机
        self.outer_state_machine.start()

    def on_set_hezuo_mode(self, hezuo_mode: bool):
        self.hezuo_mode = hezuo_mode
        # EventBusInstance.publish(GlobalEvents.RES_SET_HEZUO_MODE, hezuo_mode)
        if self.hezuo_mode:
            self.sig_hezuo_mode_true.emit()
        else:
            self.sig_hezuo_mode_false.emit()

    def on_gametime_timer_stopped(self, event_data=None):
        """游戏时间计时器关闭时的处理"""
        self.sig_time_lost_timeout.emit()

    def _setup_state_transitions(self):
        """设置状态转换规则（保持不变）"""
        # 游戏外 -> 加载中
        # 检测到有效地图时（sig_valid_map_detected）切换状态
        trans1 = QSignalTransition(self.sig_valid_map_detected)
        trans1.setTargetState(self.state_loading)
        self.state_game_out.addTransition(trans1)

        # 加载中 -> 游戏内
        # 检测到有效时间时（sig_time_detected）切换状态
        trans2 = QSignalTransition(self.sig_time_detected)
        trans2.setTargetState(self.state_in_game)
        self.state_loading.addTransition(trans2)

        # 游戏内 -> 游戏外
        # 时间丢失超时（sig_time_lost_timeout）切换状态
        trans3 = QSignalTransition(self.sig_time_lost_timeout)
        trans3.setTargetState(self.state_game_out)
        self.state_in_game.addTransition(trans3)

        # 三种状态 -> 非合作模式-游戏外
        # 合作模式关闭时（sig_hezuo_mode_false）切换状态
        trans4 = QSignalTransition(self.sig_hezuo_mode_false)
        trans4.setTargetState(self.state_notin_hezuo_game_out)
        self.state_game_out.addTransition(trans4)
        self.state_loading.addTransition(trans4)
        self.state_in_game.addTransition(trans4)

        # 非合作模式-游戏外 -> 非合作模式-游戏内
        # 检测到有效时间时（sig_time_detected）切换状态
        trans6 = QSignalTransition(self.sig_time_detected)
        trans6.setTargetState(self.state_notin_hezuo_game_in)
        self.state_notin_hezuo_game_out.addTransition(trans6)

        # 非合作模式-游戏内 -> 非合作模式-游戏外
        # 时间丢失超时（sig_time_lost_timeout）切换状态
        trans7 = QSignalTransition(self.sig_time_lost_timeout)
        trans7.setTargetState(self.state_notin_hezuo_game_out)
        self.state_notin_hezuo_game_in.addTransition(trans7)

        # 非合作模式-游戏外 -> 游戏外
        # 合作模式开启时（sig_hezuo_mode_true）切换状态
        trans5 = QSignalTransition(self.sig_hezuo_mode_true)
        trans5.setTargetState(self.state_game_out)
        self.state_notin_hezuo_game_out.addTransition(trans5)
        self.state_notin_hezuo_game_in.addTransition(trans5)

    # 设置进入和退出状态行为
    def _setup_state_behaviors(self):
        #==========================
        # 游戏外状态
        #==========================
        @pyqtSlot()
        def on_game_out_entered():
            logger.info("【状态切换】进入：游戏外")
            def func():
                # 请求地图名称截图
                EventBusInstance.publish(GlobalEvents.REQ_MAPNAME_SCREENSHOT)
                screenshot, _ = EventBusInstance.shared_data[GlobalEvents.RES_MAPNAME_SCREENSHOT]
                mapname = self.ocr.recognize_map_name(screenshot)
                if mapname in ALL_MAP_NAMES:
                    # 地图名称识别成功，触发有效地图检测信号
                    logger.info(f"识别到地图名称：{mapname}")
                    self.map_name = mapname
                    self.sig_valid_map_detected.emit()

            self.timer.timeout.connect(func)
            self.timer.start()

        @pyqtSlot()
        def on_game_out_exited():
            self.timer.timeout.disconnect()
            self.timer.stop()
            logger.info("【状态切换】退出：游戏外")

        # 绑定内部槽函数，避免被垃圾回收）
        self.on_game_out_entered = on_game_out_entered
        self.on_game_out_exited = on_game_out_exited
        self.state_game_out.entered.connect(self.on_game_out_entered)
        self.state_game_out.exited.connect(self.on_game_out_exited)

        #==========================
        # 加载中状态
        #==========================
        @pyqtSlot()
        def on_loading_entered():
            logger.info("【状态切换】进入：加载中")
            def func():
                # 请求时间截图
                EventBusInstance.publish(GlobalEvents.REQ_GAMETIME_SCREENSHOT)
                screenshot, _ = EventBusInstance.shared_data[GlobalEvents.RES_GAMETIME_SCREENSHOT]
                time = self.ocr.recognize_time(screenshot)
                if time:
                    # 时间识别成功，触发时间已有效检测信号
                    logger.info(f"识别到时间：{time}")
                    self.sig_time_detected.emit()
                    # 发布计时器开始信号
                    EventBusInstance.publish(GlobalEvents.REQ_GAMETIME_TIMER_START)

            self.timer.timeout.connect(func)
            self.timer.start()

        @pyqtSlot()
        def on_loading_exited():
            self.timer.timeout.disconnect()
            self.timer.stop()
            logger.info("【状态切换】退出：加载中")

        self.on_loading_entered = on_loading_entered
        self.on_loading_exited = on_loading_exited
        self.state_loading.entered.connect(self.on_loading_entered)
        self.state_loading.exited.connect(self.on_loading_exited)


        #==========================
        # 游戏内状态
        #==========================
        @pyqtSlot()
        def on_in_game_entered():
            logger.info(f"【状态切换】进入：游戏内 - 地图：{self.map_name}")
            match self.map_name:
                case "净网行动":
                    self.inner_map_state_machine = JingWangXingDong(self)
                    self.inner_map_state_machine.start()
                case "克哈裂痕":
                    self.inner_map_state_machine = KeHaLieHen(self)
                    self.inner_map_state_machine.start()
                case "湮灭快车":
                    self.inner_map_state_machine = YanMieKuaiChe(self)
                    self.inner_map_state_machine.start()
                case "天界封锁":
                    self.inner_map_state_machine = TianJieFengSuo(self)
                    self.inner_map_state_machine.start()
                case "虚空降临":
                    self.inner_map_state_machine = XuKongJiangLin(self)
                    self.inner_map_state_machine.start()
                case "虚空撕裂":
                    self.inner_map_state_machine = XuKongSiLie(self)
                    self.inner_map_state_machine.start()
                case "升格之链":
                    self.inner_map_state_machine = ShengGeZhiLian(self)
                    self.inner_map_state_machine.start()
                case "熔火危机":
                    self.inner_map_state_machine = RongHuoWeiJi(self)
                    self.inner_map_state_machine.start()
                case "机会渺茫":
                    self.inner_map_state_machine = JiHuiMiaoMang(self)
                    self.inner_map_state_machine.start()
                case "亡者之夜":
                    self.inner_map_state_machine = WangZheZhiYe(self)
                    self.inner_map_state_machine.start()
                case "黑暗杀星":
                    self.inner_map_state_machine = HeiAnShaXing(self)
                    self.inner_map_state_machine.start()
                case "聚铁成兵":
                    self.inner_map_state_machine = JuTieChengBing(self)
                    self.inner_map_state_machine.start()
                case "死亡摇篮":
                    self.inner_map_state_machine = SiWangYaoLan(self)
                    self.inner_map_state_machine.start()
                case "往日神庙":
                    self.inner_map_state_machine = WangRiShenMiao(self)
                    self.inner_map_state_machine.start()
                case "营救矿工":
                    self.inner_map_state_machine = YingJiuKuangGong(self)
                    self.inner_map_state_machine.start()

        @pyqtSlot()
        def on_in_game_exited():
            self.inner_map_state_machine.stop()
            self.inner_map_state_machine = None
            logger.info(f"【状态切换】退出：游戏内 - 地图：{self.map_name}")
            EventBusInstance.publish(GlobalEvents.REQ_MINIMAP_REPAINT, [])

        self.on_in_game_entered = on_in_game_entered
        self.on_in_game_exited = on_in_game_exited
        self.state_in_game.entered.connect(self.on_in_game_entered)
        self.state_in_game.exited.connect(self.on_in_game_exited)

        #==========================
        # 非合作模式-游戏外状态
        #==========================
        @pyqtSlot()
        def on_notin_hezuo_game_out_entered():
            logger.info(f"【状态切换】进入：非合作模式-游戏外")
            def func():
                # 阻塞式请求时间截图
                EventBusInstance.publish(GlobalEvents.REQ_GAMETIME_SCREENSHOT)
                screenshot, _ = EventBusInstance.shared_data[GlobalEvents.RES_GAMETIME_SCREENSHOT]
                time = self.ocr.recognize_time(screenshot)
                if time:
                    # 时间识别成功，触发时间已有效检测信号
                    logger.info(f"识别到时间：{time}")
                    self.sig_time_detected.emit()
                    # 发布计时器开始信号
                    EventBusInstance.publish(GlobalEvents.REQ_GAMETIME_TIMER_START)

            self.timer.timeout.connect(func)
            self.timer.start()

        @pyqtSlot()
        def on_notin_hezuo_game_out_exited():
            self.timer.timeout.disconnect()
            self.timer.stop()
            logger.info(f"【状态切换】退出：非合作模式-游戏外")

        self.on_notin_hezuo_game_out_entered = on_notin_hezuo_game_out_entered
        self.on_notin_hezuo_game_out_exited = on_notin_hezuo_game_out_exited
        self.state_notin_hezuo_game_out.entered.connect(self.on_notin_hezuo_game_out_entered)
        self.state_notin_hezuo_game_out.exited.connect(self.on_notin_hezuo_game_out_exited)

        #==========================
        # 非合作模式-游戏中状态
        #==========================
        @pyqtSlot()
        def on_notin_hezuo_game_in_entered():
            logger.info(f"【状态切换】进入：非合作模式-游戏中")

        @pyqtSlot()
        def on_notin_hezuo_game_in_exited():
            logger.info(f"【状态切换】退出：非合作模式-游戏中")

        self.on_notin_hezuo_game_in_entered = on_notin_hezuo_game_in_entered
        self.on_notin_hezuo_game_in_exited = on_notin_hezuo_game_in_exited
        self.state_notin_hezuo_game_in.entered.connect(self.on_notin_hezuo_game_in_entered)
        self.state_notin_hezuo_game_in.exited.connect(self.on_notin_hezuo_game_in_exited)
