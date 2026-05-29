# Health Tray Reminder

Windows background tray app for health reminders: standing, drinking water, work status, idle/away detection, camera presence checks, and daily health summaries.

## Run from source

```powershell
python -m pip install -r requirements.txt
python -m health_reminder
```

After creating the project virtual environment, you can also run:

```powershell
.\run_local.ps1
```

Optional dependencies degrade safely:

- If `opencv-python` is unavailable, camera detection is skipped.
- If `pycaw` is unavailable, media playback detection returns false.
- If `%APPDATA%` cannot be written, the app falls back to a temp data directory.

## Data directory

Default:

```text
%APPDATA%\HealthTrayReminder
```

Common files:

- `config.json`
- `run.log`
- `health_score.json`
- `away_reason.json`

## Build exe

```powershell
python -m pip install -r requirements.txt
pyinstaller health_reminder.spec
```

The spec includes `health_reminder/assets`, `health_reminder/models`, and Tcl/Tk runtime files when they can be found in the active Python environment.
