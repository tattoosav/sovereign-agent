<#
.SYNOPSIS
    Build the self-contained, offline USB bundle for the air-gapped Sovereign Agent.

.DESCRIPTION
    Run this ONCE on a build machine that HAS internet. It downloads everything the
    offline target needs (Python, Ollama, NSSM, Python wheels, and the Ollama models),
    assembles it into one folder, and writes a SHA-256 manifest for integrity.

    The operator then copies the folder to a USB stick, carries it to the offline
    machine, and runs INSTALL.bat. No further internet access is required anywhere.

.PARAMETER OutDir
    Where to build the bundle (default: .\SovereignAgent-USB).

.PARAMETER Models
    Ollama model tags to bundle.

.PARAMETER PythonVersion
    Python version to download for the target.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install\build_bundle.ps1
#>
param(
    [string]$OutDir = ".\SovereignAgent-USB",
    [string[]]$Models = @("qwen2.5-coder:7b", "qwen2.5-coder:14b", "qwen2.5-coder:32b"),
    [string]$PythonVersion = "3.11.9"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Write-Host "=== Building offline bundle at $OutDir ===" -ForegroundColor Cyan

function Get-File($url, $dest) {
    # Download with up to 3 retries; fail loudly if the file can't be fetched.
    for ($i = 1; $i -le 3; $i++) {
        try {
            Write-Host "  downloading $url"
            Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
            return
        } catch {
            Write-Host "  retry $i failed: $($_.Exception.Message)" -ForegroundColor Yellow
            Start-Sleep -Seconds ($i * 3)
        }
    }
    throw "Failed to download $url after 3 attempts."
}

# 1. Folder skeleton
$dirs = @("app", "wheelhouse", "python", "ollama", "models", "tools", "docs")
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $OutDir $d) | Out-Null }

# 2. App source (exclude caches / local state / the venv)
Write-Host "Copying app source..." -ForegroundColor Cyan
$exclude = @(".git", ".venv", "__pycache__", ".sovereign", "logs", "SovereignAgent-USB")
robocopy $repoRoot (Join-Path $OutDir "app") /E /XD $exclude /NFL /NDL /NJH /NJS | Out-Null

# 3. Python installer (offline target runtime)
Write-Host "Downloading Python $PythonVersion..." -ForegroundColor Cyan
$pyExe = Join-Path $OutDir "python\python-$PythonVersion-amd64.exe"
Get-File "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe" $pyExe

# 4. Python wheels for Windows (offline install target)
Write-Host "Downloading Windows wheels to wheelhouse..." -ForegroundColor Cyan
$pyShort = ($PythonVersion -split '\.')[0..1] -join '.'
pip download -r (Join-Path $repoRoot "requirements.lock") `
    -d (Join-Path $OutDir "wheelhouse") `
    --platform win_amd64 --python-version $pyShort --only-binary=:all:

# 5. Ollama installer
Write-Host "Downloading Ollama installer..." -ForegroundColor Cyan
Get-File "https://ollama.com/download/OllamaSetup.exe" (Join-Path $OutDir "ollama\OllamaSetup.exe")

# 6. NSSM (service manager) - download zip and extract the 64-bit exe
Write-Host "Downloading NSSM..." -ForegroundColor Cyan
$nssmZip = Join-Path $env:TEMP "nssm.zip"
Get-File "https://nssm.cc/release/nssm-2.24.zip" $nssmZip
Expand-Archive -Path $nssmZip -DestinationPath (Join-Path $env:TEMP "nssm") -Force
Copy-Item (Join-Path $env:TEMP "nssm\nssm-2.24\win64\nssm.exe") (Join-Path $OutDir "tools\nssm.exe") -Force

# 7. Export Ollama models (blobs + manifests)
Write-Host "Pulling + exporting Ollama models (this is the big one)..." -ForegroundColor Cyan
foreach ($m in $Models) { ollama pull $m }
$ollamaModels = Join-Path $env:USERPROFILE ".ollama\models"
if (Test-Path $ollamaModels) {
    robocopy $ollamaModels (Join-Path $OutDir "models") /E /NFL /NDL /NJH /NJS | Out-Null
} else {
    throw "Ollama model store not found at $ollamaModels - is Ollama installed on this build machine?"
}

# 8. Installer scripts, config, docs, README
Copy-Item (Join-Path $PSScriptRoot "install_airgap.ps1")   $OutDir
Copy-Item (Join-Path $PSScriptRoot "uninstall_airgap.ps1") $OutDir
Copy-Item (Join-Path $PSScriptRoot "preflight.ps1")        $OutDir
Copy-Item (Join-Path $PSScriptRoot "INSTALL.bat")          $OutDir
Copy-Item (Join-Path $PSScriptRoot "config.yaml")          $OutDir
Copy-Item (Join-Path $PSScriptRoot "README.md")            $OutDir
Copy-Item (Join-Path $repoRoot "docs\AIRGAP_RUNBOOK.md")   (Join-Path $OutDir "docs")

# 9. Integrity manifest (SHA-256 of every file)
Write-Host "Generating checksums..." -ForegroundColor Cyan
$root = (Resolve-Path $OutDir).Path
$checks = Get-ChildItem -Recurse -File $OutDir | Where-Object { $_.Name -ne "checksums.txt" } |
    ForEach-Object {
        $rel = $_.FullName.Substring($root.Length + 1)
        "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash)  $rel"
    }
$checks | Set-Content -Path (Join-Path $OutDir "checksums.txt") -Encoding utf8

$size = "{0:N1} GB" -f ((Get-ChildItem -Recurse -File $OutDir | Measure-Object Length -Sum).Sum / 1GB)
Write-Host "`n=== Bundle complete: $OutDir ($size) ===" -ForegroundColor Green
Write-Host "Copy this folder to a USB stick, then run INSTALL.bat on the target machine." -ForegroundColor Green
