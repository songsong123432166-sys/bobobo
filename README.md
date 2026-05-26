# HealthReminder

Windows 桌面托盘健康提醒工具。

## 当前版本

v1.4.1

更新记录见 `CHANGELOG.md`。

## 功能

- 每天 8:30 弹出上班提醒。
- 每天 17:00 弹出下班提醒。
- 工作时间内每隔 45 分钟弹出久坐提醒，每次随机显示一条趣味起身理由。
- 工作时间内每隔 60 分钟弹出喝水提醒，每次随机显示一条口语化趣味喝水理由。
- 喝水提醒会额外弹出左下角确认窗口，可选择“我喝了”或“10分钟后提醒”。
- 系统托盘右键菜单支持重置久坐计时、重置喝水计时、查看版本和退出程序。
- 启动时自动加入当前 Windows 用户的开机启动项。

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 运行

```powershell
python health_tray_reminder.py
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
