<#
.SYNOPSIS
    One-action, fully offline installer for the air-gapped Sovereign Agent.

.DESCRIPTION
    Runs entirely from the USB bundle on a machine that has NEVER been on the internet.
    No package downloads, no `ollama pull`. Verifies bundle integrity, installs Python
    + dependencies offline, installs Ollama + bundled models, writes config, sets env
    vars, and registers auto-start Windows services (Ollama + SovereignAgent) via NSSM.

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
Write-Host "=== Sovereign Agent air-gapped install ===" -ForegroundColor Cyan

# 0. Verify bundle integrity (refuse to install a tampered/corrupt USB copy)
if (-not $SkipChecksum -and (Test-Path "$bundle\checksums.txt")) {
    Write-Host "Verifying bundle integrity..."
    foreach ($line in Get-Content "$bundle\checksums.txt") {
        if ($line -notmatch '^\s*([0-9A-Fa-f]{64})\s+(.+)$') { continue }
        $hash = $matches[1]; $rel = $matches[2]
        $path = Join-Path $bundle $rel
        if (-not (Test-Path $path) -or (Get-FileHash $path -Algorithm SHA256).Hash -ne $hash) {
            throw "Integrity check FAILED for $rel - aborting install."
        }
    }
    Write-Host "Integrity OK." -ForegroundColor Green
}

# 1. Directory layout
foreach ($d in @("app", "workspace", "logs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot $d) | Out-Null
}
robocopy "$bundle\app" "$InstallRoot\app" /E /NFL /NDL /NJH /NJS | Out-Null
Copy-Item "$bundle\tools\nssm.exe" "$InstallRoot\nssm.exe" -Force

# 2. Python (silent, offline) if not already present
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) {
    Write-Host "Installing bundled Python..."
    $pyInstaller = Get-ChildItem "$bundle\python\*.exe" | Select-Object -First 1
    Start-Process -Wait -FilePath $pyInstaller.FullName `
        -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")
}

# 3. Virtualenv + offline dependency install (no index)
Write-Host "Creating venv and installing dependencies offline..."
python -m venv "$InstallRoot\app\.venv"
$venvPy = "$InstallRoot\app\.venv\Scripts\python.exe"
& $venvPy -m pip install --no-index --find-links "$bundle\wheelhouse" `
    -r "$InstallRoot\app\requirements.lock"

# 4. Ollama (silent) + bundled models (NO pull)
$ollama = (Get-Command ollama -ErrorAction SilentlyContinue)
if (-not $ollama) {
    Write-Host "Installing bundled Ollama..."
    Start-Process -Wait -FilePath "$bundle\ollama\OllamaSetup.exe" -ArgumentList "/SILENT"
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
& $nssm install Ollama $ollamaExe "serve"
& $nssm set Ollama Start SERVICE_AUTO_START
& $nssm set Ollama AppStdout "$InstallRoot\logs\ollama.out.log"
& $nssm set Ollama AppStderr "$InstallRoot\logs\ollama.err.log"

& $nssm install SovereignAgent $venvPy "-m" "src.autonomous" "--working-dir" "$InstallRoot\workspace"
& $nssm set SovereignAgent AppDirectory "$InstallRoot\app"
& $nssm set SovereignAgent AppEnvironmentExtra `
    "SOVEREIGN_AIRGAP_ENFORCE=true" "SOVEREIGN_OLLAMA_URL=http://127.0.0.1:11434"
& $nssm set SovereignAgent DependOnService Ollama
& $nssm set SovereignAgent Start SERVICE_AUTO_START
& $nssm set SovereignAgent AppStdout "$InstallRoot\logs\out.log"
& $nssm set SovereignAgent AppStderr "$InstallRoot\logs\err.log"
& $nssm set SovereignAgent AppThrottle 5000
& $nssm set SovereignAgent AppExit Default Restart

# 7. Outbound-block firewall rules (belt-and-suspenders egress prevention)
Write-Host "Adding outbound-block firewall rules..."
New-NetFirewallRule -DisplayName "Sovereign-Block-Outbound-Python" -Direction Outbound `
    -Program $venvPy -RemoteAddress Internet -Action Block -ErrorAction SilentlyContinue | Out-Null

# 8. Start services + run the egress self-check
Start-Service Ollama
Start-Sleep -Seconds 3
Start-Service SovereignAgent
Write-Host "Running egress self-check..."
& $venvPy -m src.core.egress_guard

Write-Host "`nINSTALL OK." -ForegroundColor Green
Write-Host "Drop task files into $InstallRoot\workspace\tasks\inbox; results land in ...\tasks\done." -ForegroundColor Green
