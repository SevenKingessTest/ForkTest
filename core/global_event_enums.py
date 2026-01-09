from enum import Enum

# ==========================================
# 全局事件
# ==========================================
class GlobalEvents(Enum):
    # 游戏时间截图组件的相关信号
    REQ_GAMETIME_SCREENSHOT = "游戏时间截图_请求"
    RES_GAMETIME_SCREENSHOT = "游戏时间截图_响应"

    # 任务时间截图组件的相关信号
    REQ_TASKTIME_SCREENSHOT = "任务时间截图_请求"
    RES_TASKTIME_SCREENSHOT = "任务时间截图_响应"

    # 地图名称截图组件的相关信号
    REQ_MAPNAME_SCREENSHOT = "地图名称截图_请求"
    RES_MAPNAME_SCREENSHOT = "地图名称截图_响应"

    # 聊天栏截图组件的相关信号
    REQ_CHAT_SCREENSHOT = "聊天栏截图_请求"
    RES_CHAT_SCREENSHOT = "聊天栏截图_响应"

    # 小地图组件的相关信号
    REQ_MINIMAP_SCREENSHOT = "小地图截图_请求"
    RES_MINIMAP_SCREENSHOT = "小地图截图_响应"
    REQ_MINIMAP_REPAINT = "小地图重绘制_请求"

    # 流程表组件的相关信号
    REQ_BASEPROCESSTABLE_UPDATE = "基础流程表内容更新_请求"
    REQ_MAPPROCESSTABLE_UPDATE = "地图流程表内容更新_请求"
    REQ_TASKPROCESSTABLE_UPDATE = "任务流程表内容更新_请求"

    # 游戏时间计时器的相关信号
    REQ_GAMETIME_TIMER_GETTIME = "游戏时间计时器_时间获取_请求"
    RES_GAMETIME_TIMER_GETTIME = "游戏时间计时器_时间获取_响应"
    REQ_GAMETIME_TIMER_START = "游戏时间计时器_开启_请求"
    RES_GAMETIME_TIMER_START = "游戏时间计时器_开启_响应"
    REQ_GAMETIME_TIMER_STOP = "游戏时间计时器_关闭_请求"
    RES_GAMETIME_TIMER_STOP = "游戏时间计时器_关闭_响应"
    RES_GAMETIME_TIMER_CALIBRATE = "游戏时间计时器_校准_响应"

    # 任务时间计时器的相关信号
    REQ_TASKTIME_TIMER_STATUS = "任务时间计时器_状态查询_请求"
    REQ_TASKTIME_TIMER_GETTIME = "任务时间计时器_时间获取_请求"
    RES_TASKTIME_TIMER_GETTIME = "任务时间计时器_时间获取_响应"
    REQ_TASKTIME_TIMER_START = "任务时间计时器_开启_请求"
    RES_TASKTIME_TIMER_START = "任务时间计时器_开启_响应"
    RES_TASKTIME_TIMER_PAUSE = "任务时间计时器_暂停_响应"
    RES_TASKTIME_TIMER_RESUME = "任务时间计时器_恢复_响应"
    RES_TASKTIME_TIMER_STOP = "任务时间计时器_关闭_响应"
    RES_TASKTIME_TIMER_CALIBRATE = "任务时间计时器_校准_响应"

    # 合作模式相关信号
    REQ_SET_HEZUO_MODE = "合作模式_设置_请求"
    RES_SET_HEZUO_MODE = "合作模式_设置_响应"
