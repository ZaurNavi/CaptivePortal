@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Owner-only independent TEST-GATE-PLATFORM-01/P1-v1. Never invokes/edits V7.
rem Args: PYTHON REPO HEAD TREE OUTPUT APPROVED_ENVIRONMENT_LOCK_SHA256
if "%~6"=="" exit /b 2
if not "%~7"=="" exit /b 2
set "PYTHONPATH="
set "PYTEST_ADDOPTS="
set "PYTEST_PLUGINS="
set "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1"
set "PYTHONNOUSERSITE=1"
"%~1" -I -B "%~dp0gate-preflight-v1.py" --repo "%~2" --head "%~3" --tree "%~4" --output "%~5" --run-owner-gate --launcher "%~f0" --lock-sha256 "%~6"
exit /b %errorlevel%
