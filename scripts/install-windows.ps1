<#
.SYNOPSIS
    Install RaySim on Windows with all dependencies (including pythonocc-core).

.DESCRIPTION
    This script:
    1. Downloads micromamba (lightweight conda package manager) if not present
    2. Creates a conda environment with pythonocc-core, PySide6, and all UI deps
    3. Installs raysim into the environment in editable mode
    4. Creates a desktop shortcut and a launcher script

    Run from the raysim project root:
        powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1

.NOTES
    Requires: Windows 10/11, internet connection
    Downloads: ~500 MB (pythonocc-core + Qt + OCCT + Python)
    Disk usage: ~2.5 GB after install
#>

$ErrorActionPreference = "Stop"

# --- Configuration ---
$EnvName = "raysim-ui"
$PythonVersion = "3.12"
$OcctVersion = "7.9.0"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$MambaRoot = Join-Path $env:LOCALAPPDATA "raysim-micromamba"
$MambaExe = Join-Path $ProjectRoot "bin\micromamba.exe"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RaySim Installer for Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project root: $ProjectRoot"
Write-Host ""

# --- Step 1: Micromamba ---
if (Test-Path $MambaExe) {
    Write-Host "[1/4] micromamba already installed" -ForegroundColor Green
} else {
    Write-Host "[1/4] Downloading micromamba..." -ForegroundColor Yellow
    $MambaDir = Split-Path -Parent $MambaExe
    if (-not (Test-Path $MambaDir)) { New-Item -ItemType Directory -Path $MambaDir -Force | Out-Null }

    $MambaUrl = "https://micro.mamba.pm/api/micromamba/win-64/latest"
    $TmpZip = Join-Path $env:TEMP "micromamba.tar.bz2"

    Invoke-WebRequest -Uri $MambaUrl -OutFile $TmpZip
    # micromamba ships as a tar.bz2 with Library/bin/micromamba.exe inside
    # Use tar (available on Windows 10+) to extract
    $TmpExtract = Join-Path $env:TEMP "micromamba_extract"
    if (Test-Path $TmpExtract) { Remove-Item -Recurse -Force $TmpExtract }
    New-Item -ItemType Directory -Path $TmpExtract -Force | Out-Null
    tar -xf $TmpZip -C $TmpExtract 2>$null
    $Found = Get-ChildItem -Recurse -Path $TmpExtract -Filter "micromamba.exe" | Select-Object -First 1
    if ($Found) {
        Copy-Item $Found.FullName $MambaExe -Force
        Write-Host "  Installed to $MambaExe" -ForegroundColor Green
    } else {
        Write-Error "Failed to extract micromamba.exe from download"
        exit 1
    }
    Remove-Item -Recurse -Force $TmpExtract -ErrorAction SilentlyContinue
    Remove-Item $TmpZip -ErrorAction SilentlyContinue
}

$env:MAMBA_ROOT_PREFIX = $MambaRoot

# Ensure the condabin directory exists (micromamba needs to write activation scripts there)
$CondaBin = Join-Path $MambaRoot "condabin"
if (-not (Test-Path $CondaBin)) { New-Item -ItemType Directory -Path $CondaBin -Force | Out-Null }

# --- Step 2: Create conda environment ---
$EnvPath = Join-Path $MambaRoot "envs\$EnvName"
if (Test-Path $EnvPath) {
    Write-Host "[2/4] Environment '$EnvName' already exists" -ForegroundColor Green
    Write-Host "  To recreate: delete $EnvPath and re-run this script"
} else {
    Write-Host "[2/4] Creating environment '$EnvName' (this downloads ~500 MB)..." -ForegroundColor Yellow
    Write-Host "  Python $PythonVersion + pythonocc-core $OcctVersion + PySide6 + matplotlib"
    Write-Host ""
    & $MambaExe create -n $EnvName `
        "python=$PythonVersion" `
        "pythonocc-core=$OcctVersion" `
        pyside6 matplotlib pyqtgraph `
        -c conda-forge -y
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create conda environment"
        exit 1
    }
    Write-Host "  Environment created" -ForegroundColor Green
}

# --- Step 3: Install raysim ---
Write-Host "[3/4] Installing raysim into the environment..." -ForegroundColor Yellow
& $MambaExe run -n $EnvName pip install -e "$ProjectRoot[ray,ui]" --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install raysim"
    exit 1
}

# Verify
& $MambaExe run -n $EnvName raysim --version
Write-Host "  raysim installed" -ForegroundColor Green

# --- Step 4: Create launcher scripts ---
Write-Host "[4/4] Creating launcher scripts..." -ForegroundColor Yellow

# Command-line launcher
$CliLauncher = Join-Path $ProjectRoot "raysim.cmd"
@"
@echo off
set MAMBA_ROOT_PREFIX=$MambaRoot
"$MambaExe" run -n $EnvName raysim %*
"@ | Set-Content -Path $CliLauncher -Encoding ASCII
Write-Host "  Created $CliLauncher"

# GUI launcher (hides console window)
$GuiLauncher = Join-Path $ProjectRoot "raysim-gui.vbs"
@"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Environment("Process")("MAMBA_ROOT_PREFIX") = "$MambaRoot"
WshShell.Run """$MambaExe"" run -n $EnvName raysim gui", 0, False
"@ | Set-Content -Path $GuiLauncher -Encoding ASCII
Write-Host "  Created $GuiLauncher (double-click to launch GUI)"

# Desktop shortcut
try {
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("$Desktop\RaySim.lnk")
    $Shortcut.TargetPath = "wscript.exe"
    $Shortcut.Arguments = """$GuiLauncher"""
    $Shortcut.WorkingDirectory = $ProjectRoot
    $Shortcut.Description = "RaySim - 3D TID Sector-Shielding Simulator"
    $Shortcut.Save()
    Write-Host "  Created desktop shortcut: RaySim.lnk" -ForegroundColor Green
} catch {
    Write-Host "  (Could not create desktop shortcut - not critical)" -ForegroundColor DarkYellow
}

# --- Done ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  To launch the GUI:"
Write-Host "    - Double-click 'RaySim' on your desktop"
Write-Host "    - Or double-click raysim-gui.vbs in the project folder"
Write-Host "    - Or run: .\raysim.cmd gui"
Write-Host ""
Write-Host "  To use the CLI:"
Write-Host "    .\raysim.cmd run --scene ... --materials ... --detectors ... --dose-curve ... --out run.json"
Write-Host ""
Write-Host "  To run tests:"
Write-Host "    .\raysim.cmd --version"
Write-Host ""
