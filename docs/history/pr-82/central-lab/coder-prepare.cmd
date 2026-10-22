@echo off
setlocal EnableExtensions

set "WORK=C:\CaptivPortal-Lab\coder-work"
set "BASEBRANCH=coder-work"
set "FEATURE=%~1"

if "%FEATURE%"=="" (
    echo Usage:
    echo   coder-prepare.cmd feature/task-name
    echo.
    exit /b 2
)

if not exist "%WORK%\.git" (
    echo ERROR: Coder worktree not found:
    echo   %WORK%
    exit /b 1
)

cd /d "%WORK%" || exit /b 1

for /f "delims=" %%A in ('git status --porcelain') do (
    echo ERROR: coder-work contains local changes.
    echo Finish, commit, stash, or discard them before preparing a new TASK.
    echo.
    git status --short
    exit /b 1
)

echo ============================================================
echo CaptivPortal Coder Workspace - PREPARE TASK
echo ============================================================
echo Worktree:
echo   %WORK%
echo Feature branch:
echo   %FEATURE%
echo.

echo [1/5] Fetch origin
git fetch origin || exit /b 1

echo [2/5] Switch to neutral baseline branch
git switch "%BASEBRANCH%" || exit /b 1

echo [3/5] Fast-forward neutral baseline to origin/main
git merge --ff-only origin/main || exit /b 1

git show-ref --verify --quiet "refs/heads/%FEATURE%"
if not errorlevel 1 (
    echo.
    echo ERROR: Local branch already exists:
    echo   %FEATURE%
    echo Refusing to reuse it automatically.
    exit /b 1
)

git ls-remote --exit-code --heads origin "%FEATURE%" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo ERROR: Remote branch already exists:
    echo   origin/%FEATURE%
    echo Refusing to create a new TASK branch with the same name.
    exit /b 1
)

echo [4/5] Create TASK branch from exact origin/main
git switch -c "%FEATURE%" origin/main || exit /b 1

echo [5/5] Verify
echo.
echo ============================================================
echo READY: CODER TASK WORKSPACE
echo ============================================================
echo Branch:
git branch --show-current
echo.
echo HEAD:
git rev-parse HEAD
echo.
echo Status:
git status -sb
echo.
echo Origin main:
git rev-parse origin/main
echo.
echo The Coder may now modify files only in:
echo   %WORK%
echo.
exit /b 0
