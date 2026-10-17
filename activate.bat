@echo off
rem Opens a command prompt in this folder with the project's virtual environment active.
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Creating virtual environment...
  python -m venv .venv || goto :fail
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  pip install -e ".[dev,web]" || goto :fail
) else (
  call ".venv\Scripts\activate.bat"
)
echo.
echo Virtual environment is active. Useful commands:
echo   pytest -q                                   run the tests
echo   co-extract samples\co_001_clean.txt         extract one file
echo   python -m co_extract.evaluation --corpus 1000
echo   co-extract-web                              start the demo at http://127.0.0.1:8000
echo.
cmd /k
exit /b 0
:fail
echo Setup failed. Check that Python 3.12 or newer is installed and on PATH.
pause
exit /b 1
