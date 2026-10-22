$ErrorActionPreference = "Stop"
$Repo = "$env:USERPROFILE\Downloads\CaptivPortal-KB-Work"
$Patch = Join-Path $PSScriptRoot "CaptivPortal_KB_Reconciliation_2026-08-26.patch"
$Expected = "53f617b3ac0155d0d647e58e98309927f9a4d318"

Write-Host "=== KB RECONCILIATION PATCH CHECK ==="
git -C "$Repo" fetch origin main
if ($LASTEXITCODE -ne 0) { throw "STOP: git fetch failed" }

$Main = (git -C "$Repo" rev-parse origin/main).Trim()
Write-Host "origin/main: $Main"
if ($Main -ne $Expected) {
    throw "STOP: origin/main changed; patch must be rebound"
}

$Dirty = @(git -C "$Repo" status --porcelain)
if ($Dirty.Count -ne 0) {
    throw "STOP: working tree is not clean"
}

git -C "$Repo" switch main
if ($LASTEXITCODE -ne 0) { throw "STOP: cannot switch to main" }
git -C "$Repo" merge --ff-only origin/main
if ($LASTEXITCODE -ne 0) { throw "STOP: main fast-forward failed" }

$Head = (git -C "$Repo" rev-parse HEAD).Trim()
if ($Head -ne $Expected) {
    throw "STOP: local main is not exact expected baseline"
}

git -C "$Repo" apply --check "$Patch"
if ($LASTEXITCODE -ne 0) {
    throw "STOP: git apply --check failed"
}

Write-Host "PASS: patch applies cleanly to exact main"
Write-Host "NO FILES CHANGED"
