import os
from pathlib import Path


APP_NAME = "HealthTrayReminder"
APP_DISPLAY_NAME = "健康提醒"
APP_VERSION = "2.0.0"
APP_TITLE = f"{APP_DISPLAY_NAME} v{APP_VERSION}"

DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
CONFIG_FILE = DATA_DIR / "config.json"
LOG_FILE = DATA_DIR / "run.log"

DEFAULT_CONFIG = {
    "work_start": "08:30",
    "work_end": "17:00",
    "sit_interval_minutes": 45,
    "water_interval_minutes": 60,
    "water_snooze_minutes": 10,
    "startup_enabled": True,
    "meeting_mode": False,
    "meeting_auto_screensaver": False,
}

SIT_REMINDERS = [
    "出去拔根小烟，顺便让腿开机",
    "该离开椅子一会儿了，出去透口气",
    "屁股申请解绑椅子，批准一下",
    "站起来晃一圈，别和椅子处太久",
    "出去走两步，假装自己很忙",
    "腿都快忘了自己是腿了，起来用一下",
    "起来活动一下，顺便看看窗外真实世界",
    "出去放个风，让脑子换换气",
    "椅子占用时间过长，建议强制下线",
    "站起来巡逻一圈，检查一下公司空气",
    "出去溜达两步，回来继续装作很专业",
    "身体提示：需要短暂重启一下",
    "该起身了，别把自己焊在工位上",
    "离开屏幕一分钟，让眼睛也下个班",
    "出去站会儿，顺便把灵魂叫回来",
    "腿部系统提示：长期未运行",
    "起来走走，别让椅子以为赢了",
    "出去转一圈，给今天续点状态",
    "站起来活动活动，顺便接杯水也行",
    "工位先放这儿，人出去喘口气",
]

WATER_REMINDERS = [
    "去整口水，别光靠咖啡硬顶",
    "水杯都快凉透了，给它个面子",
    "出去接杯水，顺便摸鱼三十秒",
    "该补点水了，别把自己熬成干电池",
    "喝口水压压班味",
    "少嘬两口咖啡，来点正经水",
    "给身体上点润滑油，喝口水先",
    "水杯在旁边蹲半天了，安排一下",
    "去接杯温水，顺便让眼睛离开屏幕",
    "别等嗓子冒烟了才想起喝水",
    "来一口水，给脑子续个小电",
    "喝水时间到，今天别全靠意志力",
    "去喝口水，假装这是一次高级养生",
    "嘴唇都快发通知了，先喝点水",
    "给肾哥一点工作材料，来杯水",
    "水杯不是摆设，拿起来走个流程",
    "喝点水，别让咖啡因一个人打全场",
    "去接水，顺便离开工位喘口气",
    "整两口温水，状态可能就回来了",
    "喝水小任务刷新了，点一下完成",
]
