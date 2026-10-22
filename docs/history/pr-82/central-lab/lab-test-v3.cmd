@echo off
setlocal EnableExtensions
title CaptivPortal Lab - Full Test Gate v3

set "LAB_TEST_VERSION=3"
set "CLEAN=C:\CaptivPortal-UI-Preview"
set "PYTHON=C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe"
set "LOGDIR=C:\CaptivPortal-Lab\logs"
set "TMPROOT=C:\CaptivPortal-Lab\tmp"
set "PYTHONPYCACHEPREFIX=%TMPROOT%\pycache"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
if not exist "%TMPROOT%" mkdir "%TMPROOT%"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"

set "LOG=%LOGDIR%\lab-test-%STAMP%.log"
set "RUN_TMP=%TMPROOT%\run-%STAMP%"
set "PYTEST_BASETEMP=%RUN_TMP%\pytest"

mkdir "%RUN_TMP%" >nul 2>&1

set "TEMP=%RUN_TMP%"
set "TMP=%RUN_TMP%"

echo ============================================================
echo CaptivPortal Local Lab - FULL TEST GATE v%LAB_TEST_VERSION%
echo ============================================================
echo Target:
echo   %CLEAN%
echo Log:
echo   %LOG%
echo Temp:
echo   %RUN_TMP%
echo.

cd /d "%CLEAN%" || goto :error

echo [PRECHECK] Git state
git status -sb
echo.

for /f "delims=" %%A in ('git status --porcelain') do (
    echo ERROR: Clean Main contains local changes.
    echo Tests were not started.
    echo.
    git status --short
    goto :fail
)

if not exist "%PYTHON%" (
    echo ERROR: Python virtual environment was not found:
    echo %PYTHON%
    goto :fail
)

(
    echo ============================================================
    echo CaptivPortal Local Lab - FULL TEST GATE v%LAB_TEST_VERSION%
    echo Started: %DATE% %TIME%
    echo Target: %CLEAN%
    echo Temp: %RUN_TMP%
    echo ============================================================
    echo.
    git status -sb
    echo.
) > "%LOG%" 2>&1

echo [1/3] pytest ... running
echo.>>"%LOG%"
echo ===== PYTEST =====>>"%LOG%"
"%PYTHON%" -m pytest -q -rs --basetemp="%PYTEST_BASETEMP%" >> "%LOG%" 2>&1
if errorlevel 1 goto :testfail
echo       PASS

echo [2/3] compileall ... running
echo.>>"%LOG%"
echo ===== COMPILEALL =====>>"%LOG%"
"%PYTHON%" -m compileall -q app >> "%LOG%" 2>&1
if errorlevel 1 goto :testfail
echo       PASS

echo [3/3] git diff --check ... running
echo.>>"%LOG%"
echo ===== GIT DIFF CHECK =====>>"%LOG%"
git diff --check >> "%LOG%" 2>&1
if errorlevel 1 goto :testfail
echo       PASS

echo.>>"%LOG%"
echo RESULT: PASS>>"%LOG%"
echo Finished: %DATE% %TIME%>>"%LOG%"

echo.
echo ============================================================
echo PASS: FULL LOCAL TEST GATE
echo ============================================================
echo.
echo Detailed log saved to:
echo %LOG%
echo.
git status -sb
echo.
pause
exit /b 0

:testfail
echo.>>"%LOG%"
echo RESULT: FAIL>>"%LOG%"
echo Finished: %DATE% %TIME%>>"%LOG%"

echo.
echo ============================================================
echo FAIL: FULL LOCAL TEST GATE
echo ============================================================
echo.
echo Last 40 lines:
echo ------------------------------------------------------------
powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 40"
echo ------------------------------------------------------------
echo.
echo Full log:
echo %LOG%
echo.
pause
exit /b 1

:error
echo.
echo ERROR: Could not enter Clean Main:
echo %CLEAN%
echo.
pause
exit /b 1

:fail
echo.
pause
exit /b 1
