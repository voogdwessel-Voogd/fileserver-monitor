#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installeert File Server Monitor als Windows scheduled task (SYSTEM).
.DESCRIPTION
    - Controleert/installeert Python 3.12
    - Kopieert app-bestanden naar de installatiedirectory
    - Maakt een virtual environment aan en installeert dependencies
    - Opent poort 5000 in Windows Firewall
    - Registreert en start de scheduled task als SYSTEM
.PARAMETER InstallDir
    Installatiedirectory (standaard: C:\FileServer-Monitor)
.PARAMETER Port
    Poort waarop de app luistert (standaard: 5000)
.EXAMPLE
    .\setup.ps1
    .\setup.ps1 -InstallDir "D:\Tools\FileServer-Monitor" -Port 8080
#>

param(
    [string]$InstallDir = 'C:\FileServer-Monitor',
    [int]$Port = 5000
)

$ErrorActionPreference = 'Stop'
$TaskName = 'FileServerMonitor'
$PythonMinVersion = [Version]'3.10'
$PythonInstallVersion = '3.12.10'
$PythonInstallerUrl = "https://www.python.org/ftp/python/$PythonInstallVersion/python-$PythonInstallVersion-amd64.exe"

function Write-Step([string]$msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}
function Write-Ok([string]$msg) {
    Write-Host "    OK: $msg" -ForegroundColor Green
}
function Write-Fail([string]$msg) {
    Write-Host "    FOUT: $msg" -ForegroundColor Red
}

# ── Stap 1: Python controleren / installeren ──────────────────────────────────

Write-Step "Python controleren..."

$pythonExe = $null
foreach ($cmd in @('python', 'python3', 'py')) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match 'Python (\d+\.\d+)') {
            if ([Version]$Matches[1] -ge $PythonMinVersion) {
                $pythonExe = (Get-Command $cmd -ErrorAction SilentlyContinue).Source
                Write-Ok "Gevonden: $ver ($pythonExe)"
                break
            }
        }
    } catch {}
}

if (-not $pythonExe) {
    Write-Host "    Python $PythonMinVersion+ niet gevonden. Downloaden en installeren..." -ForegroundColor Yellow
    $installer = "$env:TEMP\python-installer.exe"
    Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $installer -UseBasicParsing
    $args = '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0'
    Start-Process $installer -ArgumentList $args -Wait
    Remove-Item $installer -Force

    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path', 'User')

    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pythonExe) {
        Write-Fail "Python installatie mislukt. Installeer Python $PythonMinVersion+ handmatig via python.org."
        exit 1
    }
    Write-Ok "Python geinstalleerd: $pythonExe"
}

# ── Stap 2: Bestanden kopieren ────────────────────────────────────────────────

Write-Step "Bestanden kopieren naar $InstallDir..."

$sourceDir = $PSScriptRoot
$filesToCopy = @(
    'app.py', 'monitor.py', 'db.py', 'config.py', 'requirements.txt'
)

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
}

foreach ($file in $filesToCopy) {
    Copy-Item "$sourceDir\$file" "$InstallDir\$file" -Force
    Write-Ok $file
}

foreach ($dir in @('templates', 'static')) {
    if (Test-Path "$sourceDir\$dir") {
        Copy-Item "$sourceDir\$dir" "$InstallDir\$dir" -Recurse -Force
        Write-Ok "$dir\"
    }
}

# ── Stap 3: Virtual environment aanmaken ──────────────────────────────────────

Write-Step "Virtual environment aanmaken..."

$venvPython = "$InstallDir\venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    & $pythonExe -m venv "$InstallDir\venv"
    Write-Ok "Venv aangemaakt"
} else {
    Write-Ok "Venv bestaat al"
}

Write-Step "Dependencies installeren..."
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r "$InstallDir\requirements.txt" --quiet
Write-Ok "Dependencies geinstalleerd"

# ── Stap 4: Poort openen in firewall ─────────────────────────────────────────

Write-Step "Firewallregel instellen voor poort $Port..."

$ruleName = "FileServerMonitor-Poort$Port"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Ok "Firewallregel bestaat al"
} else {
    New-NetFirewallRule -DisplayName $ruleName `
        -Direction Inbound -Protocol TCP -LocalPort $Port `
        -Action Allow -Profile Any | Out-Null
    Write-Ok "Firewallregel aangemaakt (poort $Port)"
}

# ── Stap 5: Scheduled task registreren ───────────────────────────────────────

Write-Step "Scheduled task registreren als SYSTEM..."

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action   = New-ScheduledTaskAction -Execute $venvPython -Argument "$InstallDir\app.py" -WorkingDirectory $InstallDir
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "File Server Monitor — bestandstoegang op $env:COMPUTERNAME" | Out-Null

Write-Ok "Task geregistreerd"

# ── Stap 6: Task starten ──────────────────────────────────────────────────────

Write-Step "App starten..."
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 4

$state = (Get-ScheduledTask -TaskName $TaskName).State
if ($state -eq 'Running') {
    Write-Ok "App draait (task state: $state)"
} else {
    Write-Fail "Task state: $state — controleer Event Viewer voor details"
    exit 1
}

# ── Klaar ─────────────────────────────────────────────────────────────────────

Write-Host "`n============================================" -ForegroundColor Green
Write-Host "  Installatie geslaagd!" -ForegroundColor Green
Write-Host "  App bereikbaar op: http://localhost:$Port" -ForegroundColor Green
Write-Host "  Installatiedirectory: $InstallDir" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Green
