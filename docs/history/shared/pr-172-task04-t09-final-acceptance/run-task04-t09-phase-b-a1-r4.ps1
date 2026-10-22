﻿$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r4-20261002.py'
$PreviousGate = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r3-20261002.py'
$PhaseARunner = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-a-r2-lock-upgrade-a1-20261002.py'
$PhaseALock = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-a-r2-upgrade-20261002T071712Z-T09-A1-01\phase-a-lock.json'
$T07Helper = 'C:\CaptivPortal-Lab\tools\task04-t07-gate-a1-20261002.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$Task01Db = 'C:\CaptivPortal-Lab\gates\task04\t07\inputs\task01-source-r2.sqlite3'

# Exact formal R3 attempt that was technically blocked before product result visibility.
$PreviousBlockedRoot = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-b-20261002T081546Z-T09-A1-R3-01'
$PreviousWorkerStdout = Join-Path $PreviousBlockedRoot 'worker-1-stdout.log'

$ExpectedGateSha = '547a882ca9737ac4c8c8ea9e12553bca16a2ee1f89d802449496033769edbffc'
$ExpectedPreviousGateSha = 'f3ceab4ed4d83bbc5e75e951a320eabd5832992999ba0aa9b3d3f431fcc93ae6'
$ExpectedPhaseARunnerSha = '8d5c0857d184dd6014287b7506b03f20f1bd181b30590a9b83cc8fb884b15d44'
$ExpectedPhaseALockSha = '1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1'
$ExpectedT07Sha = 'bbe90933dd4526f4b0cb3c1db65ada38161de0147c476a5be2105bcb7cecf9ac'
$ExpectedTask01Sha = '79cfcfb8c463c235af1d7dfe4f49a8e9ef491a25749ccbeeded85b88f2ee90f9'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'
$ExpectedProfileId = 'ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c'
$ExpectedPolicyId = 'ProductValidationPolicy:v1:sha256:806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5'

foreach ($Path in @(
    $Gate,$PreviousGate,$PhaseARunner,$PhaseALock,$T07Helper,$Python,$Repo,$FoundationDb,$Task01Db,
    $PreviousBlockedRoot,$PreviousWorkerStdout
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_B_R4_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualPreviousGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PreviousGate).Hash.ToLowerInvariant()
$ActualPhaseARunnerSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PhaseARunner).Hash.ToLowerInvariant()
$ActualPhaseALockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PhaseALock).Hash.ToLowerInvariant()
$ActualT07Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T07Helper).Hash.ToLowerInvariant()
$ActualTask01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Task01Db).Hash.ToLowerInvariant()

Write-Host "T09_PHASE_B_R4_GATE_SHA256=$ActualGateSha"
Write-Host "T09_PHASE_B_R3_GATE_SHA256=$ActualPreviousGateSha"
Write-Host "T09_PHASE_A_R2_RUNNER_SHA256=$ActualPhaseARunnerSha"
Write-Host "T09_PHASE_A_R2_LOCK_SHA256=$ActualPhaseALockSha"
Write-Host "T09_PHASE_B_R4_T07_HELPER_SHA256=$ActualT07Sha"
Write-Host "T09_PHASE_B_R4_TASK01_DB_SHA256=$ActualTask01Sha"

if ($ActualGateSha -ne $ExpectedGateSha) { throw "T09_PHASE_B_R4_GATE_SHA256_MISMATCH" }
if ($ActualPreviousGateSha -ne $ExpectedPreviousGateSha) { throw "T09_PHASE_B_R3_GATE_SHA256_MISMATCH" }
if ($ActualPhaseARunnerSha -ne $ExpectedPhaseARunnerSha) { throw "T09_PHASE_A_R2_RUNNER_SHA256_MISMATCH" }
if ($ActualPhaseALockSha -ne $ExpectedPhaseALockSha) { throw "T09_PHASE_A_R2_LOCK_SHA256_MISMATCH" }
if ($ActualT07Sha -ne $ExpectedT07Sha) { throw "T09_PHASE_B_R4_T07_HELPER_SHA256_MISMATCH" }
if ($ActualTask01Sha -ne $ExpectedTask01Sha) { throw "T09_PHASE_B_R4_TASK01_DB_SHA256_MISMATCH" }

# Preserve and classify exact R3 as a technical blocker: no result visibility.
$PreviousText = Get-Content -LiteralPath $PreviousWorkerStdout -Raw
if ($PreviousText -notmatch 'GATE_EXECUTION_STATUS=BLOCKED' -or
    $PreviousText -notmatch 'BLOCKER=snapshot_memory_pressure') {
    throw "T09_PHASE_B_R4_PREVIOUS_R3_BLOCKED_IDENTITY_MISMATCH"
}

$PreviousForbidden = @(
    Get-ChildItem -LiteralPath $PreviousBlockedRoot -Recurse -File |
    Where-Object {
        $_.Name -match '^(request|result|comparison)-' -or
        $_.Name -eq 'phase-b-lock.json' -or
        $_.Name -eq 'privacy-safe-comparison-report.json' -or
        $_.Name -eq 'worker-completion.json'
    }
)
if (($PreviousForbidden | Measure-Object).Count -ne 0) {
    throw "T09_PHASE_B_R4_PREVIOUS_R3_RESULT_VISIBILITY_DETECTED"
}

Write-Host "T09_PREVIOUS_PHASE_B_R3_BLOCKED_PRESERVED=YES"
Write-Host "T09_PREVIOUS_PHASE_B_R3_BLOCKER=snapshot_memory_pressure"
Write-Host "T09_PREVIOUS_PHASE_B_R3_RESULT_VISIBILITY=NO"
Write-Host "T09_R4_REPAIR=COMPATIBILITY_PREFLIGHT_PROCESS_ISOLATION"
Write-Host "T09_R4_SNAPSHOT_MEMORY_POLICY_CHANGED=NO"
Write-Host "T09_R4_CANDIDATE_CODE_CHANGED=NO"

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne $ExpectedCommit) { throw "T09_PHASE_B_R4_CANDIDATE_COMMIT_MISMATCH" }
if ($Tree -ne $ExpectedTree) { throw "T09_PHASE_B_R4_CANDIDATE_TREE_MISMATCH" }
if ($Status) { throw "T09_PHASE_B_R4_CANDIDATE_WORKTREE_NOT_CLEAN" }

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t09\phase-b-$Stamp-T09-A1-R4-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t09-phase-b-a1-r4-pyc'

try {
    & $Python $Gate B `
        --repo $Repo `
        --foundation-db $FoundationDb `
        --task01-db $Task01Db `
        --phase-a-lock $PhaseALock `
        --phase-a-lock-sha256 $ExpectedPhaseALockSha `
        --output $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T09_PHASE_B_R4_PROCESS_EXIT_CODE=$Rc"
Write-Host "T09_PHASE_B_R4_OUTPUT=$OutputDir"

if ($Rc -ne 0) {
    throw "T09_PHASE_B_R4_EXECUTION_FAILED exit_code=$Rc"
}

$LockPath = Join-Path $OutputDir 'phase-b-lock.json'
$ReportPath = Join-Path $OutputDir 'privacy-safe-comparison-report.json'
$CompatibilityPath = Join-Path $OutputDir 'compatibility-report.json'
$PreflightPath = Join-Path $OutputDir 'compatibility-preflight\compatibility-preflight.json'

foreach ($Path in @($LockPath,$ReportPath,$CompatibilityPath,$PreflightPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_B_R4_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
$Report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
$Compatibility = Get-Content -LiteralPath $CompatibilityPath -Raw | ConvertFrom-Json
$Preflight = Get-Content -LiteralPath $PreflightPath -Raw | ConvertFrom-Json

$LockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $LockPath).Hash.ToLowerInvariant()
$PreflightSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PreflightPath).Hash.ToLowerInvariant()

if ($Lock.phase -ne 'B') { throw "T09_PHASE_B_R4_LOCK_PHASE_MISMATCH" }
if ($Lock.candidate_commit -ne $ExpectedCommit -or $Lock.candidate_tree -ne $ExpectedTree) {
    throw "T09_PHASE_B_R4_LOCK_CANDIDATE_MISMATCH"
}
if ($Lock.runner_sha256 -ne $ExpectedGateSha -or
    $Lock.phase_b_runner_sha256 -ne $ExpectedGateSha) {
    throw "T09_PHASE_B_R4_LOCK_RUNNER_MISMATCH"
}
if ($Lock.phase_a_lock_sha256 -ne $ExpectedPhaseALockSha -or
    $Lock.phase_a_runner_sha256 -ne $ExpectedPhaseARunnerSha) {
    throw "T09_PHASE_B_R4_LOCK_PHASE_A_PROVENANCE_MISMATCH"
}
if ($Lock.state -ne 'OWNER_REVIEW_REQUIRED') {
    throw "T09_PHASE_B_R4_STATE_MISMATCH"
}

if ($Lock.compatibility_preflight.file -ne 'compatibility-preflight/compatibility-preflight.json') {
    throw "T09_PHASE_B_R4_PREFLIGHT_FILE_MISMATCH"
}
if ($Lock.compatibility_preflight.file_sha256 -ne $PreflightSha) {
    throw "T09_PHASE_B_R4_PREFLIGHT_SHA_MISMATCH"
}
if ($Lock.compatibility_preflight.runner_sha256 -ne $ExpectedGateSha) {
    throw "T09_PHASE_B_R4_PREFLIGHT_RUNNER_MISMATCH"
}
if ($Preflight.status -ne 'PASS' -or $Preflight.network_attempt_count -ne 0) {
    throw "T09_PHASE_B_R4_PREFLIGHT_STATUS_MISMATCH"
}
if ($Preflight.runner_sha256 -ne $ExpectedGateSha -or
    $Preflight.candidate_commit -ne $ExpectedCommit -or
    $Preflight.candidate_tree -ne $ExpectedTree -or
    $Preflight.phase_a_lock_sha256 -ne $ExpectedPhaseALockSha) {
    throw "T09_PHASE_B_R4_PREFLIGHT_PROVENANCE_MISMATCH"
}
if ($Preflight.profile.artifact_id -ne $ExpectedProfileId) {
    throw "T09_PHASE_B_R4_PREFLIGHT_PROFILE_MISMATCH"
}
$PreflightChecks = @($Preflight.checks)
if (($PreflightChecks | Measure-Object).Count -ne 9) {
    throw "T09_PHASE_B_R4_PREFLIGHT_CHECK_COUNT_NOT_9"
}
foreach ($Check in $PreflightChecks) {
    if ($Check.status -ne 'PASS') {
        throw "T09_PHASE_B_R4_PREFLIGHT_COMPATIBILITY_FAILURE"
    }
}

$Workers = @($Lock.worker_executions)
if (($Workers | Measure-Object).Count -ne 2) {
    throw "T09_PHASE_B_R4_WORKER_COUNT_NOT_2"
}
foreach ($Worker in $Workers) {
    if ($Worker.runner_sha256 -ne $ExpectedGateSha) {
        throw "T09_PHASE_B_R4_WORKER_RUNNER_MISMATCH"
    }
    if ($Worker.process_id -eq $Lock.compatibility_preflight.process_id) {
        throw "T09_PHASE_B_R4_PREFLIGHT_PROCESS_REUSED_AS_WORKER"
    }
}

if ($Report.state -ne 'OWNER_REVIEW_REQUIRED') { throw "T09_PHASE_B_R4_REPORT_STATE_MISMATCH" }
if ($Report.profile.artifact_id -ne $ExpectedProfileId) { throw "T09_PHASE_B_R4_REPORT_PROFILE_MISMATCH" }
if ($Report.product_validation_policy.artifact_id -ne $ExpectedPolicyId) {
    throw "T09_PHASE_B_R4_REPORT_POLICY_MISMATCH"
}
if ($Report.automatic_learning -ne $false) { throw "T09_PHASE_B_R4_AUTOMATIC_LEARNING_NOT_FALSE" }
if ($Report.production_activation -ne $false) { throw "T09_PHASE_B_R4_PRODUCTION_ACTIVATION_NOT_FALSE" }

$Entries = @($Report.entries)
if (($Entries | Measure-Object).Count -ne 2) {
    throw "T09_PHASE_B_R4_ENTRY_COUNT_NOT_2"
}

if ($Compatibility.compatibility_preflight.file_sha256 -ne $PreflightSha -or
    $Compatibility.compatibility_preflight.runner_sha256 -ne $ExpectedGateSha) {
    throw "T09_PHASE_B_R4_COMPATIBILITY_PREFLIGHT_BINDING_MISMATCH"
}
$CompatDevices = @($Compatibility.controlled_device_checks)
if (($CompatDevices | Measure-Object).Count -ne 2) {
    throw "T09_PHASE_B_R4_COMPAT_DEVICE_COUNT_NOT_2"
}
foreach ($Device in $CompatDevices) {
    $Checks = @($Device.checks)
    if (($Checks | Measure-Object).Count -ne 9) {
        throw "T09_PHASE_B_R4_COMPAT_CHECK_COUNT_NOT_9"
    }
    foreach ($Check in $Checks) {
        if ($Check.status -ne 'PASS') {
            throw "T09_PHASE_B_R4_COMPATIBILITY_FAILURE"
        }
    }
}

$Results = @()
for ($i = 1; $i -le 2; $i++) {
    $CmpPath = Join-Path $OutputDir "comparison-$i.json"
    $ResultPath = Join-Path $OutputDir "result-$i.json"
    $RequestPath = Join-Path $OutputDir "request-$i.json"

    foreach ($Path in @($CmpPath,$ResultPath,$RequestPath)) {
        if (-not (Test-Path -LiteralPath $Path)) {
            throw "T09_PHASE_B_R4_CONTROLLED_ARTIFACT_MISSING: $Path"
        }
    }

    $Cmp = Get-Content -LiteralPath $CmpPath -Raw | ConvertFrom-Json
    $Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
    $Request = Get-Content -LiteralPath $RequestPath -Raw | ConvertFrom-Json
    $Entry = $Entries[$i - 1]

    if ($Cmp.artifact_type -ne 'ProductValidationComparisonRecord') {
        throw "T09_PHASE_B_R4_COMPARISON_TYPE_MISMATCH_$i"
    }
    if ($Result.artifact_type -ne 'ClassificationResult') {
        throw "T09_PHASE_B_R4_RESULT_TYPE_MISMATCH_$i"
    }
    if ($Request.artifact_type -ne 'ClassificationRequestManifest') {
        throw "T09_PHASE_B_R4_REQUEST_TYPE_MISMATCH_$i"
    }
    if ($Cmp.artifact_id -ne $Entry.comparison.artifact_id -or
        $Result.artifact_id -ne $Entry.result.artifact_id -or
        $Request.artifact_id -ne $Entry.request.artifact_id) {
        throw "T09_PHASE_B_R4_ENTRY_ARTIFACT_BINDING_MISMATCH_$i"
    }

    $Outcomes = @($Cmp.semantic_payload.per_dimension_outcomes)
    $Platform = @($Outcomes | Where-Object { $_.dimension_name -eq 'platform_family' })[0]
    $DeviceClass = @($Outcomes | Where-Object { $_.dimension_name -eq 'device_class' })[0]

    $Results += [pscustomobject]@{
        Label = $Entry.controlled_device_lab_label
        Comparison = $Cmp.artifact_id
        ComparisonOutcome = $Cmp.semantic_payload.overall_validation_outcome
        PlatformStatus = $Platform.actual_status
        PlatformValue = $Platform.actual_value_or_ref
        PlatformSupport = $Platform.support_level
        PlatformComparison = $Platform.comparison_outcome
        DeviceClassStatus = $DeviceClass.actual_status
        DeviceClassValue = $DeviceClass.actual_value_or_ref
        DeviceClassSupport = $DeviceClass.support_level
        DeviceClassComparison = $DeviceClass.comparison_outcome
    }
}

$Android = @($Results | Where-Object { $_.Label -eq 'OWNER_ANDROID' })
$Windows = @($Results | Where-Object { $_.Label -eq 'OWNER_WINDOWS_LAPTOP' })

if (($Android | Measure-Object).Count -ne 1 -or ($Windows | Measure-Object).Count -ne 1) {
    throw "T09_PHASE_B_R4_CONTROLLED_DEVICE_LABEL_SET_MISMATCH"
}

Write-Host ""
Write-Host "T09_COMPATIBILITY_PREFLIGHT_STATUS=PASS"
Write-Host "T09_COMPATIBILITY_PREFLIGHT_SHA256=$PreflightSha"
Write-Host "T09_COMPATIBILITY_PREFLIGHT_PROCESS_ID=$($Lock.compatibility_preflight.process_id)"
foreach ($Row in $Results) {
    Write-Host "T09_DEVICE=$($Row.Label)"
    Write-Host "  COMPARISON_OUTCOME=$($Row.ComparisonOutcome)"
    Write-Host "  PLATFORM=$($Row.PlatformStatus)|$($Row.PlatformValue)|$($Row.PlatformSupport)|$($Row.PlatformComparison)"
    Write-Host "  DEVICE_CLASS=$($Row.DeviceClassStatus)|$($Row.DeviceClassValue)|$($Row.DeviceClassSupport)|$($Row.DeviceClassComparison)"
    Write-Host "  COMPARISON_ID=$($Row.Comparison)"
}

Write-Host ""
Write-Host "T09_PHASE_B_R4_LAUNCHER_STATUS=PASS"
Write-Host "T09_PHASE_B_EXECUTED=YES"
Write-Host "T09_PHASE_B_STATUS=OWNER_REVIEW_REQUIRED"
Write-Host "T09_PHASE_B_POLICY_OUTCOME=$($Report.policy_outcome)"
Write-Host "T09_PHASE_B_CORRECT_DEVICE_CLASS_COUNT=$($Report.correct_device_class_count)"
Write-Host "T09_PHASE_B_WORKER_COUNT=$(($Workers | Measure-Object).Count)"
Write-Host "T09_PHASE_B_AUTOMATIC_LEARNING=NO"
Write-Host "T09_PHASE_B_PRODUCTION_ACTIVATION=NO"
Write-Host "T09_PHASE_B_LOCK_PATH=$LockPath"
Write-Host "T09_PHASE_B_LOCK_SHA256=$LockSha"
