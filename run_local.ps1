$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  python -m venv (Join-Path $root ".venv")
  $python = Join-Path $root ".venv\Scripts\python.exe"
}
& $python -m health_reminder
