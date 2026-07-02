@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PATH=%USERPROFILE%\.local\bin;%PATH%
cd /d "%~dp0order-fulfillment-coordinator\apps\api"
uv run fastapi dev src/fulfillment/main.py
