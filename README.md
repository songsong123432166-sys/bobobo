# HealthReminder

Windows 桌面托盘健康提醒工具。

## 当前版本

v2.7.0

更新记录见 `CHANGELOG.md`。

## 功能

- 每天 8:30 随机弹出一条上班招呼。
- 每天 17:00 随机弹出一条下班招呼。
- 工作时间内按自定义间隔弹出久坐提醒，每次随机显示一条趣味起身理由。
- 工作时间内按自定义间隔弹出喝水提醒，每次随机显示一条口语化趣味喝水理由。
- 久坐和喝水提醒时间相近时会自动合并为一个弹窗，默认合并窗口为 5 分钟。
- 合并提醒弹出后，相关提醒会从弹出时间重新计算下一次提醒。
- 新增勿扰时间段，可在主界面自定义开始时间和结束时间。
- 喝水提醒会额外弹出确认窗口，可选择“我喝了”或稍后提醒。
- 新增今日健康分，记录喝水、起身、连续久坐、开会模式等状态。
- 喝水和起身完成后会自动加分，并在弹窗里反馈今日健康分。
- 新增电脑状态检测，长时间无鼠标键盘输入时会暂停提醒。
- 常见视频播放器或会议软件正在出声时会视为使用中，不会误判离开。
- 新增可选摄像头检测模块，默认关闭；开启后每 30 分钟本地判断一次电脑前是否有人。
- 新增主界面，可以查看运行状态、修改上班/下班时间、修改提醒间隔。
- 主界面改为苹果健康摘要页风格，增加头像、健康分圆环、圆角卡片、电脑使用时长和简洁动效。
- 托盘图标改为健康爱心图标。
- 新增运行日志，记录启动、提醒、重置计时、开会模式等状态。
- 新增开机自启开关，可以在主界面里打开或关闭。
- 新增开会模式，开启后会暂停久坐和喝水提醒。
- 系统托盘右键菜单支持打开主界面、切换开会模式、重置计时、查看版本和退出程序。
- 提醒统一使用程序自带的右下角滑入弹窗，不再使用 Windows 系统通知。
- 配置使用 JSON 文件保存，运行日志使用 TXT 文件保存。

## 配置和日志位置

程序会自动创建下面的目录：

```text
%APPDATA%\HealthTrayReminder
```

常用文件：

```text
config.json
run.log
```

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 运行

```powershell
python health_tray_reminder.py
```

## 项目结构

```text
health_tray_reminder.py        程序入口
health_reminder\app.py         主流程和提醒逻辑
health_reminder\ui.py          主界面和喝水确认窗口
health_reminder\config_store.py 配置读写
health_reminder\event_log.py   运行日志
health_reminder\health_score.py 今日健康分
health_reminder\activity.py     电脑状态检测
health_reminder\camera_presence.py 摄像头存在检测
health_reminder\windows_integration.py 开机自启和 Windows 状态检测
health_reminder\tray_icon.py   托盘图标
```

## 打包

推荐使用项目里的批处理脚本：

```text
build_ascii.bat
```

也可以手动运行：

```powershell
python -m PyInstaller --noconsole --name HealthReminder --distpath ".\dist" --workpath ".\build" --specpath "." ".\health_tray_reminder.py"
```

打包完成后，程序位于：

```text
dist\HealthReminder\HealthReminder.exe
```

发送给别人时，请发送整个文件夹：

```text
dist\HealthReminder
```
