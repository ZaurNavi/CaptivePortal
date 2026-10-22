$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$Gate = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r5-20261002.py'
$DecisionHelper = 'C:\CaptivPortal-Lab\tools\task04-t09-owner-accept-r5.py'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$PhaseALock = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-a-r2-upgrade-20261002T071712Z-T09-A1-01\phase-a-lock.json'
$PhaseBLock = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-b-20261002T105950Z-T09-A1-R5-01\phase-b-lock.json'

$ExpectedGateSha = 'a80456c02b875eb5b9ef7205683473f79be0a039a18434898ad2a46d8ad0063f'
$ExpectedHelperSha = '350b12f8fb49a0ae54aa005ae1cd2bb4769de9bdf38ba7b7cdba436fa629e834'
$ExpectedPhaseALockSha = '1142010057ddaa8564fe076160f35595e84ae51c5dae6d798d5e8bbb839c6ac1'
$ExpectedPhaseBLockSha = '93256ffa5224693a1823b0ece4bba5f7a2eb919eb022a08d59e6837a89603a05'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'

foreach ($Path in @($Python,$Repo,$Gate,$DecisionHelper,$FoundationDb,$PhaseALock,$PhaseBLock)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_C_R5_REQUIRED_PATH_MISSING:$Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualHelperSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $DecisionHelper).Hash.ToLowerInvariant()
$ActualPhaseALockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PhaseALock).Hash.ToLowerInvariant()
$ActualPhaseBLockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PhaseBLock).Hash.ToLowerInvariant()

Write-Host "T09_PHASE_C_R5_GATE_SHA256=$ActualGateSha"
Write-Host "T09_OWNER_DECISION_HELPER_SHA256=$ActualHelperSha"
Write-Host "T09_PHASE_A_LOCK_SHA256=$ActualPhaseALockSha"
Write-Host "T09_PHASE_B_R5_LOCK_SHA256=$ActualPhaseBLockSha"

if ($ActualGateSha -ne $ExpectedGateSha) { throw "T09_PHASE_C_R5_GATE_SHA256_MISMATCH" }
if ($ActualHelperSha -ne $ExpectedHelperSha) { throw "T09_OWNER_DECISION_HELPER_SHA256_MISMATCH" }
if ($ActualPhaseALockSha -ne $ExpectedPhaseALockSha) { throw "T09_PHASE_A_LOCK_SHA256_MISMATCH" }
if ($ActualPhaseBLockSha -ne $ExpectedPhaseBLockSha) { throw "T09_PHASE_B_R5_LOCK_SHA256_MISMATCH" }

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain
Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"
if ($Commit -ne $ExpectedCommit) { throw "T09_PHASE_C_R5_CANDIDATE_COMMIT_MISMATCH" }
if ($Tree -ne $ExpectedTree) { throw "T09_PHASE_C_R5_CANDIDATE_TREE_MISMATCH" }
if ($Status) { throw "T09_PHASE_C_R5_CANDIDATE_WORKTREE_NOT_CLEAN" }

$B = Get-Content -LiteralPath $PhaseBLock -Raw | ConvertFrom-Json
if ($B.phase -ne 'B' -or $B.state -ne 'OWNER_REVIEW_REQUIRED' -or $B.policy_outcome -ne 'PASS') {
    throw "T09_PHASE_C_R5_PHASE_B_STATE_MISMATCH"
}
if ($B.runner_sha256 -ne $ExpectedGateSha -or $B.phase_b_runner_sha256 -ne $ExpectedGateSha) {
    throw "T09_PHASE_C_R5_PHASE_B_RUNNER_MISMATCH"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$DecisionDir = 'C:\CaptivPortal-Lab\official-runs\task04\t09\owner-decisions'
$DecisionPath = Join-Path $DecisionDir "owner-decision-$Stamp-T09-A1-R5.json"

& $Python -I -B $DecisionHelper `
    --phase-a-lock $PhaseALock `
    --phase-b-lock $PhaseBLock `
    --output $DecisionPath
$DecisionRc = $LASTEXITCODE
Write-Host "T09_OWNER_DECISION_HELPER_EXIT_CODE=$DecisionRc"
if ($DecisionRc -ne 0) { throw "T09_OWNER_DECISION_CREATION_FAILED:$DecisionRc" }
if (-not (Test-Path -LiteralPath $DecisionPath)) { throw "T09_OWNER_DECISION_FILE_MISSING" }

$Decision = Get-Content -LiteralPath $DecisionPath -Raw | ConvertFrom-Json
if ($Decision.actor_role -ne 'OWNER' -or $Decision.decision -ne 'ACCEPT' -or
    $Decision.decision_subject_type -ne 'TASK04_PRODUCT_VALIDATION') {
    throw "T09_OWNER_DECISION_CONTENT_MISMATCH"
}
if ($Decision.decision_subject_id -ne $B.validation_run_id) {
    throw "T09_OWNER_DECISION_VALIDATION_RUN_MISMATCH"
}
if (@($Decision.referenced_artifact_ids).Count -ne 8 -or
    @($Decision.referenced_gate_ids).Count -ne 1 -or
    @($Decision.referenced_gate_ids)[0] -ne 'T-09') {
    throw "T09_OWNER_DECISION_REFERENCE_SET_MISMATCH"
}

$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t09\phase-c-$Stamp-T09-A1-R5-01"
$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t09-phase-c-a1-r5-pyc'

try {
    & $Python $Gate C `
        --repo $Repo `
        --foundation-db $FoundationDb `
        --phase-a-lock $PhaseALock `
        --phase-a-lock-sha256 $ExpectedPhaseALockSha `
        --phase-b-lock $PhaseBLock `
        --phase-b-lock-sha256 $ExpectedPhaseBLockSha `
        --owner-decision $DecisionPath `
        --output $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T09_PHASE_C_R5_PROCESS_EXIT_CODE=$Rc"
Write-Host "T09_PHASE_C_R5_OUTPUT=$OutputDir"
if ($Rc -ne 0) { throw "T09_PHASE_C_R5_EXECUTION_FAILED:$Rc" }

$GateResultPath = Join-Path $OutputDir 't09-gate-result-manifest.json'
$GateProofPath = Join-Path $OutputDir 't09-gate-proof-artifact.json'
$ExecutionPath = Join-Path $OutputDir 't09-execution-evidence.json'
$CopiedDecisionPath = Join-Path $OutputDir 'owner-decision.json'
$CopiedPhaseBLock = Join-Path $OutputDir 'phase-b-lock.json'
$PrivacyReportPath = Join-Path $OutputDir 'privacy-safe-comparison-report.json'

foreach ($Path in @($GateResultPath,$GateProofPath,$ExecutionPath,$CopiedDecisionPath,$CopiedPhaseBLock,$PrivacyReportPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_PHASE_C_R5_EXPECTED_OUTPUT_MISSING:$Path"
    }
}

$GateResult = Get-Content -LiteralPath $GateResultPath -Raw | ConvertFrom-Json
$GateProof = Get-Content -LiteralPath $GateProofPath -Raw | ConvertFrom-Json
$Execution = Get-Content -LiteralPath $ExecutionPath -Raw | ConvertFrom-Json
$CopiedDecision = Get-Content -LiteralPath $CopiedDecisionPath -Raw | ConvertFrom-Json

if ($GateResult.artifact_type -ne 'GateResultManifest' -or
    $GateResult.semantic_payload.gate_id -ne 'T-09' -or
    $GateResult.semantic_payload.status -ne 'PASS') {
    throw "T09_FINAL_GATE_RESULT_NOT_PASS"
}
if ($GateResult.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit -or
    $GateResult.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T09_FINAL_GATE_RESULT_CANDIDATE_MISMATCH"
}
if ($GateProof.artifact_type -ne 'GateProofArtifact' -or
    $GateProof.semantic_payload.proof_kind -ne 'TASK04_PRODUCT_VALIDATION' -or
    $GateProof.semantic_payload.source_gate_id -ne 'T-09') {
    throw "T09_FINAL_GATE_PROOF_MISMATCH"
}
if ($Execution.status -ne 'PASS' -or $Execution.policy_outcome -ne 'PASS' -or
    $Execution.production_action -ne $false) {
    throw "T09_FINAL_EXECUTION_EVIDENCE_MISMATCH"
}
if ($CopiedDecision.decision_record_id -ne $Decision.decision_record_id -or
    $CopiedDecision.record_sha256 -ne $Decision.record_sha256 -or
    $CopiedDecision.decision -ne 'ACCEPT') {
    throw "T09_FINAL_OWNER_DECISION_MISMATCH"
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $CopiedPhaseBLock).Hash.ToLowerInvariant() -ne $ExpectedPhaseBLockSha) {
    throw "T09_FINAL_PHASE_B_LOCK_COPY_MISMATCH"
}
$DecisionRefs = @($GateResult.semantic_payload.decision_record_refs)
if ($DecisionRefs.Count -ne 1 -or $DecisionRefs[0] -ne $Decision.decision_record_id) {
    throw "T09_FINAL_DECISION_REFERENCE_MISMATCH"
}

Write-Host ""
Write-Host "T09_PHASE_C_R5_LAUNCHER_STATUS=PASS"
Write-Host "T09_FINAL_GATE_STATUS=PASS"
Write-Host "T09_FINAL_POLICY_OUTCOME=PASS"
Write-Host "T09_FINAL_OWNER_DECISION=ACCEPT"
Write-Host "T09_FINAL_AUTOMATIC_LEARNING=NO"
Write-Host "T09_FINAL_PRODUCTION_ACTION=NO"
Write-Host "T09_FINAL_GATE_PROOF_ARTIFACT=$($GateProof.artifact_id)"
Write-Host "T09_FINAL_GATE_RESULT_MANIFEST=$($GateResult.artifact_id)"
Write-Host "T09_FINAL_OWNER_DECISION_RECORD_ID=$($Decision.decision_record_id)"
Write-Host "T09_FINAL_OWNER_DECISION_RECORD_SHA256=$($Decision.record_sha256)"
Write-Host "T09_FINAL_OUTPUT=$OutputDir"
