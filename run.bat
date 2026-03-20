@echo off
cd /d "%~dp0"
echo Starting Yuvraj Library...
if not exist venv (
    echo Setting up Python environment (first time only)...
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt --quiet
echo.
echo Library is ready! Opening in your browser...
start "" http://localhost:5000
python app.py
pause
