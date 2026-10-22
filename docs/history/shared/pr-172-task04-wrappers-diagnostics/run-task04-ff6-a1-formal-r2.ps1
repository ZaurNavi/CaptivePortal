$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-ff6-a1-formal-r2.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'

$ExpectedSha = '39538960cf4793636d9ad905f9a8c3e7a51ee48770c9b10bc8c87c6a4c8bd7de'

if (-not (Test-Path -LiteralPath $Gate)) {
    throw "F_F6_A1_R2_GATE_MISSING: $Gate"
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "PYTHON_MISSING: $Python"
}

$ActualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()

Write-Host "F_F6_A1_R2_GATE_SHA256=$ActualSha"

if ($ActualSha -ne $ExpectedSha) {
    throw "F_F6_A1_R2_GATE_SHA256_MISMATCH expected=$ExpectedSha actual=$ActualSha"
}

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-ff6-a1-formal-r2-pyc'

try {
    & $Python $Gate
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

if ($Rc -ne 0) {
    throw "F_F6_A1_R2_FORMAL_FAILED exit_code=$Rc"
}

Write-Host "F_F6_A1_R2_LAUNCHER_STATUS=PASS"
