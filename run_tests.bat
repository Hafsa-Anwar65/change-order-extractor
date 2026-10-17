@echo off
rem Runs tests, lint, type check and the evaluation inside the virtual environment.
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo No .venv found. Run activate.bat once first.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
pytest -q || goto :done
ruff check . || goto :done
ruff format --check . || goto :done
mypy || goto :done
python -m co_extract.evaluation --corpus 300
:done
pause
