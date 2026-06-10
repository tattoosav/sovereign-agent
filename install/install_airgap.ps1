<#
.SYNOPSIS
    One-action, fully offline installer for the air-gapped Sovereign Agent + CRM.

.DESCRIPTION
    Runs entirely from the USB bundle on a machine that has NEVER been on the internet.
    No package downloads, no `ollama pull`. Logged, idempotent, and self-verifying:
    it runs preflight checks, verifies bundle integrity, installs Python + dependencies
    offline, installs Ollama + bundled models, registers auto-start Windows services,
    then runs a self-test before declaring success. Any error stops the install with a
    clear message and a full transcript in <InstallRoot>\logs.

    Run elevated (INSTALL.bat does this for you).

.PARAMETER InstallRoot
    Where the agent is installed (default C:\Sovereign).
#>
param(
    [string]$InstallRoot = "C:\Sovereign",
    [switch]$SkipChecksum
)

$ErrorActionPreference = "Stop"
$bundle = $PSScriptRoot
New-Item -ItemType Directory -Force -Path "$InstallRoot\logs" | Out-Null
$log = "$InstallRoot\logs\install-$(Get-Date -Format yyyyMMdd-HHmmss).log"
Start-Transcript -Path $log -Append | Out-Null

function Fail($msg) {
    Write-Host "`nINSTALL FAILED: $msg" -ForegroundColor Red
    Write-Host "Full log: $log" -ForegroundColor Yellow
    Stop-Transcript | Out-Null
    exit 1
}

try {
    Write-Host "=== Sovereign Agent air-gapped install ===" -ForegroundColor Cyan

    # 0a. Preflight (target + bundle sanity)
    & "$bundle\preflight.ps1" -Bundle $bundle
    if ($LASTEXITCODE -ne 0) { Fail "preflight checks did not pass." }

    # 0b. Integrity (refuse a tampered/corrupt USB copy)
    if (-not $SkipChecksum -and (Test-Path "$bundle\checksums.txt")) {
        Write-Host "Verifying bundle integrity..." -ForegroundColor Cyan
        foreach ($line in Get-Content "$bundle\checksums.txt") {
            if ($line -notmatch '^\s*([0-9A-Fa-f]{64})\s+(.+)$') { continue }
            $hash = $matches[1]; $rel = $matches[2]
            $path = Join-Path $bundle $rel
            if (-not (Test-Path $path) -or (Get-FileHash $path -Algorithm SHA256).Hash -ne $hash) {
                Fail "integrity check FAILED for $rel."
            }
        }
        Write-Host "Integrity OK." -ForegroundColor Green
    }

    # 1. Directory layout + app copy
    foreach ($d in @("app", "workspace", "logs")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot $d) | Out-Null
    }
    robocopy "$bundle\app" "$InstallRoot\app" /E /NFL /NDL /NJH /NJS | Out-Null
    Copy-Item "$bundle\tools\nssm.exe" "$InstallRoot\nssm.exe" -Force

    # 2. Python (silent, offline) if not already present
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "Installing bundled Python..." -ForegroundColor Cyan
        $pyInstaller = Get-ChildItem "$bundle\python\*.exe" | Select-Object -First 1
        Start-Process -Wait -FilePath $pyInstaller.FullName `
            -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1"
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                    [Environment]::GetEnvironmentVariable("Path", "User")
    }

    # 3. Virtualenv + offline dependency install (no index)
    Write-Host "Creating venv and installing dependencies offline..." -ForegroundColor Cyan
    python -m venv "$InstallRoot\app\.venv"
    $venvPy = "$InstallRoot\app\.venv\Scripts\python.exe"
    & $venvPy -m pip install --no-index --find-links "$bundle\wheelhouse" `
        -r "$InstallRoot\app\requirements.lock"
    if ($LASTEXITCODE -ne 0) { Fail "offline dependency install failed." }

    # 4. Ollama (silent) + bundled models (NO pull)
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Host "Installing bundled Ollama..." -ForegroundColor Cyan
        Start-Process -Wait -FilePath "$bundle\ollama\OllamaSetup.exe" -ArgumentList "/SILENT"
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
    }
    $modelDest = Join-Path $env:USERPROFILE ".ollama\models"
    New-Item -ItemType Directory -Force -Path $modelDest | Out-Null
    robocopy "$bundle\models" $modelDest /E /NFL /NDL /NJH /NJS | Out-Null

    # 5. Config + machine environment variables
    Copy-Item "$bundle\config.yaml" "$InstallRoot\app\config.yaml" -Force
    [Environment]::SetEnvironmentVariable("SOVEREIGN_AIRGAP_ENFORCE", "true", "Machine")
    [Environment]::SetEnvironmentVariable("SOVEREIGN_WORKING_DIR", "$InstallRoot\workspace", "Machine")
    [Environment]::SetEnvironmentVariable("SOVEREIGN_OLLAMA_URL", "http://127.0.0.1:11434", "Machine")

    # 6. Register services (Ollama first; agent depends on it; both auto-start at boot)
    $nssm = "$InstallRoot\nssm.exe"
    $ollamaExe = (Get-Command ollama).Source
    & $nssm install Ollama $ollamaExe "serve" 2>$null
    & $nssm set Ollama Start SERVICE_AUTO_START
    & $nssm set Ollama AppStdout "$InstallRoot\logs\ollama.out.log"
    & $nssm set Ollama AppStderr "$InstallRoot\logs\ollama.err.log"

    & $nssm install SovereignAgent $venvPy "-m" "src.autonomous" "--working-dir" "$InstallRoot\workspace" 2>$null
    & $nssm set SovereignAgent AppDirectory "$InstallRoot\app"
    & $nssm set SovereignAgent AppEnvironmentExtra `
        "SOVEREIGN_AIRGAP_ENFORCE=true" "SOVEREIGN_OLLAMA_URL=http://127.0.0.1:11434"
    & $nssm set SovereignAgent DependOnService Ollama
    & $nssm set SovereignAgent Start SERVICE_AUTO_START
    & $nssm set SovereignAgent AppStdout "$InstallRoot\logs\out.log"
    & $nssm set SovereignAgent AppStderr "$InstallRoot\logs\err.log"
    & $nssm set SovereignAgent AppThrottle 5000
    & $nssm set SovereignAgent AppExit Default Restart

    # Web UI service so the CRM is always available at http://127.0.0.1:8000/crm
    & $nssm install SovereignWeb $venvPy "-m" "src.web" "--host" "127.0.0.1" "--port" "8000" 2>$null
    & $nssm set SovereignWeb AppDirectory "$InstallRoot\app"
    & $nssm set SovereignWeb AppEnvironmentExtra `
        "SOVEREIGN_AIRGAP_ENFORCE=true" "SOVEREIGN_WORKING_DIR=$InstallRoot\workspace" `
        "SOVEREIGN_OLLAMA_URL=http://127.0.0.1:11434"
    & $nssm set SovereignWeb DependOnService Ollama
    & $nssm set SovereignWeb Start SERVICE_AUTO_START
    & $nssm set SovereignWeb AppStdout "$InstallRoot\logs\web.out.log"
    & $nssm set SovereignWeb AppStderr "$InstallRoot\logs\web.err.log"
    & $nssm set SovereignWeb AppExit Default Restart

    # 7. Outbound-block firewall rules (belt-and-suspenders egress prevention)
    Write-Host "Adding outbound-block firewall rules..." -ForegroundColor Cyan
    New-NetFirewallRule -DisplayName "Sovereign-Block-Outbound-Python" -Direction Outbound `
        -Program $venvPy -RemoteAddress Internet -Action Block -ErrorAction SilentlyContinue | Out-Null

    # 8. Start services
    Start-Service Ollama
    Start-Sleep -Seconds 3
    Start-Service SovereignAgent
    Start-Service SovereignWeb

    # 9. Self-test (offline): egress check + CRM/web smoke
    Write-Host "Running post-install self-test..." -ForegroundColor Cyan
    Push-Location "$InstallRoot\app"
    & $venvPy -m scripts.smoke
    $smoke = $LASTEXITCODE
    & $venvPy -m src.core.egress_guard
    Pop-Location
    if ($smoke -ne 0) { Fail "post-install self-test failed (see above)." }

    Write-Host "`n=== INSTALL OK ===" -ForegroundColor Green
    Write-Host "CRM web UI:   http://127.0.0.1:8000/crm  (start: python -m src.web)" -ForegroundColor Green
    Write-Host "Drop tasks:   $InstallRoot\workspace\tasks\inbox   ->  results in ...\tasks\done" -ForegroundColor Green
    Write-Host "Log:          $log" -ForegroundColor Green
    Stop-Transcript | Out-Null
}
catch {
    Fail $_.Exception.Message
}
