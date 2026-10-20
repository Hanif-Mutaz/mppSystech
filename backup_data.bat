@echo off
rem Backup PostgreSQL (aman dijalankan saat server hidup). Butuh pg_dump di PATH
rem (ikut terpasang bersama PostgreSQL: C:\Program Files\PostgreSQL\16\bin).
cd /d "%~dp0"
if not exist backup mkdir backup
rem Baca MPP_DATABASE_URL dari .env bila belum ada di environment
if "%MPP_DATABASE_URL%"=="" for /f "usebackq tokens=1,* delims==" %%a in (".env") do if "%%a"=="MPP_DATABASE_URL" set "MPP_DATABASE_URL=%%b"
if "%MPP_DATABASE_URL%"=="" (echo MPP_DATABASE_URL belum di-set di .env & exit /b 1)
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set dt=%%i
pg_dump --format=custom --file="backup\mpp_%dt%.dump" "%MPP_DATABASE_URL%"
if errorlevel 1 (echo BACKUP GAGAL & exit /b 1)
echo Backup selesai: backup\mpp_%dt%.dump
rem Simpan 30 backup terakhir
powershell -NoProfile -Command "Get-ChildItem backup\mpp_*.dump | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item"
rem Restore: pg_restore --clean --if-exists --no-owner -d "%MPP_DATABASE_URL%" backup\NAMA_FILE.dump
