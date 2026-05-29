# Architecture

The app is split into five layers so tray callbacks, Tk widgets, Windows APIs, and persistence do not depend on each other directly.

## Layers

- `health_reminder.core`
  - AppData path resolution, JSON storage, configuration, event logging, daily health metrics, and score calculation.
  - This layer must not import Tkinter, pystray, OpenCV, or Windows UI APIs.

- `health_reminder.platform`
  - Adapters for host capabilities: Windows idle time, registry autostart, pycaw media detection, OpenCV camera presence, tray icon creation.
  - Every adapter degrades safely when the dependency or host capability is unavailable.

- `health_reminder.services`
  - Background business workflows and state machines.
  - Reminder timing, merge-window logic, do-not-disturb rules, work reminders, idle pause, camera absence detection, and UI event publishing live here.

- `health_reminder.ui`
  - Tkinter main window, right-bottom reminder popup, and central away-reason dialog.
  - UI code does not run timers directly and does not call platform detection APIs.

- `health_reminder.app`
  - Composition root.
  - Creates stores, services, queue, tray, and UI; owns startup and shutdown.

## Threading

- Tkinter stays on the main thread.
- `ReminderService` runs on a daemon background thread.
- `TrayController` runs pystray on its own thread.
- Background services and tray callbacks communicate with Tk through a `queue.Queue`.

## Persistence

Default data directory:

```text
%APPDATA%\HealthTrayReminder
```

If AppData is unavailable, the app falls back to the user home directory, then temp, without crashing.

## Packaging

`health_reminder.spec` includes application assets, models, and attempts to collect Tcl/Tk runtime files from the active Python installation.
