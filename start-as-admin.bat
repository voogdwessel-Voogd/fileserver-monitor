@echo off
powershell -Command "Start-Process powershell -ArgumentList '-NoExit -Command cd C:\Claude\FileServer-Monitor; py app.py' -Verb RunAs"
