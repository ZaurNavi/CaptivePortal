$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r2-20261002.py'
$PhaseARunner = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-a-r2-lock-upgrade-a1-20261002.py'
$PhaseALock = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-a-r2-upgrade-20261002T071712Z-T09-A1-01\phase-a-lock.json'
$T07Helper = 'C:\CaptivPortal-Lab\tools\task04-t07-gate-a1-20261002.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$Task01Db = 'C:\CaptivPortal-Lab\gates\task04\t07\inputs\task01-source-r2.sqlite3'

$ExpectedGateSha = 'fceb54dc653978f8aaaa9720ab9441c844748c971ff40e5920046563da1df1c8'
$ExpectedPhaseARunnerSha = '8d5c0857d184dd6014287b7506b03f20f1bd181b30590a9b83cc8fb884b15d44'
$ExpectedPhaseALockSha = '1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1'
$ExpectedT07Sha = 'bbe90933dd4526f4b0cb3c1db65ada38161de0147c476a5be2105bcb7cecf9ac'
$ExpectedTask01Sha = '79cfcfb8c463c235af1d7dfe4f49a8e9ef491a25749ccbeeded85b88f2ee90f9'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'
$ExpectedProfileId = 'ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c'
$ExpectedPolicyId = 'ProductValidationPolicy:v1:sha256:806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5'

foreach ($Path in @(
    $Gate,$PhaseARunner,$PhaseALock,$T07Helper,$Python,$Repo,$FoundationDb,$Task01Db
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_B_R2_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualPhaseARunnerSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PhaseARunner).Hash.ToLowerInvariant()
$ActualPhaseALockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PhaseALock).Hash.ToLowerInvariant()
$ActualT07Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T07Helper).Hash.ToLowerInvariant()
$ActualTask01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Task01Db).Hash.ToLowerInvariant()

Write-Host "T09_PHASE_B_R2_GATE_SHA256=$ActualGateSha"
Write-Host "T09_PHASE_A_R2_RUNNER_SHA256=$ActualPhaseARunnerSha"
Write-Host "T09_PHASE_A_R2_LOCK_SHA256=$ActualPhaseALockSha"
Write-Host "T09_PHASE_B_R2_T07_HELPER_SHA256=$ActualT07Sha"
Write-Host "T09_PHASE_B_R2_TASK01_DB_SHA256=$ActualTask01Sha"

if ($ActualGateSha -ne $ExpectedGateSha) { throw "T09_PHASE_B_R2_GATE_SHA256_MISMATCH" }
if ($ActualPhaseARunnerSha -ne $ExpectedPhaseARunnerSha) { throw "T09_PHASE_A_R2_RUNNER_SHA256_MISMATCH" }
if ($ActualPhaseALockSha -ne $ExpectedPhaseALockSha) { throw "T09_PHASE_A_R2_LOCK_SHA256_MISMATCH" }
if ($ActualT07Sha -ne $ExpectedT07Sha) { throw "T09_PHASE_B_R2_T07_HELPER_SHA256_MISMATCH" }
if ($ActualTask01Sha -ne $ExpectedTask01Sha) { throw "T09_PHASE_B_R2_TASK01_DB_SHA256_MISMATCH" }

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne $ExpectedCommit) { throw "T09_PHASE_B_R2_CANDIDATE_COMMIT_MISMATCH" }
if ($Tree -ne $ExpectedTree) { throw "T09_PHASE_B_R2_CANDIDATE_TREE_MISMATCH" }
if ($Status) { throw "T09_PHASE_B_R2_CANDIDATE_WORKTREE_NOT_CLEAN" }

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t09\phase-b-$Stamp-T09-A1-R2-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t09-phase-b-a1-r2-pyc'

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

Write-Host "T09_PHASE_B_R2_PROCESS_EXIT_CODE=$Rc"
Write-Host "T09_PHASE_B_R2_OUTPUT=$OutputDir"

if ($Rc -ne 0) {
    throw "T09_PHASE_B_R2_EXECUTION_FAILED exit_code=$Rc"
}

$LockPath = Join-Path $OutputDir 'phase-b-lock.json'
$ReportPath = Join-Path $OutputDir 'privacy-safe-comparison-report.json'
$CompatibilityPath = Join-Path $OutputDir 'compatibility-report.json'

foreach ($Path in @($LockPath,$ReportPath,$CompatibilityPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_B_R2_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
$Report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
$Compatibility = Get-Content -LiteralPath $CompatibilityPath -Raw | ConvertFrom-Json

$LockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $LockPath).Hash.ToLowerInvariant()

if ($Lock.phase -ne 'B') { throw "T09_PHASE_B_R2_LOCK_PHASE_MISMATCH" }
if ($Lock.candidate_commit -ne $ExpectedCommit -or $Lock.candidate_tree -ne $ExpectedTree) {
    throw "T09_PHASE_B_R2_LOCK_CANDIDATE_MISMATCH"
}
if ($Lock.runner_sha256 -ne $ExpectedGateSha -or
    $Lock.phase_b_runner_sha256 -ne $ExpectedGateSha) {
    throw "T09_PHASE_B_R2_LOCK_RUNNER_MISMATCH"
}
if ($Lock.phase_a_lock_sha256 -ne $ExpectedPhaseALockSha -or
    $Lock.phase_a_runner_sha256 -ne $ExpectedPhaseARunnerSha) {
    throw "T09_PHASE_B_R2_LOCK_PHASE_A_PROVENANCE_MISMATCH"
}
if ($Lock.state -ne 'OWNER_REVIEW_REQUIRED') {
    throw "T09_PHASE_B_R2_STATE_MISMATCH"
}

$Workers = @($Lock.worker_executions)
if (($Workers | Measure-Object).Count -ne 2) {
    throw "T09_PHASE_B_R2_WORKER_COUNT_NOT_2"
}
foreach ($Worker in $Workers) {
    if ($Worker.runner_sha256 -ne $ExpectedGateSha) {
        throw "T09_PHASE_B_R2_WORKER_RUNNER_MISMATCH"
    }
}

if ($Report.state -ne 'OWNER_REVIEW_REQUIRED') { throw "T09_PHASE_B_R2_REPORT_STATE_MISMATCH" }
if ($Report.profile.artifact_id -ne $ExpectedProfileId) { throw "T09_PHASE_B_R2_REPORT_PROFILE_MISMATCH" }
if ($Report.product_validation_policy.artifact_id -ne $ExpectedPolicyId) {
    throw "T09_PHASE_B_R2_REPORT_POLICY_MISMATCH"
}
if ($Report.automatic_learning -ne $false) { throw "T09_PHASE_B_R2_AUTOMATIC_LEARNING_NOT_FALSE" }
if ($Report.production_activation -ne $false) { throw "T09_PHASE_B_R2_PRODUCTION_ACTIVATION_NOT_FALSE" }

$Entries = @($Report.entries)
if (($Entries | Measure-Object).Count -ne 2) {
    throw "T09_PHASE_B_R2_ENTRY_COUNT_NOT_2"
}

$CompatDevices = @($Compatibility.controlled_device_checks)
if (($CompatDevices | Measure-Object).Count -ne 2) {
    throw "T09_PHASE_B_R2_COMPAT_DEVICE_COUNT_NOT_2"
}
foreach ($Device in $CompatDevices) {
    $Checks = @($Device.checks)
    if (($Checks | Measure-Object).Count -ne 9) {
        throw "T09_PHASE_B_R2_COMPAT_CHECK_COUNT_NOT_9"
    }
    foreach ($Check in $Checks) {
        if ($Check.status -ne 'PASS') {
            throw "T09_PHASE_B_R2_COMPATIBILITY_FAILURE"
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
            throw "T09_PHASE_B_R2_CONTROLLED_ARTIFACT_MISSING: $Path"
        }
    }

    $Cmp = Get-Content -LiteralPath $CmpPath -Raw | ConvertFrom-Json
    $Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
    $Request = Get-Content -LiteralPath $RequestPath -Raw | ConvertFrom-Json
    $Entry = $Entries[$i - 1]

    if ($Cmp.artifact_type -ne 'ProductValidationComparisonRecord') {
        throw "T09_PHASE_B_R2_COMPARISON_TYPE_MISMATCH_$i"
    }
    if ($Result.artifact_type -ne 'ClassificationResult') {
        throw "T09_PHASE_B_R2_RESULT_TYPE_MISMATCH_$i"
    }
    if ($Request.artifact_type -ne 'ClassificationRequestManifest') {
        throw "T09_PHASE_B_R2_REQUEST_TYPE_MISMATCH_$i"
    }
    if ($Cmp.artifact_id -ne $Entry.comparison.artifact_id -or
        $Result.artifact_id -ne $Entry.result.artifact_id -or
        $Request.artifact_id -ne $Entry.request.artifact_id) {
        throw "T09_PHASE_B_R2_ENTRY_ARTIFACT_BINDING_MISMATCH_$i"
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
    throw "T09_PHASE_B_R2_CONTROLLED_DEVICE_LABEL_SET_MISMATCH"
}

Write-Host ""
foreach ($Row in $Results) {
    Write-Host "T09_DEVICE=$($Row.Label)"
    Write-Host "  COMPARISON_OUTCOME=$($Row.ComparisonOutcome)"
    Write-Host "  PLATFORM=$($Row.PlatformStatus)|$($Row.PlatformValue)|$($Row.PlatformSupport)|$($Row.PlatformComparison)"
    Write-Host "  DEVICE_CLASS=$($Row.DeviceClassStatus)|$($Row.DeviceClassValue)|$($Row.DeviceClassSupport)|$($Row.DeviceClassComparison)"
    Write-Host "  COMPARISON_ID=$($Row.Comparison)"
}

Write-Host ""
Write-Host "T09_PHASE_B_R2_LAUNCHER_STATUS=PASS"
Write-Host "T09_PHASE_B_EXECUTED=YES"
Write-Host "T09_PHASE_B_STATUS=OWNER_REVIEW_REQUIRED"
Write-Host "T09_PHASE_B_POLICY_OUTCOME=$($Report.policy_outcome)"
Write-Host "T09_PHASE_B_CORRECT_DEVICE_CLASS_COUNT=$($Report.correct_device_class_count)"
Write-Host "T09_PHASE_B_WORKER_COUNT=$(($Workers | Measure-Object).Count)"
Write-Host "T09_PHASE_B_AUTOMATIC_LEARNING=NO"
Write-Host "T09_PHASE_B_PRODUCTION_ACTIVATION=NO"
Write-Host "T09_PHASE_B_LOCK_PATH=$LockPath"
Write-Host "T09_PHASE_B_LOCK_SHA256=$LockSha"
Write-Host "T09_PHASE_B_RUNNER_SHA256=$ExpectedGateSha"
Write-Host "OWNER_DECISION_REQUIRED=YES_AFTER_REVIEW"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=OWNER_REVIEW_T09_COMPARISON"
