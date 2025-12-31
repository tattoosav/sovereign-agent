@echo off
REM =============================================================================
REM Sovereign Agent - Windows Session Manager
REM =============================================================================
REM Use this on Windows without Git Bash
REM Requires: ssh, scp (included in Windows 10+)
REM =============================================================================

setlocal enabledelayedexpansion

REM Configuration - EDIT THESE or set as environment variables
if "%LAMBDA_IP%"=="" set LAMBDA_IP=
if "%LAMBDA_USER%"=="" set LAMBDA_USER=ubuntu
if "%LAMBDA_KEY%"=="" set LAMBDA_KEY=%USERPROFILE%\.ssh\lambda_key

set REMOTE_AGENT_DIR=~/sovereign-agent
set WEB_PORT=8000
set SCRIPT_DIR=%~dp0
set LOCAL_AGENT_DIR=%SCRIPT_DIR%..

REM Colors (Windows 10+)
set GREEN=[92m
set YELLOW=[93m
set RED=[91m
set CYAN=[96m
set NC=[0m

if "%1"=="" goto usage
if "%1"=="start" goto start_session
if "%1"=="stop" goto stop_session
if "%1"=="status" goto show_status
if "%1"=="push" goto push_files
if "%1"=="pull" goto pull_files
if "%1"=="shell" goto open_shell
if "%1"=="logs" goto show_logs
goto usage

:check_config
if "%LAMBDA_IP%"=="" (
    echo %RED%[ERROR]%NC% LAMBDA_IP not set!
    echo.
    echo Set it with:
    echo   set LAMBDA_IP=your-instance-ip
    echo.
    exit /b 1
)
if not exist "%LAMBDA_KEY%" (
    echo %RED%[ERROR]%NC% SSH key not found: %LAMBDA_KEY%
    exit /b 1
)
exit /b 0

:start_session
call :check_config
if errorlevel 1 exit /b 1

echo.
echo ==============================================
echo   Starting Sovereign Agent Session
echo ==============================================
echo.

echo %CYAN%[STEP]%NC% 1/5 Testing connection...
ssh -i "%LAMBDA_KEY%" -o StrictHostKeyChecking=no -o ConnectTimeout=10 %LAMBDA_USER%@%LAMBDA_IP% "echo Connected"
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Cannot connect to VPS
    exit /b 1
)

echo %CYAN%[STEP]%NC% 2/5 Syncing code...
call :push_code_only

echo %CYAN%[STEP]%NC% 3/5 Syncing patterns...
call :push_patterns_only

echo %CYAN%[STEP]%NC% 4/5 Starting Ollama...
ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP% "pgrep ollama || (ollama serve &>/dev/null &)"
timeout /t 2 /nobreak >nul

echo %CYAN%[STEP]%NC% 5/5 Starting agent...
ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP% "cd %REMOTE_AGENT_DIR% && pkill -f 'python.*src.web' 2>/dev/null; sleep 1; nohup uv run python -m src.web --host 0.0.0.0 --port %WEB_PORT% > agent.log 2>&1 &"

timeout /t 3 /nobreak >nul

echo.
echo ==============================================
echo   SESSION READY!
echo ==============================================
echo.
echo   Web UI: %GREEN%http://%LAMBDA_IP%:%WEB_PORT%%NC%
echo   SSH:    ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP%
echo.
echo   Commands:
echo     %~nx0 status  - Check status
echo     %~nx0 logs    - View logs
echo     %~nx0 stop    - Stop session
echo.
goto :eof

:stop_session
call :check_config
if errorlevel 1 exit /b 1

echo.
echo ==============================================
echo   Stopping Sovereign Agent Session
echo ==============================================
echo.

echo %CYAN%[STEP]%NC% 1/3 Stopping agent...
ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP% "pkill -f 'python.*src.web' 2>/dev/null || true"

echo %CYAN%[STEP]%NC% 2/3 Pulling code...
call :pull_code_only

echo %CYAN%[STEP]%NC% 3/3 Pulling patterns...
call :pull_patterns_only

echo.
echo ==============================================
echo   SESSION ENDED
echo ==============================================
echo.
echo   %YELLOW%Don't forget to stop your Lambda instance!%NC%
echo.
goto :eof

:show_status
call :check_config
if errorlevel 1 exit /b 1

echo.
echo Session Status
echo ==============
echo.

ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP% "echo 'Connection: OK' && echo && echo 'GPU:' && nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv && echo && echo 'Agent:' && (pgrep -f 'python.*src.web' && echo 'Running at http://%LAMBDA_IP%:%WEB_PORT%' || echo 'Not running') && echo && echo 'Models:' && ollama list"
goto :eof

:show_logs
call :check_config
if errorlevel 1 exit /b 1
echo %GREEN%[INFO]%NC% Streaming logs (Ctrl+C to exit)...
ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP% "tail -f %REMOTE_AGENT_DIR%/agent.log"
goto :eof

:open_shell
call :check_config
if errorlevel 1 exit /b 1
ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP%
goto :eof

:push_files
call :check_config
if errorlevel 1 exit /b 1
call :push_code_only
call :push_patterns_only
echo %GREEN%[INFO]%NC% All files pushed!
goto :eof

:pull_files
call :check_config
if errorlevel 1 exit /b 1
call :pull_code_only
call :pull_patterns_only
echo %GREEN%[INFO]%NC% All files pulled!
goto :eof

:push_code_only
echo %GREEN%[INFO]%NC% Pushing code...
ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP% "mkdir -p %REMOTE_AGENT_DIR%"
scp -i "%LAMBDA_KEY%" -r "%LOCAL_AGENT_DIR%\src" %LAMBDA_USER%@%LAMBDA_IP%:%REMOTE_AGENT_DIR%/
scp -i "%LAMBDA_KEY%" -r "%LOCAL_AGENT_DIR%\pyproject.toml" %LAMBDA_USER%@%LAMBDA_IP%:%REMOTE_AGENT_DIR%/
scp -i "%LAMBDA_KEY%" -r "%LOCAL_AGENT_DIR%\deploy" %LAMBDA_USER%@%LAMBDA_IP%:%REMOTE_AGENT_DIR%/
exit /b 0

:push_patterns_only
if exist "%LOCAL_AGENT_DIR%\.sovereign" (
    echo %GREEN%[INFO]%NC% Pushing patterns...
    ssh -i "%LAMBDA_KEY%" %LAMBDA_USER%@%LAMBDA_IP% "mkdir -p ~/.sovereign"
    scp -i "%LAMBDA_KEY%" -r "%LOCAL_AGENT_DIR%\.sovereign\patterns" %LAMBDA_USER%@%LAMBDA_IP%:~/.sovereign/ 2>nul
    scp -i "%LAMBDA_KEY%" -r "%LOCAL_AGENT_DIR%\.sovereign\conversations" %LAMBDA_USER%@%LAMBDA_IP%:~/.sovereign/ 2>nul
    scp -i "%LAMBDA_KEY%" -r "%LOCAL_AGENT_DIR%\.sovereign\knowledge" %LAMBDA_USER%@%LAMBDA_IP%:~/.sovereign/ 2>nul
)
exit /b 0

:pull_code_only
echo %GREEN%[INFO]%NC% Pulling code...
scp -i "%LAMBDA_KEY%" -r %LAMBDA_USER%@%LAMBDA_IP%:%REMOTE_AGENT_DIR%/src "%LOCAL_AGENT_DIR%\"
exit /b 0

:pull_patterns_only
echo %GREEN%[INFO]%NC% Pulling patterns...
if not exist "%LOCAL_AGENT_DIR%\.sovereign" mkdir "%LOCAL_AGENT_DIR%\.sovereign"
scp -i "%LAMBDA_KEY%" -r %LAMBDA_USER%@%LAMBDA_IP%:~/.sovereign/patterns "%LOCAL_AGENT_DIR%\.sovereign\" 2>nul
scp -i "%LAMBDA_KEY%" -r %LAMBDA_USER%@%LAMBDA_IP%:~/.sovereign/conversations "%LOCAL_AGENT_DIR%\.sovereign\" 2>nul
scp -i "%LAMBDA_KEY%" -r %LAMBDA_USER%@%LAMBDA_IP%:~/.sovereign/knowledge "%LOCAL_AGENT_DIR%\.sovereign\" 2>nul
exit /b 0

:usage
echo.
echo Sovereign Agent - Windows Session Manager
echo ==========================================
echo.
echo Usage: %~nx0 ^<command^>
echo.
echo Commands:
echo   start   Start agent session
echo   stop    Stop and sync back
echo   status  Show session status
echo   push    Push code + patterns to VPS
echo   pull    Pull code + patterns from VPS
echo   shell   SSH into VPS
echo   logs    Stream agent logs
echo.
echo Configuration:
echo   set LAMBDA_IP=your-instance-ip
echo   set LAMBDA_KEY=path-to-ssh-key
echo.
echo Example:
echo   set LAMBDA_IP=123.45.67.89
echo   %~nx0 start
echo.
goto :eof
