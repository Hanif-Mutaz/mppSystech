@echo off
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":6000" ^| findstr "LISTENING"') do taskkill /PID %%a /F
