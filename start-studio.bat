@echo off
title Course Studio
cd /d "%~dp0"
echo.
echo   Starting Course Studio...
echo   Leave this window open while you use it.
echo.
python "%~dp0platform/build.py" studio
if errorlevel 1 (
  echo.
  echo   Could not start. Check that Python is installed and on your PATH,
  echo   and that 'pip install markdown' has been run.
  pause
)
