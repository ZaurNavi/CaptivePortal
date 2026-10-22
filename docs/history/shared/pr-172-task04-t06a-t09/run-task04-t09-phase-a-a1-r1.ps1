$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-a-a1-20261002.py'
$T07Helper = 'C:\CaptivPortal-Lab\tools\task04-t07-gate-a1-20261002.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$T06ARunDir = 'C:\CaptivPortal-Lab\official-runs\task04\t06a\official-run-20261001T124442Z-T06A-A1-01\fe25e9fc-7b03-485b-ae68-0f806fd96af6'

$ExpectedGateSha = '197b134fcc19ceead1d83e5e1598391168a4f5d4783a34331f6470f700c3df9a'
$ExpectedT07Sha = 'bbe90933dd4526f4b0cb3c1db65ada38161de0147c476a5be2105bcb7cecf9ac'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'
$ExpectedProfileId = 'ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c'
$ExpectedPolicyId = 'ProductValidationPolicy:v1:sha256:806779ca1844e55083a2c1c464cf8d94a9bdd0b2f97436d203b63fd03e81bea5'
$ExpectedT06AResultId = 'GateResultManifest:v1:sha256:cd102f0fca7adb9e09ce1ff69d2109b34691e7362fd071a0617fc300547db406'
$ExpectedT06AProofId = 'GateProofArtifact:v1:sha256:6e404961cce296382f03b37e54111b6d535a1e1c44432a8e8f6269290bf64267'

foreach ($Path in @($Gate,$T07Helper,$Python,$Repo,$FoundationDb,$T06ARunDir)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_A_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualT07Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T07Helper).Hash.ToLowerInvariant()

Write-Host "T09_PHASE_A_GATE_SHA256=$ActualGateSha"
Write-Host "T09_PHASE_A_T07_HELPER_SHA256=$ActualT07Sha"

if ($ActualGateSha -ne $ExpectedGateSha) {
    throw "T09_PHASE_A_GATE_SHA256_MISMATCH"
}
if ($ActualT07Sha -ne $ExpectedT07Sha) {
    throw "T09_PHASE_A_T07_HELPER_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne $ExpectedCommit) {
    throw "T09_PHASE_A_CANDIDATE_COMMIT_MISMATCH"
}
if ($Tree -ne $ExpectedTree) {
    throw "T09_PHASE_A_CANDIDATE_TREE_MISMATCH"
}
if ($Status) {
    throw "T09_PHASE_A_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$T06AProfilePath = Join-Path $T06ARunDir 't06a-classification-runtime-profile.json'
$T06AProofPath = Join-Path $T06ARunDir 't06a-gate-proof-artifact.json'
$T06AResultPath = Join-Path $T06ARunDir 't06a-gate-result-manifest.json'

foreach ($Path in @($T06AProfilePath,$T06AProofPath,$T06AResultPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_A_T06A_PREREQUISITE_MISSING: $Path"
    }
}

$T06AProfile = Get-Content -LiteralPath $T06AProfilePath -Raw | ConvertFrom-Json
$T06AProof = Get-Content -LiteralPath $T06AProofPath -Raw | ConvertFrom-Json
$T06AResult = Get-Content -LiteralPath $T06AResultPath -Raw | ConvertFrom-Json

if ($T06AProfile.artifact_id -ne $ExpectedProfileId) {
    throw "T09_PHASE_A_PROFILE_ID_MISMATCH"
}
if ($T06AProof.artifact_id -ne $ExpectedT06AProofId) {
    throw "T09_PHASE_A_T06A_PROOF_ID_MISMATCH"
}
if ($T06AResult.artifact_id -ne $ExpectedT06AResultId -or
    $T06AResult.semantic_payload.status -ne 'PASS') {
    throw "T09_PHASE_A_T06A_RESULT_MISMATCH"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t09\phase-a-$Stamp-T09-A1-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t09-phase-a-a1-pyc'

try {
    & $Python $Gate A `
        --repo $Repo `
        --foundation-db $FoundationDb `
        --output $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T09_PHASE_A_PROCESS_EXIT_CODE=$Rc"
Write-Host "T09_PHASE_A_OUTPUT=$OutputDir"

if ($Rc -ne 0) {
    throw "T09_PHASE_A_FAILED exit_code=$Rc"
}

$LockPath = Join-Path $OutputDir 'phase-a-lock.json'
$Gt1Path = Join-Path $OutputDir 'ground-truth-1.json'
$Gt2Path = Join-Path $OutputDir 'ground-truth-2.json'
$RegPath = Join-Path $OutputDir 'ground-truth-registration.json'
$ProfilePath = Join-Path $OutputDir 'exact-profile.json'
$PolicyPath = Join-Path $OutputDir 'exact-product-policy.json'
$ResultPath = Join-Path $OutputDir 't06a-result.json'
$ProofPath = Join-Path $OutputDir 't06a-proof.json'

foreach ($Path in @(
    $LockPath,$Gt1Path,$Gt2Path,$RegPath,$ProfilePath,$PolicyPath,$ResultPath,$ProofPath
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_A_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

# Phase A MUST NOT expose or create classification results.
$Forbidden = @(
    Get-ChildItem -LiteralPath $OutputDir -File -ErrorAction Stop |
    Where-Object {
        $_.Name -match '^(request|result|comparison)-' -or
        $_.Name -eq 'phase-b-lock.json' -or
        $_.Name -eq 'privacy-safe-comparison-report.json'
    }
)
if (($Forbidden | Measure-Object).Count -ne 0) {
    throw "T09_PHASE_A_RESULT_VISIBILITY_VIOLATION"
}

$Lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
$Gt1 = Get-Content -LiteralPath $Gt1Path -Raw | ConvertFrom-Json
$Gt2 = Get-Content -LiteralPath $Gt2Path -Raw | ConvertFrom-Json
$Reg = Get-Content -LiteralPath $RegPath -Raw | ConvertFrom-Json
$ExactProfile = Get-Content -LiteralPath $ProfilePath -Raw | ConvertFrom-Json
$ExactPolicy = Get-Content -LiteralPath $PolicyPath -Raw | ConvertFrom-Json

$LockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $LockPath).Hash.ToLowerInvariant()

if ($Lock.phase -ne 'A') {
    throw "T09_PHASE_A_LOCK_PHASE_MISMATCH"
}
if ($Lock.candidate_commit -ne $ExpectedCommit -or $Lock.candidate_tree -ne $ExpectedTree) {
    throw "T09_PHASE_A_LOCK_CANDIDATE_MISMATCH"
}
if ($Lock.runner_sha256 -ne $ExpectedGateSha) {
    throw "T09_PHASE_A_LOCK_RUNNER_SHA_MISMATCH"
}
if ($Lock.helper_sha256 -ne $ExpectedT07Sha) {
    throw "T09_PHASE_A_LOCK_HELPER_SHA_MISMATCH"
}
if ($Lock.profile.artifact_id -ne $ExpectedProfileId) {
    throw "T09_PHASE_A_LOCK_PROFILE_MISMATCH"
}
if ($Lock.product_validation_policy.artifact_id -ne $ExpectedPolicyId) {
    throw "T09_PHASE_A_LOCK_POLICY_MISMATCH"
}

$Bindings = @($Lock.device_bindings)
if (($Bindings | Measure-Object).Count -ne 2) {
    throw "T09_PHASE_A_DEVICE_BINDING_COUNT_NOT_2"
}

$Android = @($Bindings | Where-Object { $_.controlled_device_lab_label -eq 'OWNER_ANDROID' })
$Windows = @($Bindings | Where-Object { $_.controlled_device_lab_label -eq 'OWNER_WINDOWS_LAPTOP' })

if (($Android | Measure-Object).Count -ne 1 -or ($Windows | Measure-Object).Count -ne 1) {
    throw "T09_PHASE_A_DEVICE_LABEL_SET_MISMATCH"
}

if ($Android[0].site_id -ne '6a64f17630da7c70d232187a' -or
    $Android[0].observed_mac -ne 'BE:00:7D:9B:04:2E' -or
    $Android[0].platform_family_ground_truth -ne 'android' -or
    $Android[0].device_class_ground_truth -ne 'smartphone' -or
    $Android[0].window_start_utc -ne '2026-09-30T09:04:08.388Z' -or
    $Android[0].window_end_utc -ne '2026-09-30T09:08:09.000Z' -or
    $Android[0].ground_truth_method -ne 'OWNER_CONTROLLED_DEVICE') {
    throw "T09_PHASE_A_ANDROID_GROUND_TRUTH_MISMATCH"
}

if ($Windows[0].site_id -ne '6a64f17630da7c70d232187a' -or
    $Windows[0].observed_mac -ne 'CC:F9:E4:D6:AB:1E' -or
    $Windows[0].platform_family_ground_truth -ne 'windows' -or
    $Windows[0].device_class_ground_truth -ne 'laptop' -or
    $Windows[0].window_start_utc -ne '2026-09-30T09:23:00.176Z' -or
    $Windows[0].window_end_utc -ne '2026-09-30T09:30:15.000Z' -or
    $Windows[0].ground_truth_method -ne 'OWNER_CONTROLLED_DEVICE') {
    throw "T09_PHASE_A_WINDOWS_GROUND_TRUTH_MISMATCH"
}

if ($Gt1.artifact_type -ne 'ControlledValidationGroundTruthRecord' -or
    $Gt2.artifact_type -ne 'ControlledValidationGroundTruthRecord') {
    throw "T09_PHASE_A_GROUND_TRUTH_ARTIFACT_TYPE_MISMATCH"
}

if ($Reg.state -ne 'REGISTERED_PRE_RESULT') {
    throw "T09_PHASE_A_REGISTRATION_STATE_MISMATCH"
}
if ($Reg.validation_run_id -ne $Lock.validation_run_id) {
    throw "T09_PHASE_A_REGISTRATION_RUN_ID_MISMATCH"
}

if ($ExactProfile.artifact_id -ne $ExpectedProfileId) {
    throw "T09_PHASE_A_EXACT_PROFILE_MISMATCH"
}
if ($ExactPolicy.artifact_id -ne $ExpectedPolicyId) {
    throw "T09_PHASE_A_EXACT_POLICY_MISMATCH"
}

$CommitAfter = (& git -C $Repo rev-parse HEAD).Trim()
$TreeAfter = (& git -C $Repo show -s --format=%T HEAD).Trim()
$StatusAfter = & git -C $Repo status --porcelain

if ($CommitAfter -ne $ExpectedCommit -or
    $TreeAfter -ne $ExpectedTree -or
    $StatusAfter) {
    throw "T09_PHASE_A_CANDIDATE_CHANGED_OR_DIRTY"
}

Write-Host ""
Write-Host "T09_PHASE_A_LAUNCHER_STATUS=PASS"
Write-Host "T09_PHASE_A_STATUS=GROUND_TRUTH_LOCKED"
Write-Host "T09_PHASE_A_RESULT_VISIBILITY=NO"
Write-Host "T09_PHASE_A_CONTROLLED_DEVICE_COUNT=2"
Write-Host "T09_PHASE_A_PROFILE_ID=$ExpectedProfileId"
Write-Host "T09_PHASE_A_POLICY_ID=$ExpectedPolicyId"
Write-Host "T09_PHASE_A_LOCK_PATH=$LockPath"
Write-Host "T09_PHASE_A_LOCK_SHA256=$LockSha"
Write-Host "T09_PHASE_A_RUNNER_SHA256=$ExpectedGateSha"
Write-Host "OWNER_DECISION_REQUIRED=NO_AT_PHASE_A"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T09_PHASE_B_BUILD_FROM_EXACT_LOCK"
