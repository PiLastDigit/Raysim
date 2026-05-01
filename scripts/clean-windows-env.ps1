<#
.SYNOPSIS
    Clean the RaySim Windows conda environment and package cache, then verify.

.DESCRIPTION
    Run this if the install script failed mid-way (e.g., corrupted package cache).
    After running, re-run install-windows.ps1 to reinstall cleanly.

    powershell -ExecutionPolicy Bypass -File scripts\clean-windows-env.ps1
#>

$ErrorActionPreference = "Stop"

$MambaRoot = Join-Path $env:LOCALAPPDATA "raysim-micromamba"
$EnvPath = Join-Path $MambaRoot "envs\raysim-ui"
$PkgsPath = Join-Path $MambaRoot "pkgs"

# Also check the old (WSL-created) location inside the project
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$OldMambaRoot = Join-Path $ProjectRoot ".micromamba"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RaySim Environment Cleanup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$cleaned = 0

# --- Remove partial environment ---
if (Test-Path $EnvPath) {
    Write-Host "Removing environment: $EnvPath" -ForegroundColor Yellow
    Remove-Item -Recurse -Force $EnvPath
    $cleaned++
    Write-Host "  Removed" -ForegroundColor Green
} else {
    Write-Host "Environment not found (already clean): $EnvPath" -ForegroundColor DarkGray
}

# --- Remove package cache ---
if (Test-Path $PkgsPath) {
    $size = (Get-ChildItem -Recurse -Force $PkgsPath -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    $sizeMB = [math]::Round($size / 1MB, 0)
    Write-Host "Removing package cache ($sizeMB MB): $PkgsPath" -ForegroundColor Yellow
    # Use robocopy empty-dir trick to handle paths exceeding 260 chars (Qt headers)
    $emptyDir = Join-Path $env:TEMP "raysim_empty_dir"
    New-Item -ItemType Directory -Path $emptyDir -Force | Out-Null
    robocopy $emptyDir $PkgsPath /MIR /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    Remove-Item -Recurse -Force $PkgsPath -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $emptyDir -ErrorAction SilentlyContinue
    $cleaned++
    Write-Host "  Removed" -ForegroundColor Green
} else {
    Write-Host "Package cache not found (already clean): $PkgsPath" -ForegroundColor DarkGray
}

# --- Remove old WSL-created .micromamba if it exists ---
if (Test-Path $OldMambaRoot) {
    $size = (Get-ChildItem -Recurse -Force $OldMambaRoot -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    $sizeMB = [math]::Round($size / 1MB, 0)
    Write-Host "Removing old WSL-created .micromamba ($sizeMB MB): $OldMambaRoot" -ForegroundColor Yellow
    $emptyDir2 = Join-Path $env:TEMP "raysim_empty_dir2"
    New-Item -ItemType Directory -Path $emptyDir2 -Force | Out-Null
    robocopy $emptyDir2 $OldMambaRoot /MIR /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    Remove-Item -Recurse -Force $OldMambaRoot -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $emptyDir2 -ErrorAction SilentlyContinue
    $cleaned++
    Write-Host "  Removed" -ForegroundColor Green
} else {
    Write-Host "Old .micromamba not found (already clean): $OldMambaRoot" -ForegroundColor DarkGray
}

# --- Verification ---
Write-Host ""
Write-Host "--- Verification ---" -ForegroundColor Cyan
$allClean = $true

$checks = @(
    @{ Path = $EnvPath;     Label = "Environment (raysim-ui)" },
    @{ Path = $PkgsPath;    Label = "Package cache" },
    @{ Path = $OldMambaRoot; Label = "Old WSL .micromamba" }
)

foreach ($check in $checks) {
    if (Test-Path $check.Path) {
        Write-Host "  STILL EXISTS: $($check.Label) -> $($check.Path)" -ForegroundColor Red
        $allClean = $false
    } else {
        Write-Host "  CLEAN: $($check.Label)" -ForegroundColor Green
    }
}

# Check that micromamba binary still exists (we keep it)
$MambaExe = Join-Path $ProjectRoot "bin\micromamba.exe"
if (Test-Path $MambaExe) {
    Write-Host "  OK: micromamba.exe still present (kept)" -ForegroundColor Green
} else {
    Write-Host "  MISSING: micromamba.exe (install script will re-download)" -ForegroundColor DarkYellow
}

# Check that launcher files exist (they'll need updating after reinstall)
$CliLauncher = Join-Path $ProjectRoot "raysim.cmd"
$GuiLauncher = Join-Path $ProjectRoot "raysim-gui.vbs"
if (Test-Path $CliLauncher) {
    Write-Host "  OK: raysim.cmd exists (will be refreshed by installer)" -ForegroundColor Green
}
if (Test-Path $GuiLauncher) {
    Write-Host "  OK: raysim-gui.vbs exists (will be refreshed by installer)" -ForegroundColor Green
}

Write-Host ""
if ($allClean) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  All clean! Ready to reinstall." -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Next step:"
    Write-Host "    powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1"
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  Some items could not be removed." -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Close any programs using the raysim environment, then re-run this script."
    Write-Host "  If that doesn't help, manually delete the paths listed above."
}
Write-Host ""
