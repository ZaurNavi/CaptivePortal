$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-ff6-a1-formal-r3.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'

$ExpectedSha = '04ca985da6a1fa10594f7456312ff748b3e1990a6c1b3cca06e4e068beebd9db'

if (-not (Test-Path -LiteralPath $Gate)) {
    throw "F_F6_A1_R3_GATE_MISSING: $Gate"
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "PYTHON_MISSING: $Python"
}

$ActualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()

Write-Host "F_F6_A1_R3_GATE_SHA256=$ActualSha"

if ($ActualSha -ne $ExpectedSha) {
    throw "F_F6_A1_R3_GATE_SHA256_MISMATCH expected=$ExpectedSha actual=$ActualSha"
}

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-ff6-a1-formal-r3-pyc'

try {
    & $Python $Gate
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

if ($Rc -ne 0) {
    throw "F_F6_A1_R3_FORMAL_FAILED exit_code=$Rc"
}

Write-Host "F_F6_A1_R3_LAUNCHER_STATUS=PASS"
