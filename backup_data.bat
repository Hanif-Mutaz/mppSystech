@echo off
cd /d "%~dp0"
if not exist backup mkdir backup
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
copy /Y data\mpp.db "backup\mpp_%dt:~0,8%_%dt:~8,6%.db"
