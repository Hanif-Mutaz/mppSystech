@echo off
cd /d "%~dp0"
where py >nul 2>nul || (echo Python belum terpasang. Install Python 3.11/3.12 dan centang Add Python to PATH.& pause & exit /b 1)
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
netsh advfirewall firewall add rule name="MPP Server Port 5000" dir=in action=allow protocol=TCP localport=5000
if not exist data mkdir data
echo Instalasi selesai.
echo Jalankan start_server.bat, lalu buka http://localhost:5000
pause
