@echo off
REM =============================================================================
REM Sovereign Agent - RunPod Session Manager (Windows)
REM =============================================================================
setlocal enabledelayedexpansion

REM Colors
set GREEN=[92m
set YELLOW=[93m
set RED=[91m
set CYAN=[96m
set NC=[0m

REM Configuration
if "%RUNPOD_IP%"=="" set RUNPOD_IP=
if "%RUNPOD_PORT%"=="" set RUNPOD_PORT=22
if "%RUNPOD_KEY%"=="" set RUNPOD_KEY=%USERPROFILE%\.ssh\runpod_key

set REMOTE_DIR=/workspace/sovereign-agent
set SCRIPT_DIR=%~dp0
set LOCAL_DIR=%SCRIPT_DIR%..

if "%1"=="" goto usage
if "%1"=="start" goto start_session
if "%1"=="stop" goto stop_session
if "%1"=="status" goto show_status
if "%1"=="push" goto push_files
if "%1"=="pull" goto pull_files
if "%1"=="shell" goto open_shell
if "%1"=="logs" goto show_logs
if "%1"=="setup" goto first_setup
goto usage

:check_config
if "%RUNPOD_IP%"=="" (
    echo %RED%[ERROR]%NC% RUNPOD_IP not set!
    echo.
    echo Get your pod's SSH info from RunPod dashboard:
    echo   1. Click on your running pod
    echo   2. Click "Connect" button
    echo   3. Copy the SSH command details
    echo.
    echo Then set:
    echo   set RUNPOD_IP=your-pod-ip
    echo   set RUNPOD_PORT=your-pod-port
    echo.
    exit /b 1
)
exit /b 0

:ssh_cmd
ssh -i "%RUNPOD_KEY%" -p %RUNPOD_PORT% -o StrictHostKeyChecking=no root@%RUNPOD_IP% %*
exit /b %errorlevel%

:first_setup
call :check_config
if errorlevel 1 exit /b 1

echo.
echo %CYAN%============================================%NC%
echo   First-Time RunPod Setup
echo %CYAN%============================================%NC%
echo.

echo %CYAN%[1/6]%NC% Installing Ollama...
call :ssh_cmd "curl -fsSL https://ollama.com/install.sh | sh"

echo %CYAN%[2/6]%NC% Starting Ollama...
call :ssh_cmd "ollama serve > /dev/null 2>&1 &"
timeout /t 3 /nobreak >nul

echo %CYAN%[3/6]%NC% Pulling vision model (llava)...
call :ssh_cmd "ollama pull llava"

echo %CYAN%[4/6]%NC% Pulling coding models...
call :ssh_cmd "ollama pull qwen2.5-coder:7b"
call :ssh_cmd "ollama pull qwen2.5-coder:14b"

echo %CYAN%[5/6]%NC% Installing Python dependencies...
call :ssh_cmd "pip install uv httpx rich pyyaml chromadb fastapi uvicorn mss"

echo %CYAN%[6/6]%NC% Creating workspace...
call :ssh_cmd "mkdir -p %REMOTE_DIR%"

echo.
echo %GREEN%[SUCCESS]%NC% First-time setup complete!
echo.
echo Next: Run '%~nx0 push' to upload your agent code
echo.
goto :eof

:start_session
call :check_config
if errorlevel 1 exit /b 1

echo.
echo %CYAN%============================================%NC%
echo   Starting Sovereign Agent on RunPod
echo %CYAN%============================================%NC%
echo.

echo %CYAN%[1/5]%NC% Testing connection...
call :ssh_cmd "echo Connected"
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Cannot connect to RunPod
    exit /b 1
)

echo %CYAN%[2/5]%NC% Syncing code...
call :push_code_only

echo %CYAN%[3/5]%NC% Syncing patterns...
call :push_patterns_only

echo %CYAN%[4/5]%NC% Starting Ollama...
call :ssh_cmd "pgrep ollama || (nohup ollama serve > /dev/null 2>&1 &)"
timeout /t 2 /nobreak >nul

echo %CYAN%[5/5]%NC% Starting agent...
call :ssh_cmd "cd %REMOTE_DIR% && pkill -f 'python.*src.web' 2>/dev/null; sleep 1; nohup python -m src.web --host 0.0.0.0 --port 8000 > agent.log 2>&1 &"

timeout /t 3 /nobreak >nul

echo.
echo %GREEN%============================================%NC%
echo   SESSION READY!
echo %GREEN%============================================%NC%
echo.
echo   Web UI: %GREEN%http://%RUNPOD_IP%:8000%NC%
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
echo %CYAN%============================================%NC%
echo   Stopping Session
echo %CYAN%============================================%NC%
echo.

echo %CYAN%[1/3]%NC% Stopping agent...
call :ssh_cmd "pkill -f 'python.*src.web' 2>/dev/null || true"

echo %CYAN%[2/3]%NC% Pulling code changes...
call :pull_code_only

echo %CYAN%[3/3]%NC% Pulling patterns...
call :pull_patterns_only

echo.
echo %GREEN%Session ended. Don't forget to stop your RunPod instance!%NC%
echo.
goto :eof

:show_status
call :check_config
if errorlevel 1 exit /b 1

echo.
echo %CYAN%Session Status%NC%
echo ==============
echo.
call :ssh_cmd "echo 'Connection: OK' && echo && nvidia-smi --query-gpu=name,memory.used,memory.free --format=csv && echo && echo 'Agent:' && (pgrep -f 'python.*src.web' > /dev/null && echo 'Running' || echo 'Not running') && echo && echo 'Ollama:' && (pgrep ollama > /dev/null && echo 'Running' || echo 'Not running') && echo && echo 'Models:' && ollama list 2>/dev/null"
goto :eof

:show_logs
call :check_config
if errorlevel 1 exit /b 1
echo Streaming logs (Ctrl+C to exit)...
call :ssh_cmd "tail -f %REMOTE_DIR%/agent.log"
goto :eof

:open_shell
call :check_config
if errorlevel 1 exit /b 1
ssh -i "%RUNPOD_KEY%" -p %RUNPOD_PORT% -o StrictHostKeyChecking=no root@%RUNPOD_IP%
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
echo Pushing code...
call :ssh_cmd "mkdir -p %REMOTE_DIR%"
scp -i "%RUNPOD_KEY%" -P %RUNPOD_PORT% -r "%LOCAL_DIR%\src" root@%RUNPOD_IP%:%REMOTE_DIR%/
scp -i "%RUNPOD_KEY%" -P %RUNPOD_PORT% "%LOCAL_DIR%\pyproject.toml" root@%RUNPOD_IP%:%REMOTE_DIR%/
exit /b 0

:push_patterns_only
if exist "%LOCAL_DIR%\.sovereign" (
    echo Pushing patterns...
    call :ssh_cmd "mkdir -p ~/.sovereign"
    scp -i "%RUNPOD_KEY%" -P %RUNPOD_PORT% -r "%LOCAL_DIR%\.sovereign\patterns" root@%RUNPOD_IP%:~/.sovereign/ 2>nul
    scp -i "%RUNPOD_KEY%" -P %RUNPOD_PORT% -r "%LOCAL_DIR%\.sovereign\knowledge" root@%RUNPOD_IP%:~/.sovereign/ 2>nul
)
exit /b 0

:pull_code_only
echo Pulling code...
scp -i "%RUNPOD_KEY%" -P %RUNPOD_PORT% -r root@%RUNPOD_IP%:%REMOTE_DIR%/src "%LOCAL_DIR%\"
exit /b 0

:pull_patterns_only
echo Pulling patterns...
if not exist "%LOCAL_DIR%\.sovereign" mkdir "%LOCAL_DIR%\.sovereign"
scp -i "%RUNPOD_KEY%" -P %RUNPOD_PORT% -r root@%RUNPOD_IP%:~/.sovereign/patterns "%LOCAL_DIR%\.sovereign\" 2>nul
scp -i "%RUNPOD_KEY%" -P %RUNPOD_PORT% -r root@%RUNPOD_IP%:~/.sovereign/knowledge "%LOCAL_DIR%\.sovereign\" 2>nul
exit /b 0

:usage
echo.
echo %CYAN%Sovereign Agent - RunPod Session Manager%NC%
echo =========================================
echo.
echo Usage: %~nx0 ^<command^>
echo.
echo Commands:
echo   setup     First-time setup (install Ollama, models, deps)
echo   start     Start agent session
echo   stop      Stop and sync back
echo   status    Show session status
echo   push      Push code + patterns
echo   pull      Pull code + patterns
echo   shell     SSH into pod
echo   logs      Stream agent logs
echo.
echo Configuration:
echo   set RUNPOD_IP=your-pod-ip
echo   set RUNPOD_PORT=your-ssh-port
echo   set RUNPOD_KEY=path-to-ssh-key
echo.
echo Example:
echo   set RUNPOD_IP=212.81.xxx.xxx
echo   set RUNPOD_PORT=12345
echo   %~nx0 setup
echo   %~nx0 start
echo.
goto :eof
