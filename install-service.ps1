# Run this script as Administrator once to install the app as a scheduled task
# The task runs as SYSTEM (full admin rights) and starts on boot

$taskName = "FileServerMonitor"
$pythonPath = (Get-Command py).Source
$appPath = "C:\Claude\FileServer-Monitor\app.py"
$workDir = "C:\Claude\FileServer-Monitor"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument $appPath `
    -WorkingDirectory $workDir

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "File Server Monitor - tracks who opens SMB files" | Out-Null

# Start immediately
Start-ScheduledTask -TaskName $taskName

Write-Host "Installed and started '$taskName' as SYSTEM service." -ForegroundColor Green
Write-Host "App runs at http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Other commands:"
Write-Host "  Stop:    Stop-ScheduledTask -TaskName $taskName"
Write-Host "  Start:   Start-ScheduledTask -TaskName $taskName"
Write-Host "  Remove:  Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
