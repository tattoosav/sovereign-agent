@echo off
REM Sovereign Agent - one-click air-gapped installer.
REM Double-click this file on the offline target machine. It self-elevates and
REM runs install_airgap.ps1 entirely from the USB bundle (no internet required).

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   Sovereign Agent - Air-Gapped Install
echo ============================================================
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0install_airgap.ps1"

echo.
echo Done. See docs\AIRGAP_RUNBOOK.md for how to submit tasks.
pause
