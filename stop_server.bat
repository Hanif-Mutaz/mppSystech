@echo off
setlocal
set PORT=5000
if exist "%~dp0.env" for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do if "%%a"=="MPP_PORT" set PORT=%%b
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do taskkill /PID %%a /F
