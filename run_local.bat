@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Installing dependencies...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
)
call .venv\Scripts\activate.bat
python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause