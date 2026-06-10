<#
.SYNOPSIS
    Assemble the self-contained, offline USB bundle for the air-gapped Sovereign Agent.

.DESCRIPTION
    Run this ONCE on a build machine that HAS internet. It produces a single folder
    (SovereignAgent-USB) containing everything the offline target needs: app source,
    Python wheels, Python installer, Ollama installer, exported models, NSSM, the
    installer scripts, config, docs, and a SHA-256 manifest for integrity.

    Copy the resulting folder to a USB stick and carry it to the air-gapped machine,
    then run INSTALL.bat there.

.PARAMETER OutDir
    Where to build the bundle (default: .\SovereignAgent-USB).

.PARAMETER Models
    Ollama model tags to bundle.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install\build_bundle.ps1
#>
param(
    [string]$OutDir = ".\SovereignAgent-USB",
    [string[]]$Models = @("qwen2.5-coder:7b", "qwen2.5-coder:14b", "qwen2.5-coder:32b"),
    [string]$PythonVersion = "3.11"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Write-Host "Building offline bundle at $OutDir" -ForegroundColor Cyan

# 1. Folder skeleton
$dirs = @("app", "wheelhouse", "python", "ollama", "models", "tools", "docs")
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $OutDir $d) | Out-Null }

# 2. App source (exclude caches / local state / the venv)
Write-Host "Copying app source..."
$exclude = @(".git", ".venv", "__pycache__", ".sovereign", "logs", "SovereignAgent-USB")
robocopy $repoRoot (Join-Path $OutDir "app") /E /XD $exclude /NFL /NDL /NJH /NJS | Out-Null

# 3. Python wheels for Windows (offline install target)
Write-Host "Downloading Windows wheels to wheelhouse..."
pip download -r (Join-Path $repoRoot "requirements.lock") `
    -d (Join-Path $OutDir "wheelhouse") `
    --platform win_amd64 --python-version $PythonVersion --only-binary=:all:

# 4. Stage the external installers (operator downloads these once, places alongside)
Write-Host "NOTE: place the following installers into the bundle before shipping:" -ForegroundColor Yellow
Write-Host "  - python\python-$PythonVersion-amd64.exe   (https://www.python.org/downloads/windows/)"
Write-Host "  - ollama\OllamaSetup.exe                    (https://ollama.com/download/windows)"
Write-Host "  - tools\nssm.exe                            (https://nssm.cc/download)"

# 5. Export Ollama models (blobs + manifests)
Write-Host "Exporting Ollama models..."
foreach ($m in $Models) { ollama pull $m }
$ollamaModels = Join-Path $env:USERPROFILE ".ollama\models"
if (Test-Path $ollamaModels) {
    robocopy $ollamaModels (Join-Path $OutDir "models") /E /NFL /NDL /NJH /NJS | Out-Null
} else {
    Write-Host "WARNING: $ollamaModels not found - pull models then re-run." -ForegroundColor Yellow
}

# 6. Installer scripts, config, docs
Copy-Item (Join-Path $PSScriptRoot "install_airgap.ps1")   $OutDir
Copy-Item (Join-Path $PSScriptRoot "uninstall_airgap.ps1") $OutDir
Copy-Item (Join-Path $PSScriptRoot "INSTALL.bat")          $OutDir
Copy-Item (Join-Path $PSScriptRoot "config.yaml")          $OutDir
Copy-Item (Join-Path $repoRoot "docs\AIRGAP_RUNBOOK.md")   (Join-Path $OutDir "docs")

# 7. Integrity manifest (SHA-256 of every file)
Write-Host "Generating checksums..."
$checks = Get-ChildItem -Recurse -File $OutDir | Where-Object { $_.Name -ne "checksums.txt" } |
    ForEach-Object {
        $rel = $_.FullName.Substring((Resolve-Path $OutDir).Path.Length + 1)
        "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash)  $rel"
    }
$checks | Set-Content -Path (Join-Path $OutDir "checksums.txt") -Encoding utf8

Write-Host "Bundle complete: $OutDir" -ForegroundColor Green
Write-Host "Copy this folder to a USB stick and run INSTALL.bat on the target." -ForegroundColor Green
