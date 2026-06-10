@echo off
REM ============================================================
REM  Sovereign Agent + CRM - one-click offline installer
REM  Double-click this file on the OFFLINE target machine.
REM  It self-elevates and runs install_airgap.ps1 from the USB.
REM  No internet is required or used.
REM ============================================================

REM Self-elevate to Administrator if needed.
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ============================================================
echo   Sovereign Agent + CRM - Air-Gapped Install
echo ============================================================
echo.
echo This will install the offline AI + CRM and set it to start
echo automatically at boot. It takes several minutes (copying the
echo AI models is the slow part). Do not close this window.
echo.
pause

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0install_airgap.ps1"
set RESULT=%errorLevel%

echo.
if %RESULT% neq 0 (
    echo ============================================================
    echo   INSTALL DID NOT COMPLETE. See the log path shown above.
    echo ============================================================
) else (
    echo ============================================================
    echo   INSTALL COMPLETE.
    echo   Open the CRM at:  http://127.0.0.1:8000/crm
    echo   See docs\AIRGAP_RUNBOOK.md for daily use.
    echo ============================================================
)
echo.
pause
