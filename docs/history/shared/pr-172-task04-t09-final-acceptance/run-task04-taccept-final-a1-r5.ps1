$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Gate = 'C:\CaptivPortal-Lab\tools\task04-taccept-final-a1-r5-20261003.py'
$ExpectedGateSha = 'f6e9a99f791ee2c2ce724fc622caf8b59d557a5ca86c5f93178e8a51857e4e2a'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'

foreach ($Path in @($Python,$Gate,$Repo)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "TACCEPT_REQUIRED_PATH_MISSING:$Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
Write-Host "TACCEPT_GATE_SHA256=$ActualGateSha"
if ($ActualGateSha -ne $ExpectedGateSha) {
    throw "TACCEPT_GATE_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain
Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"
Write-Host "TACCEPT_PREVIOUS_R1_STATUS=BLOCKED_BEFORE_ACCEPTANCE_WRITE"
Write-Host "TACCEPT_PREVIOUS_R1_BLOCKER=INCOMPLETE_ARTIFACT_INDEX"
Write-Host "TACCEPT_PREVIOUS_R2_STATUS=BLOCKED_BEFORE_ACCEPTANCE_WRITE"
Write-Host "TACCEPT_PREVIOUS_R2_BLOCKER=INCOMPLETE_RETAINED_FOUNDATION_ARTIFACT_RESOLUTION"
Write-Host "TACCEPT_PREVIOUS_R3_STATUS=BLOCKED_BEFORE_ACCEPTANCE_WRITE"
Write-Host "TACCEPT_PREVIOUS_R3_BLOCKER=RETAINED_SEARCH_ROOT_OMITTED_LAB_ARTIFACTS"
Write-Host "TACCEPT_FORENSICS_TARGET_ARTIFACT_RETRIEVABLE=YES"
Write-Host "TACCEPT_R4_REPAIR=ADD_LAB_ARTIFACTS_TO_EXACT_LAZY_RESOLVER"
Write-Host "TACCEPT_PREVIOUS_R4_STATUS=BLOCKED_BEFORE_ACCEPTANCE_WRITE"
Write-Host "TACCEPT_PREVIOUS_R4_BLOCKER=OVEREXPANDED_HISTORICAL_GATE_PROOF_INPUTS"
Write-Host "TACCEPT_R5_REPAIR=R14_BOUNDED_HISTORICAL_AUDIT_GRAPH"
if ($Commit -ne $ExpectedCommit) { throw "TACCEPT_CANDIDATE_COMMIT_MISMATCH" }
if ($Tree -ne $ExpectedTree) { throw "TACCEPT_CANDIDATE_TREE_MISMATCH" }
if ($Status) { throw "TACCEPT_CANDIDATE_WORKTREE_NOT_CLEAN" }

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$Output = "C:\CaptivPortal-Lab\official-runs\task04\taccept\official-run-$Stamp-TACCEPT-A1-R5-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-taccept-a1-r5-pyc'
try {
    & $Python -I -B $Gate --output $Output
    $Code = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "TACCEPT_PROCESS_EXIT_CODE=$Code"
Write-Host "TACCEPT_OUTPUT=$Output"
if ($Code -ne 0) {
    throw "TACCEPT_EXECUTION_FAILED:$Code"
}

$Lock = Join-Path $Output 'taccept-lock.json'
$Acceptance = Join-Path $Output 'task04-acceptance-manifest.json'
$Rpm = Join-Path $Output 'classification-runtime-profile-admission-manifest.json'
$GateResult = Join-Path $Output 'taccept-gate-result-manifest.json'
$Decision = Join-Path $Output 'owner-decision.json'

foreach ($Path in @($Lock,$Acceptance,$Rpm,$GateResult,$Decision)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "TACCEPT_EXPECTED_OUTPUT_MISSING:$Path"
    }
}

$L = Get-Content -LiteralPath $Lock -Raw | ConvertFrom-Json
$A = Get-Content -LiteralPath $Acceptance -Raw | ConvertFrom-Json
$R = Get-Content -LiteralPath $Rpm -Raw | ConvertFrom-Json
$G = Get-Content -LiteralPath $GateResult -Raw | ConvertFrom-Json
$D = Get-Content -LiteralPath $Decision -Raw | ConvertFrom-Json
$LockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Lock).Hash.ToLowerInvariant()

if ($L.gate_id -ne 'T-ACCEPT' -or $L.status -ne 'PASS' -or
    $L.candidate_commit -ne $ExpectedCommit -or $L.candidate_tree -ne $ExpectedTree) {
    throw "TACCEPT_LOCK_CONTENT_MISMATCH"
}
if ($L.update_class -ne 'INITIAL_CLASSIFICATION' -or $null -ne $L.classification_active_pointer_after -or
    $L.production_activation -ne $false) {
    throw "TACCEPT_LOCK_ACTIVATION_INVARIANT_MISMATCH"
}
if ($A.artifact_type -ne 'Task04AcceptanceManifest' -or
    $A.artifact_id -ne $L.task04_acceptance_manifest.artifact_id) {
    throw "TACCEPT_ACCEPTANCE_MANIFEST_MISMATCH"
}
if ($R.artifact_type -ne 'RuntimeProfileAdmissionManifest' -or
    $R.semantic_payload.profile_kind -ne 'classification' -or
    $R.semantic_payload.update_class -ne 'INITIAL_CLASSIFICATION' -or
    $R.artifact_id -ne $L.classification_runtime_profile_admission_manifest.artifact_id) {
    throw "TACCEPT_RPM_MISMATCH"
}
if ($G.artifact_type -ne 'GateResultManifest' -or
    $G.semantic_payload.gate_id -ne 'T-ACCEPT' -or
    $G.semantic_payload.status -ne 'PASS' -or
    $G.artifact_id -ne $L.gate_result_manifest.artifact_id) {
    throw "TACCEPT_GATE_RESULT_MISMATCH"
}
if ($D.actor_role -ne 'OWNER' -or $D.decision -ne 'ACCEPT' -or
    $D.decision_record_id -ne $L.owner_decision_record_id) {
    throw "TACCEPT_OWNER_DECISION_MISMATCH"
}

Write-Host ""
Write-Host "TACCEPT_LAUNCHER_STATUS=PASS"
Write-Host "TACCEPT_FINAL_GATE_STATUS=PASS"
Write-Host "DEVICE_FINGERPRINT_TASK04_STATUS=ACCEPTED_PRODUCTION_ELIGIBLE"
Write-Host "TACCEPT_TASK04_ACCEPTANCE_MANIFEST=$($A.artifact_id)"
Write-Host "TACCEPT_CLASSIFICATION_RPM=$($R.artifact_id)"
Write-Host "TACCEPT_GATE_RESULT_MANIFEST=$($G.artifact_id)"
Write-Host "TACCEPT_OWNER_DECISION_RECORD_ID=$($D.decision_record_id)"
Write-Host "TACCEPT_CLASSIFICATION_ACTIVE_POINTER=ABSENT"
Write-Host "TACCEPT_PRODUCTION_ACTIVATION=NO"
Write-Host "TACCEPT_LOCK_PATH=$Lock"
Write-Host "TACCEPT_LOCK_SHA256=$LockSha"
