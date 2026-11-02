@echo off
cd /d "%~dp0"
"order-fulfillment-coordinator\apps\api\.venv\Scripts\python.exe" scripts\teacher_demo.py %*
if errorlevel 1 pause
