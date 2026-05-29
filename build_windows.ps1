$ErrorActionPreference = "Stop"
python -m pip install -r requirements.txt
pyinstaller health_reminder.spec
