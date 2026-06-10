<#
.SYNOPSIS
    Stop and remove the Sovereign Agent air-gapped install.

.PARAMETER InstallRoot
    Install location (default C:\Sovereign).

.PARAMETER Purge
    Also delete the install directory (workspace + results included).
#>
param(
    [string]$InstallRoot = "C:\Sovereign",
    [switch]$Purge
)

$ErrorActionPreference = "SilentlyContinue"
$nssm = "$InstallRoot\nssm.exe"

Write-Host "Stopping services..." -ForegroundColor Cyan
Stop-Service SovereignAgent
Stop-Service Ollama

if (Test-Path $nssm) {
    & $nssm remove SovereignAgent confirm
    & $nssm remove Ollama confirm
}

Remove-NetFirewallRule -DisplayName "Sovereign-Block-Outbound-Python"

[Environment]::SetEnvironmentVariable("SOVEREIGN_AIRGAP_ENFORCE", $null, "Machine")
[Environment]::SetEnvironmentVariable("SOVEREIGN_WORKING_DIR", $null, "Machine")
[Environment]::SetEnvironmentVariable("SOVEREIGN_OLLAMA_URL", $null, "Machine")

if ($Purge) {
    Write-Host "Purging $InstallRoot ..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $InstallRoot
}

Write-Host "Uninstall complete." -ForegroundColor Green
