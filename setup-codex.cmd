@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%setup-codex.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Codex setup failed. Review the error above.
)

if /I "%~1"=="--no-pause" exit /b %EXIT_CODE%
echo.
pause
exit /b %EXIT_CODE%
