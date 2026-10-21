$ErrorActionPreference = 'Stop'

$Repair = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-a-r2-lock-upgrade-a1-20261002.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$SourceLock = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-a-20261002T064012Z-T09-A1-01\phase-a-lock.json'
$BlockedPhaseB = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-b-20261002T070912Z-T09-A1-01'

$ExpectedRepairSha = '8d5c0857d184dd6014287b7506b03f20f1bd181b30590a9b83cc8fb884b15d44'
$ExpectedSourceLockSha = '6bbd4d03fe694c8a4a2cf9caef8ab79c8659bab42105a1e8a8e86df3298ac4a7'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'

foreach ($Path in @($Repair,$Python,$Repo,$SourceLock,$BlockedPhaseB)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_A_REPAIR_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualRepairSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Repair).Hash.ToLowerInvariant()
$ActualSourceLockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceLock).Hash.ToLowerInvariant()

Write-Host "T09_PHASE_A_REPAIR_RUNNER_SHA256=$ActualRepairSha"
Write-Host "T09_SOURCE_PHASE_A_LOCK_SHA256=$ActualSourceLockSha"

if ($ActualRepairSha -ne $ExpectedRepairSha) {
    throw "T09_PHASE_A_REPAIR_RUNNER_SHA256_MISMATCH"
}
if ($ActualSourceLockSha -ne $ExpectedSourceLockSha) {
    throw "T09_SOURCE_PHASE_A_LOCK_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne $ExpectedCommit) { throw "T09_PHASE_A_REPAIR_CANDIDATE_COMMIT_MISMATCH" }
if ($Tree -ne $ExpectedTree) { throw "T09_PHASE_A_REPAIR_CANDIDATE_TREE_MISMATCH" }
if ($Status) { throw "T09_PHASE_A_REPAIR_CANDIDATE_WORKTREE_NOT_CLEAN" }

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t09\phase-a-r2-upgrade-$Stamp-T09-A1-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t09-phase-a-r2-upgrade-pyc'

try {
    & $Python $Repair `
        --repo $Repo `
        --source-phase-a-lock $SourceLock `
        --source-phase-a-lock-sha256 $ExpectedSourceLockSha `
        --blocked-phase-b-output $BlockedPhaseB `
        --output $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T09_PHASE_A_REPAIR_PROCESS_EXIT_CODE=$Rc"
Write-Host "T09_PHASE_A_REPAIR_OUTPUT=$OutputDir"

if ($Rc -ne 0) {
    throw "T09_PHASE_A_REPAIR_FAILED exit_code=$Rc"
}

$NewLockPath = Join-Path $OutputDir 'phase-a-lock.json'
if (-not (Test-Path -LiteralPath $NewLockPath)) {
    throw "T09_PHASE_A_REPAIRED_LOCK_MISSING"
}

$NewLock = Get-Content -LiteralPath $NewLockPath -Raw | ConvertFrom-Json
$NewLockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $NewLockPath).Hash.ToLowerInvariant()

if ($NewLock.phase -ne 'A') { throw "T09_PHASE_A_REPAIRED_LOCK_PHASE_MISMATCH" }
if ($NewLock.candidate_commit -ne $ExpectedCommit -or $NewLock.candidate_tree -ne $ExpectedTree) {
    throw "T09_PHASE_A_REPAIRED_LOCK_CANDIDATE_MISMATCH"
}
if ($NewLock.runner_sha256 -ne $ExpectedRepairSha) {
    throw "T09_PHASE_A_REPAIRED_LOCK_RUNNER_MISMATCH"
}
if ($NewLock.source_phase_a_lock_sha256 -ne $ExpectedSourceLockSha) {
    throw "T09_PHASE_A_REPAIRED_LOCK_PARENT_MISMATCH"
}
if ($NewLock.blocked_phase_b_pre_result_verified -ne $true) {
    throw "T09_PHASE_A_REPAIRED_LOCK_PRE_RESULT_PROOF_MISSING"
}

$Registrations = @($NewLock.ground_truth_registrations)
if (($Registrations | Measure-Object).Count -ne 2) {
    throw "T09_PHASE_A_REPAIRED_REGISTRATION_COUNT_NOT_2"
}

foreach ($Index in 1..2) {
    $Gt = Join-Path $OutputDir "ground-truth-$Index.json"
    $Reg = Join-Path $OutputDir "ground-truth-registration-$Index.json"
    if (-not (Test-Path -LiteralPath $Gt) -or -not (Test-Path -LiteralPath $Reg)) {
        throw "T09_PHASE_A_REPAIRED_REQUIRED_MEMBER_MISSING_$Index"
    }
}

Write-Host ""
Write-Host "T09_PHASE_A_REPAIR_LAUNCHER_STATUS=PASS"
Write-Host "T09_PHASE_A_REPAIR_STATUS=GROUND_TRUTH_LOCK_UPGRADED_PRE_RESULT"
Write-Host "T09_PHASE_A_ORIGINAL_LOCK_PRESERVED=YES"
Write-Host "T09_PHASE_A_GROUND_TRUTH_BYTES_PRESERVED=YES"
Write-Host "T09_PHASE_A_RESULT_VISIBILITY_BEFORE_UPGRADE=NO"
Write-Host "T09_PHASE_A_R2_REGISTRATION_COUNT=2"
Write-Host "T09_PHASE_A_R2_LOCK_PATH=$NewLockPath"
Write-Host "T09_PHASE_A_R2_LOCK_SHA256=$NewLockSha"
Write-Host "T09_PHASE_A_R2_RUNNER_SHA256=$ExpectedRepairSha"
Write-Host "OWNER_DECISION_REQUIRED=NO_AT_PHASE_A"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T09_PHASE_B_REBIND_TO_R2_LOCK"
