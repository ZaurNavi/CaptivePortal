$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t02-gate-a1-20261001.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$ExpectedSha = '96bc6842e42507a46e4b1f4b8bf5f3811a04a6db58dc321e84c570e1b7a500f0'

if (-not (Test-Path -LiteralPath $Gate)) {
    throw "T02_A1_GATE_MISSING: $Gate"
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "PYTHON_MISSING: $Python"
}

if (-not (Test-Path -LiteralPath $Repo)) {
    throw "A1_REPOSITORY_MISSING: $Repo"
}

if (-not (Test-Path -LiteralPath $FoundationDb)) {
    throw "FOUNDATION_CONTROL_DB_MISSING: $FoundationDb"
}

$ActualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
Write-Host "T02_A1_GATE_SHA256=$ActualSha"

if ($ActualSha -ne $ExpectedSha) {
    throw "T02_A1_GATE_SHA256_MISMATCH expected=$ExpectedSha actual=$ActualSha"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne '8a39459be3ce7ed40e325736034245f0025cf249') {
    throw "T02_A1_CANDIDATE_COMMIT_MISMATCH"
}

if ($Tree -ne 'e2521f27c9f91978e381bce202ab3e3c83aa6dad') {
    throw "T02_A1_CANDIDATE_TREE_MISMATCH"
}

if ($Status) {
    throw "T02_A1_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t02\official-run-$Stamp-T02-A1-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t02-a1-pyc'

try {
    & $Python $Gate `
        --repo $Repo `
        --foundation-control-db $FoundationDb `
        --output-dir $OutputDir

    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T02_PROCESS_EXIT_CODE=$Rc"
Write-Host "T02_OUTPUT_ROOT=$OutputDir"

if ($Rc -ne 0) {
    throw "T02_A1_FORMAL_FAILED exit_code=$Rc"
}

Write-Host "T02_A1_LAUNCHER_STATUS=PASS"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-03"
