chcp 65001
@echo off

SET CURDIR=%~dp0
SET CURDRIVE=%CURDIR:~0,2%

%CURDRIVE%
CD %CURDIR%

for /f "tokens=* USEBACKQ" %%a in (`python --version`) DO (
SET PV=%%a
)
)
SET PV=%PV:~0,8%
CLS
IF NOT "%PV%" == "Python 3" (
ECHO Python 3.x not found
ECHO Please install python
ECHO.
pause
start https://www.python.org/downloads/
exit
)

TITLE VLIVE-BACKUP-BOT
mode con: cols=60 lines=9
CLS

echo.
echo ======================VLIVE-BACKUP-BOT======================
echo.
echo.
echo                            LOADING...
echo.
echo.
echo ============================================================

IF EXIST venv (
rmdir /S /Q venv
)

python -m venv venv

venv\Scripts\python -m pip install -q -q -q --upgrade pip
venv\Scripts\python -m pip install -q -q -q -r requirements.txt


CLS
mode con: cols=150 lines=50
venv\Scripts\python core_en.py
PAUSE
