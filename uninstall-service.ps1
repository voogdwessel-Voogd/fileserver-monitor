# Run as Administrator to remove the scheduled task
Stop-ScheduledTask -TaskName "FileServerMonitor" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "FileServerMonitor" -Confirm:$false
Write-Host "FileServerMonitor task removed." -ForegroundColor Yellow
