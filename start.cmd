@echo off
setlocal
where py >nul 2>nul
if errorlevel 1 goto missing
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    py -3.12 "%~dp0run.py" %*
    goto finished
)
py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    py -3.11 "%~dp0run.py" %*
    goto finished
)
:missing
echo Install Python 3.12 ^(64-bit^) from python.org, including the Python launcher.
pause
exit /b 1
:finished
if errorlevel 1 pause
