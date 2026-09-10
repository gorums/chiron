@echo off
title Course platform - tutor bridge
cd /d "%~dp0"

echo.
echo   Starting the tutor bridge for your course...
echo.

where claude >nul 2>nul
if %errorlevel%==0 (
  echo   [ok] Claude Code found - questions will use your Pro/Max plan, no API charges.
) else (
  echo   [!] Claude Code was not found on this PATH.
  echo       Install it from https://claude.com/claude-code and sign in, or use an
  echo       API key in the site's Settings instead.
)
echo.

where python >nul 2>nul
if %errorlevel%==0 (
  python tutor-bridge.py
  goto :done
)

where py >nul 2>nul
if %errorlevel%==0 (
  py tutor-bridge.py
  goto :done
)

echo.
echo   Python was not found on this computer.
echo.
echo   Install it from https://www.python.org/downloads/  (tick "Add python.exe to PATH"),
echo   then double-click this file again. Nothing else is needed - the bridge uses
echo   only what ships with Python.
echo.

:done
echo.
pause
