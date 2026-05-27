# HealthReminder

Windows 桌面托盘健康提醒工具。

## 当前版本

v2.0.0

更新记录见 `CHANGELOG.md`。

## 功能

- 每天 8:30 弹出上班提醒。
- 每天 17:00 弹出下班提醒。
- 工作时间内按自定义间隔弹出久坐提醒，每次随机显示一条趣味起身理由。
- 工作时间内按自定义间隔弹出喝水提醒，每次随机显示一条口语化趣味喝水理由。
- 喝水提醒会额外弹出确认窗口，可选择“我喝了”或稍后提醒。
- 新增主界面，可以查看运行状态、修改上班/下班时间、修改提醒间隔。
- 新增运行日志，记录启动、提醒、重置计时、开会模式等状态。
- 新增开机自启开关，可以在主界面里打开或关闭。
- 新增开会模式，开启后会暂停久坐和喝水提醒。
- 开会模式支持自动进入 Windows 屏保。
- 系统托盘右键菜单支持打开主界面、切换开会模式、重置计时、查看版本和退出程序。
- 通知使用 Windows 桌面通知，并带托盘气泡兜底。
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
health_reminder\notifier.py    Windows 通知
health_reminder\windows_integration.py 开机自启和屏保
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
