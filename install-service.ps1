# Run this script as Administrator once to install the app as a scheduled task
# The task runs as SYSTEM (full admin rights) and starts on boot

$log = "C:\Claude\FileServer-Monitor\install.log"
Start-Transcript -Path $log -Force

$taskName  = "FileServerMonitor"
$pythonPath = "C:\Claude\FileServer-Monitor\venv\Scripts\python.exe"
$appPath   = "C:\Claude\FileServer-Monitor\app.py"
$workDir   = "C:\Claude\FileServer-Monitor"

Write-Host "Checking python: $pythonPath"
if (-not (Test-Path $pythonPath)) { Write-Error "Python not found at $pythonPath"; Stop-Transcript; exit 1 }

Write-Host "Removing existing task (if any)..."
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Write-Host "Creating task action..."
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $appPath -WorkingDirectory $workDir

Write-Host "Creating trigger..."
$trigger = New-ScheduledTaskTrigger -AtStartup

Write-Host "Creating settings..."
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)

Write-Host "Creating principal (SYSTEM)..."
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Write-Host "Registering task..."
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "File Server Monitor"

Write-Host "Starting task..."
Start-ScheduledTask -TaskName $taskName

Start-Sleep -Seconds 3
$state = (Get-ScheduledTask -TaskName $taskName).State
Write-Host "Task state: $state" -ForegroundColor Cyan

Stop-Transcript
