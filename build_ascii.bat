@echo off
setlocal
cd /d "%~dp0"

echo Current folder:
echo %CD%
echo.

if not exist "%CD%\health_tray_reminder.py" (
    echo ERROR: health_tray_reminder.py was not found in this folder.
    pause
    exit /b 1
)

if not exist "%CD%\health_reminder\app.py" (
    echo ERROR: health_reminder package was not found in this folder.
    pause
    exit /b 1
)

set PYTHON_CMD=python
python --version >nul 2>nul
if errorlevel 1 (
    set PYTHON_CMD=py -3
)

echo Python command:
echo %PYTHON_CMD%
echo.

%PYTHON_CMD% --version
if errorlevel 1 (
    echo.
    echo ERROR: Python was not found from this batch file.
    echo Please run the commands in the VS Code terminal instead.
    pause
    exit /b 1
)

echo.
echo Python location:
%PYTHON_CMD% -c "import sys; print(sys.executable)"

echo.
echo Checking pip...
%PYTHON_CMD% -m pip --version
if errorlevel 1 (
    echo.
    echo pip was not found. Trying to enable pip...
    %PYTHON_CMD% -m ensurepip --upgrade
)

echo.
echo Installing packages...
%PYTHON_CMD% -m pip install pystray schedule pillow pyinstaller pycaw opencv-python
if errorlevel 1 (
    echo.
    echo Package installation failed. Checking whether packages already exist...
    %PYTHON_CMD% -c "import pystray, schedule, PIL, PyInstaller, pycaw, cv2; print('Packages already installed.')"
    if errorlevel 1 (
        echo.
        echo ERROR: Packages are still missing.
        echo Please copy all text above and send it to me.
        pause
        exit /b 1
    )
)

echo.
echo Building app...
%PYTHON_CMD% -m PyInstaller -y --noconsole --name HealthReminder --distpath "%CD%\dist" --workpath "%CD%\build" --specpath "%CD%" "%CD%\health_tray_reminder.py"
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    echo Please copy all text above and send it to me.
    pause
    exit /b 1
)

if not exist "%CD%\dist\HealthReminder\HealthReminder.exe" (
    echo.
    echo ERROR: Build command finished, but HealthReminder.exe was not created.
    echo Please copy all text in this window and send it to me.
    pause
    exit /b 1
)

echo.
echo SUCCESS.
echo Open this folder:
echo %CD%\dist\HealthReminder
echo.
pause
