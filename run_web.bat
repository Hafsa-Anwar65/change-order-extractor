@echo off
rem Starts the demo UI with the project's virtual environment.
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo No .venv found. Run activate.bat once first.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
start "" http://127.0.0.1:8000
co-extract-web
pause
