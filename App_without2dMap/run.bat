@echo off
cd /d "%~dp0"

if not exist .venv (
    echo First run: installing packages, please wait...
    py -3 -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

set HOLLOW_DB_SERVER=localhost\SQLEXPRESS
python main.py
pause