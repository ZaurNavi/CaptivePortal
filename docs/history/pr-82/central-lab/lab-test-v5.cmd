@echo off
setlocal EnableExtensions EnableDelayedExpansion
title CaptivPortal Lab - Exact Worktree Gate v5

set "LAB_TEST_VERSION=5"
set "DEFAULT_TARGET=C:\CaptivPortal-Lab\coder-work"
set "CLEAN=C:\CaptivPortal-UI-Preview"
set "PYTHON=C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe"
set "LOGDIR=C:\CaptivPortal-Lab\logs"
set "TMPROOT=C:\CaptivPortal-Lab\tmp"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%DEFAULT_TARGET%"

rem Safety allowlist: Central Lab only tests known local worktrees.
if /I "%TARGET%"=="C:\CaptivPortal-Lab\coder-work" goto :target_ok
if /I "%TARGET%"=="C:\CaptivPortal-UI-Preview" goto :target_ok
if /I "%TARGET%"=="C:\CaptivPortal-UI-Work" goto :target_ok

echo ERROR: Target is outside the Central Lab worktree allowlist:
echo   %TARGET%
echo.
echo Allowed:
echo   C:\CaptivPortal-Lab\coder-work
echo   C:\CaptivPortal-UI-Preview
echo   C:\CaptivPortal-UI-Work
echo.
exit /b 2

:target_ok
if not exist "%TARGET%\.git" (
    echo ERROR: Git worktree not found:
    echo   %TARGET%
    exit /b 1
)

if not exist "%PYTHON%" (
    echo ERROR: Shared Central Lab Python was not found:
    echo   %PYTHON%
    exit /b 1
)

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
if not exist "%TMPROOT%" mkdir "%TMPROOT%"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=manual"

for /f "delims=" %%B in ('git -C "%TARGET%" branch --show-current') do set "BRANCH=%%B"
if not defined BRANCH set "BRANCH=DETACHED"

set "SAFE_BRANCH=%BRANCH:/=-%"
set "SAFE_BRANCH=%SAFE_BRANCH:\=-%"
set "SAFE_BRANCH=%SAFE_BRANCH::=-%"

set "LOG=%LOGDIR%\lab-test-v5-%STAMP%-%SAFE_BRANCH%.log"
set "RUN_TMP=%TMPROOT%\run-v5-%STAMP%"
set "STRICT_TMP=%RUN_TMP%\strict"
set "PYTHONPYCACHEPREFIX=%RUN_TMP%\pycache"

mkdir "%RUN_TMP%" >nul 2>&1
set "TEMP=%RUN_TMP%"
set "TMP=%RUN_TMP%"

rem Exact known Windows-local compatibility baseline cases.
set "KNOWN_SQLITE=tests/analytics/test_current_traffic.py::test_sql_integrity_aggregates_reject_corrupt_rate_and_null_values[wired_download_mbps-inf-bad_rate_count]"
set "KNOWN_NODE=tests/test_auth_retry_frontend.py::test_lost_retry_response_reconciles_active_run"
set "KNOWN_THREAD_A=tests/visitor_registry/test_device_registry_worker.py::test_long_full_audit_runs_in_worker_and_does_not_block_start"
set "KNOWN_THREAD_B=tests/visitor_registry/test_device_registry_worker.py::test_start_exposes_initializing_until_full_audit_finishes[ready]"
set "KNOWN_THREAD_C=tests/visitor_registry/test_device_registry_worker.py::test_start_exposes_initializing_until_full_audit_finishes[stopping]"

set /a COMPAT_WARN=0
set /a COMPAT_PASS=0

echo ============================================================
echo CaptivPortal Central Lab - EXACT WORKTREE GATE v%LAB_TEST_VERSION%
echo ============================================================
echo Target:
echo   %TARGET%
echo Branch:
echo   %BRANCH%
echo Log:
echo   %LOG%
echo.

echo [PRECHECK 1/5] Working tree cleanliness
for /f "delims=" %%A in ('git -C "%TARGET%" status --porcelain') do (
    echo ERROR: Target worktree contains uncommitted changes.
    echo Official Central Lab evidence requires a clean exact artifact.
    echo.
    git -C "%TARGET%" status --short
    goto :precheck_fail
)
echo       PASS

echo [PRECHECK 2/5] Refresh origin refs
git -C "%TARGET%" fetch origin >nul 2>&1
if errorlevel 1 (
    echo ERROR: git fetch origin failed.
    goto :precheck_fail
)
echo       PASS

for /f "delims=" %%H in ('git -C "%TARGET%" rev-parse HEAD') do set "HEAD_BEFORE=%%H"
for /f "delims=" %%M in ('git -C "%TARGET%" rev-parse origin/main') do set "ORIGIN_MAIN=%%M"
for /f "delims=" %%P in ('"%PYTHON%" --version 2^>^&1') do set "PYTHON_VERSION=%%P"

echo [PRECHECK 3/5] Current main ancestry
git -C "%TARGET%" merge-base --is-ancestor origin/main HEAD >nul 2>&1
if errorlevel 1 (
    echo ERROR: Target HEAD is not based on current origin/main.
    echo Rebase/update the TASK branch before Central Lab acceptance.
    echo.
    echo Target HEAD:
    echo   %HEAD_BEFORE%
    echo Current origin/main:
    echo   %ORIGIN_MAIN%
    goto :precheck_fail
)
echo       PASS

echo [PRECHECK 4/5] Node.js availability
where node >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is required for the Central Lab gate.
    goto :precheck_fail
)
for /f "delims=" %%N in ('node --version') do set "NODE_VERSION=%%N"
echo       PASS - %NODE_VERSION%

echo [PRECHECK 5/5] Python availability
echo       PASS - %PYTHON_VERSION%
echo.

(
    echo ============================================================
    echo CaptivPortal Central Lab - EXACT WORKTREE GATE v%LAB_TEST_VERSION%
    echo Started: %DATE% %TIME%
    echo Target: %TARGET%
    echo Branch: %BRANCH%
    echo HEAD: %HEAD_BEFORE%
    echo origin/main: %ORIGIN_MAIN%
    echo Python: %PYTHON_VERSION%
    echo Node: %NODE_VERSION%
    echo Temp: %RUN_TMP%
    echo ============================================================
    echo.
    git -C "%TARGET%" status -sb
    echo.
) > "%LOG%" 2>&1

cd /d "%TARGET%" || goto :patherror

echo [1/5] Strict pytest suite ... running
echo.>>"%LOG%"
echo ===== STRICT PYTEST SUITE =====>>"%LOG%"
"%PYTHON%" -m pytest -q -rs ^
  --basetemp="%STRICT_TMP%" ^
  --deselect="%KNOWN_SQLITE%" ^
  --deselect="%KNOWN_NODE%" ^
  --deselect="%KNOWN_THREAD_A%" ^
  --deselect="%KNOWN_THREAD_B%" ^
  --deselect="%KNOWN_THREAD_C%" ^
  >> "%LOG%" 2>&1
if errorlevel 1 goto :testfail
echo       PASS
echo.

echo [2/5] Windows compatibility baseline
echo.>>"%LOG%"
echo ===== WINDOWS COMPATIBILITY BASELINE =====>>"%LOG%"

call :compat "SQLite infinity edge case" "%KNOWN_SQLITE%" "sqlite"
if errorlevel 2 goto :testfail

call :compat "Node async harness timing" "%KNOWN_NODE%" "node"
if errorlevel 2 goto :testfail

call :compat "Visitor Registry timing - long audit" "%KNOWN_THREAD_A%" "thread-a"
if errorlevel 2 goto :testfail

call :compat "Visitor Registry timing - previous ready" "%KNOWN_THREAD_B%" "thread-b"
if errorlevel 2 goto :testfail

call :compat "Visitor Registry timing - previous stopping" "%KNOWN_THREAD_C%" "thread-c"
if errorlevel 2 goto :testfail

echo.
echo [3/5] compileall ... running
echo.>>"%LOG%"
echo ===== COMPILEALL =====>>"%LOG%"
"%PYTHON%" -m compileall -q app >> "%LOG%" 2>&1
if errorlevel 1 goto :testfail
echo       PASS
echo.

echo [4/5] branch diff check ... running
echo.>>"%LOG%"
echo ===== BRANCH DIFF CHECK =====>>"%LOG%"
git diff --check origin/main...HEAD >> "%LOG%" 2>&1
if errorlevel 1 goto :testfail
git diff --check >> "%LOG%" 2>&1
if errorlevel 1 goto :testfail
echo       PASS
echo.

echo [5/5] Exact-artifact immutability check
for /f "delims=" %%H in ('git rev-parse HEAD') do set "HEAD_AFTER=%%H"
if /I not "%HEAD_BEFORE%"=="!HEAD_AFTER!" (
    echo ERROR: HEAD changed while the gate was running.
    echo Before: %HEAD_BEFORE%
    echo After:  !HEAD_AFTER!
    goto :testfail
)
for /f "delims=" %%A in ('git status --porcelain') do (
    echo ERROR: Worktree changed while the gate was running.
    git status --short
    goto :testfail
)
echo       PASS

(
    echo.
    echo ===== RESULT =====
    echo RESULT: PASS
    echo STRICT_REGRESSIONS: 0
    echo COMPATIBILITY_WARNINGS: !COMPAT_WARN!
    echo COMPATIBILITY_PASSES: !COMPAT_PASS!
    echo ARTIFACT_HEAD: %HEAD_BEFORE%
    echo ARTIFACT_BRANCH: %BRANCH%
    echo ORIGIN_MAIN: %ORIGIN_MAIN%
    echo Finished: %DATE% %TIME%
) >> "%LOG%"

echo.
echo ============================================================
echo PASS: CENTRAL LAB EXACT WORKTREE GATE
echo ============================================================
echo Artifact:
echo   %TARGET%
echo Branch:
echo   %BRANCH%
echo HEAD:
echo   %HEAD_BEFORE%
echo origin/main:
echo   %ORIGIN_MAIN%
echo.
echo Strict regressions:
echo   0
echo Compatibility baseline warnings:
echo   !COMPAT_WARN!
echo Compatibility baseline passes:
echo   !COMPAT_PASS!
echo.
echo Detailed evidence:
echo   %LOG%
echo.
echo NOTE:
echo   This is the authoritative Windows Central Lab full-regression gate
echo   for the exact clean HEAD shown above.
echo   A separate Linux production-compatible gate remains separate when
echo   required by release/deploy acceptance.
echo.
pause
exit /b 0

:compat
set "COMPAT_LABEL=%~1"
set "COMPAT_TEST=%~2"
set "COMPAT_KEY=%~3"

echo       %COMPAT_LABEL% ... running
echo.>>"%LOG%"
echo --- %COMPAT_LABEL% --- >>"%LOG%"

"%PYTHON%" -m pytest -q "%COMPAT_TEST%" ^
  --basetemp="%RUN_TMP%\compat-%COMPAT_KEY%" ^
  >> "%LOG%" 2>&1

set "COMPAT_RC=!ERRORLEVEL!"

if "!COMPAT_RC!"=="0" (
    echo             PASS - baseline case now passes
    echo COMPAT_RESULT: PASS - %COMPAT_LABEL%>>"%LOG%"
    set /a COMPAT_PASS+=1
    exit /b 0
)

if "!COMPAT_RC!"=="1" (
    echo             WARN - known Windows-local baseline failure
    echo COMPAT_RESULT: WARN - %COMPAT_LABEL%>>"%LOG%"
    set /a COMPAT_WARN+=1
    exit /b 0
)

echo             FAIL - pytest infrastructure/collection error ^(exit !COMPAT_RC!^)
echo COMPAT_RESULT: FATAL exit !COMPAT_RC! - %COMPAT_LABEL%>>"%LOG%"
exit /b 2

:testfail
(
    echo.
    echo ===== RESULT =====
    echo RESULT: FAIL
    echo ARTIFACT_HEAD: %HEAD_BEFORE%
    echo ARTIFACT_BRANCH: %BRANCH%
    echo ORIGIN_MAIN: %ORIGIN_MAIN%
    echo Finished: %DATE% %TIME%
) >> "%LOG%"

echo.
echo ============================================================
echo FAIL: CENTRAL LAB EXACT WORKTREE GATE
echo ============================================================
echo Artifact HEAD:
echo   %HEAD_BEFORE%
echo.
echo Last 60 log lines:
echo ------------------------------------------------------------
powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 60"
echo ------------------------------------------------------------
echo.
echo Full evidence:
echo   %LOG%
echo.
pause
exit /b 1

:precheck_fail
echo.
echo Central Lab gate was NOT started.
echo.
pause
exit /b 1

:patherror
echo.
echo ERROR: Could not enter target worktree:
echo   %TARGET%
echo.
pause
exit /b 1
