$ErrorActionPreference = 'Stop'

# DIAGNOSTIC ONLY.
# Proves process isolation between the heavyweight T-06A 9/9 compatibility preflight
# and the memory-guarded normal RequestAssembly path. PRECHECK and WORKER are separate
# fresh -I -B Python processes. The compatibility report is canonical, SHA-bound, and
# re-verified by WORKER against the same commit/tree/profile/foundation/Phase-A lock.
# The real 96 MiB guard is unchanged. Stops BEFORE store.persist().
# It does NOT execute formal T-09 Phase B/C and does NOT create formal gate artifacts.

$FormalGate = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r3-20261002.py'
$Diag = 'C:\CaptivPortal-Lab\tools\t09-r3-compat-isolation-diag-v4.py'
$PhaseARunner = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-a-r2-lock-upgrade-a1-20261002.py'
$PhaseALock = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-a-r2-upgrade-20261002T071712Z-T09-A1-01\phase-a-lock.json'
$T07Helper = 'C:\CaptivPortal-Lab\tools\task04-t07-gate-a1-20261002.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$Task01Db = 'C:\CaptivPortal-Lab\gates\task04\t07\inputs\task01-source-r2.sqlite3'

$ExpectedFormalGateSha = 'f3ceab4ed4d83bbc5e75e951a320eabd5832992999ba0aa9b3d3f431fcc93ae6'
$ExpectedDiagSha = 'a8e6948572850c72774d20bad1e752df9d195f30972ed3754799165039d551b1'
$ExpectedPhaseARunnerSha = '8d5c0857d184dd6014287b7506b03f20f1bd181b30590a9b83cc8fb884b15d44'
$ExpectedPhaseALockSha = '1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1'
$ExpectedT07Sha = 'bbe90933dd4526f4b0cb3c1db65ada38161de0147c476a5be2105bcb7cecf9ac'
$ExpectedTask01Sha = '79cfcfb8c463c235af1d7dfe4f49a8e9ef491a25749ccbeeded85b88f2ee90f9'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'

foreach ($Path in @(
    $FormalGate,$Diag,$PhaseARunner,$PhaseALock,$T07Helper,$Python,$Repo,$FoundationDb,$Task01Db
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_MEMDIAG_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualFormalGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $FormalGate).Hash.ToLowerInvariant()
$ActualDiagSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Diag).Hash.ToLowerInvariant()
$ActualPhaseARunnerSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PhaseARunner).Hash.ToLowerInvariant()
$ActualPhaseALockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PhaseALock).Hash.ToLowerInvariant()
$ActualT07Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T07Helper).Hash.ToLowerInvariant()
$ActualTask01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Task01Db).Hash.ToLowerInvariant()
$ActualFoundationSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $FoundationDb).Hash.ToLowerInvariant()

Write-Host "FORMAL_GATE_SHA256=$ActualFormalGateSha"
Write-Host "DIAGNOSTIC_RUNNER_SHA256=$ActualDiagSha"
Write-Host "PHASE_A_RUNNER_SHA256=$ActualPhaseARunnerSha"
Write-Host "PHASE_A_LOCK_SHA256=$ActualPhaseALockSha"
Write-Host "T07_HELPER_SHA256=$ActualT07Sha"
Write-Host "SOURCE_FOUNDATION_SHA256=$ActualFoundationSha"
Write-Host "SOURCE_TASK01_SHA256=$ActualTask01Sha"

if ($ActualFormalGateSha -ne $ExpectedFormalGateSha) { throw "FORMAL_GATE_SHA256_MISMATCH" }
if ($ActualDiagSha -ne $ExpectedDiagSha) { throw "DIAGNOSTIC_RUNNER_SHA256_MISMATCH" }
if ($ActualPhaseARunnerSha -ne $ExpectedPhaseARunnerSha) { throw "PHASE_A_RUNNER_SHA256_MISMATCH" }
if ($ActualPhaseALockSha -ne $ExpectedPhaseALockSha) { throw "PHASE_A_LOCK_SHA256_MISMATCH" }
if ($ActualT07Sha -ne $ExpectedT07Sha) { throw "T07_HELPER_SHA256_MISMATCH" }
if ($ActualTask01Sha -ne $ExpectedTask01Sha) { throw "TASK01_SOURCE_SHA256_MISMATCH" }

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain
Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"
Write-Host "CANDIDATE_WORKTREE_CLEAN=$([string]::IsNullOrWhiteSpace(($Status -join '')))"

if ($Commit -ne $ExpectedCommit) { throw "CANDIDATE_COMMIT_MISMATCH" }
if ($Tree -ne $ExpectedTree) { throw "CANDIDATE_TREE_MISMATCH" }
if ($Status) { throw "CANDIDATE_WORKTREE_NOT_CLEAN" }

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$Root = "C:\CaptivPortal-Lab\diagnostics\t09\r3-compat-isolation-$Stamp"
$ParentDir = Join-Path $Root 'parent-inputs'
$PrecheckDir = Join-Path $Root 'compat-precheck'
$PrecheckLog = Join-Path $Root 'compat-precheck-console.log'
$WorkerDir = Join-Path $Root 'worker-1'
$WorkerLog = Join-Path $Root 'worker-1-console.log'

New-Item -ItemType Directory -Path $Root | Out-Null

# First process: create the same consolidated DELETE-journal parent snapshots
# that formal Phase B passes to a fresh worker. This process then exits.
& $Python -I -B $Diag PREPARE `
    --repo $Repo `
    --foundation-db $FoundationDb `
    --task01-db $Task01Db `
    --output $ParentDir
$PrepRc = $LASTEXITCODE
Write-Host "PREPARE_PROCESS_EXIT_CODE=$PrepRc"
if ($PrepRc -ne 0) { throw "T09_MEMDIAG_PREPARE_FAILED exit_code=$PrepRc" }

$ParentFoundation = Join-Path $ParentDir 'foundation-snapshot.sqlite3'
$ParentTask01 = Join-Path $ParentDir 'task01-snapshot.sqlite3'
foreach ($Path in @($ParentFoundation,$ParentTask01)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_MEMDIAG_PREPARED_INPUT_MISSING: $Path"
    }
}

$ParentFoundationSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ParentFoundation).Hash.ToLowerInvariant()
$ParentTask01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ParentTask01).Hash.ToLowerInvariant()
Write-Host "PARENT_FOUNDATION_SHA256=$ParentFoundationSha"
Write-Host "PARENT_TASK01_SHA256=$ParentTask01Sha"

# Second process: exact heavyweight 9/9 compatibility preflight in its own fresh process.
$PrecheckArgs = @(
    '-I','-B',$Diag,'PRECHECK',
    '--repo',$Repo,
    '--foundation-db',$ParentFoundation,
    '--output',$PrecheckDir,
    '--phase-a-lock',$PhaseALock,
    '--phase-a-lock-sha256',$ExpectedPhaseALockSha,
    '--runner-sha256',$ActualDiagSha
)

& $Python @PrecheckArgs 2>&1 | Tee-Object -FilePath $PrecheckLog
$PrecheckRc = $LASTEXITCODE
Write-Host "COMPATIBILITY_PREFLIGHT_PROCESS_EXIT_CODE=$PrecheckRc"
if ($PrecheckRc -ne 0) { throw "T09_COMPAT_PREFLIGHT_FAILED exit_code=$PrecheckRc" }

$CompatibilityReport = Join-Path $PrecheckDir 'compatibility-preflight.json'
if (-not (Test-Path -LiteralPath $CompatibilityReport)) {
    throw "T09_COMPAT_PREFLIGHT_REPORT_MISSING: $CompatibilityReport"
}
$CompatibilityReportSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $CompatibilityReport).Hash.ToLowerInvariant()
Write-Host "COMPATIBILITY_PREFLIGHT_REPORT=$CompatibilityReport"
Write-Host "COMPATIBILITY_PREFLIGHT_SHA256=$CompatibilityReportSha"

# Third process: normal memory-guarded RequestAssembly worker. It verifies the retained
# compatibility preflight report but does not rerun the heavyweight compatibility routine
# in this process. No GC/working-set trimming and no guard/policy changes are permitted.
$WorkerArgs = @(
    '-I','-B',$Diag,'WORKER',
    '--repo',$Repo,
    '--foundation-db',$ParentFoundation,
    '--task01-db',$ParentTask01,
    '--output',$WorkerDir,
    '--phase-a-lock',$PhaseALock,
    '--phase-a-lock-sha256',$ExpectedPhaseALockSha,
    '--device-label','OWNER_ANDROID',
    '--runner-sha256',$ActualDiagSha,
    '--parent-foundation-sha256',$ParentFoundationSha,
    '--parent-task01-sha256',$ParentTask01Sha,
    '--compatibility-report',$CompatibilityReport,
    '--compatibility-report-sha256',$CompatibilityReportSha
)

& $Python @WorkerArgs 2>&1 | Tee-Object -FilePath $WorkerLog
$Rc = $LASTEXITCODE

Write-Host "T09_MEMDIAG_PROCESS_EXIT_CODE=$Rc"
Write-Host "T09_MEMDIAG_ROOT=$Root"
Write-Host "T09_COMPAT_PREFLIGHT_LOG=$PrecheckLog"
Write-Host "T09_MEMDIAG_LOG=$WorkerLog"
Write-Host "T09_FORMAL_PHASE_B_RERUN=NO"
Write-Host "PRODUCTION_ACTION=NO"

if ($Rc -ne 0 -and $Rc -ne 2) {
    throw "T09_MEMDIAG_ABNORMAL_EXIT exit_code=$Rc"
}

# Exit 0 = assembly succeeded under the real guard.
# Exit 2 = diagnostic blocker (expected/valid outcome if snapshot_memory_pressure reproduces).
exit $Rc
