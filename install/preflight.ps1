<#
.SYNOPSIS
    Pre-install checks for the air-gapped Sovereign Agent bundle.

.DESCRIPTION
    Validates the target machine and the bundle BEFORE the installer changes anything.
    Run automatically by install_airgap.ps1; can also be run on its own to dry-check a
    USB copy. Exits non-zero if any check fails so the installer can stop safely.
#>
param(
    [string]$Bundle = $PSScriptRoot,
    [int]$MinFreeGb = 30
)

$ok = $true
function Test-Item($name, [bool]$pass, $detail = "") {
    $tag = if ($pass) { "[ OK ]" } else { "[FAIL]"; $script:ok = $false }
    $color = if ($pass) { "Green" } else { "Red" }
    Write-Host "$tag $name $detail" -ForegroundColor $color
}

Write-Host "=== Preflight checks ===" -ForegroundColor Cyan

# Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Test-Item "Administrator privileges" $isAdmin

# 64-bit Windows
Test-Item "64-bit Windows" ([Environment]::Is64BitOperatingSystem) "($([Environment]::OSVersion.VersionString))"

# Disk space on system drive
$sys = (Get-Item $env:SystemDrive).Root
$freeGb = [math]::Round((Get-PSDrive ($sys.Substring(0,1))).Free / 1GB, 1)
Test-Item "Free disk space" ($freeGb -ge $MinFreeGb) "($freeGb GB free, need $MinFreeGb GB)"

# Required bundle contents
$required = @(
    "install_airgap.ps1", "config.yaml", "checksums.txt",
    "app\requirements.lock", "app\src\autonomous.py",
    "tools\nssm.exe", "ollama\OllamaSetup.exe"
)
foreach ($rel in $required) {
    Test-Item "Bundle file: $rel" (Test-Path (Join-Path $Bundle $rel))
}
Test-Item "Python installer present" (
    @(Get-ChildItem (Join-Path $Bundle "python") -Filter *.exe -ErrorAction SilentlyContinue).Count -ge 1)
Test-Item "Wheelhouse populated" (
    @(Get-ChildItem (Join-Path $Bundle "wheelhouse") -Filter *.whl -ErrorAction SilentlyContinue).Count -ge 1)
Test-Item "Model store present" (
    @(Get-ChildItem (Join-Path $Bundle "models") -Recurse -File -ErrorAction SilentlyContinue).Count -ge 1)

Write-Host ""
if ($ok) {
    Write-Host "Preflight PASSED - safe to install." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Preflight FAILED - fix the items above before installing." -ForegroundColor Red
    exit 1
}
