$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t05-gate-a1-r2-20261001.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$T06ARunDir = 'C:\CaptivPortal-Lab\official-runs\task04\t06a\official-run-20261001T124442Z-T06A-A1-01\fe25e9fc-7b03-485b-ae68-0f806fd96af6'

$T01Helper = 'C:\CaptivPortal-Lab\tools\task04-t01-gate-a1-20261001.py'
$T06ARunner = 'C:\CaptivPortal-Lab\tools\task04-t06a-gate-a1-20261001.py'
$T06Manifest = 'C:\CaptivPortal-Lab\official-runs\task04\t06\official-run-20261001T121859Z-T06-A1-01\6ca9f53d-1b46-44f3-b4fe-1a2dced4c8a8\t06-manifest.json'
$PreviousFailedResult = 'C:\CaptivPortal-Lab\official-runs\task04\t05\official-run-20261001T125331Z-T05-A1-01\62bcd6bd-1caf-4902-b6e3-05940ee2db19\t05-gate-result-manifest.json'

$ExpectedGateSha = '229bbd45bf8a0edab0c9ad1dc60ea4ec52f2a533f07e984ecf0634c69b34c006'
$ExpectedT01Sha = 'ac8a73606c8136fae3486ec63ee3ffe200852bbdbf53dc4b72144f369055f6b4'
$ExpectedT06ARunnerSha = 'cd3f22eec438c02b2ef11b9d1febd32aed7508130f6b1ab45caf77b7610567ed'
$ExpectedT06ManifestFileSha = 'd0f651952d4e425acbee57d6b1219e676bc60147b43def5033611300e57428c9'
$ExpectedPreviousFailId = 'GateResultManifest:v1:sha256:3dc19780824645abbbb5a2400cd445bb168e33a545d0f9866cebe512b7049979'

$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'
$ExpectedProfileId = 'ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c'
$ExpectedT06AProofId = 'GateProofArtifact:v1:sha256:6e404961cce296382f03b37e54111b6d535a1e1c44432a8e8f6269290bf64267'
$ExpectedT06AResultId = 'GateResultManifest:v1:sha256:cd102f0fca7adb9e09ce1ff69d2109b34691e7362fd071a0617fc300547db406'

foreach ($Path in @(
    $Gate,$Python,$Repo,$FoundationDb,$T06ARunDir,
    $T01Helper,$T06ARunner,$T06Manifest,$PreviousFailedResult
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T05_R2_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualT01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T01Helper).Hash.ToLowerInvariant()
$ActualT06ARunnerSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T06ARunner).Hash.ToLowerInvariant()
$ActualT06ManifestFileSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T06Manifest).Hash.ToLowerInvariant()

Write-Host "T05_A1_R2_GATE_SHA256=$ActualGateSha"
Write-Host "T05_A1_R2_T01_HELPER_SHA256=$ActualT01Sha"
Write-Host "T05_A1_R2_T06A_RUNNER_SHA256=$ActualT06ARunnerSha"
Write-Host "T05_A1_R2_T06_MANIFEST_FILE_SHA256=$ActualT06ManifestFileSha"

if ($ActualGateSha -ne $ExpectedGateSha) {
    throw "T05_A1_R2_GATE_SHA256_MISMATCH"
}
if ($ActualT01Sha -ne $ExpectedT01Sha) {
    throw "T05_A1_R2_T01_HELPER_SHA256_MISMATCH"
}
if ($ActualT06ARunnerSha -ne $ExpectedT06ARunnerSha) {
    throw "T05_A1_R2_T06A_RUNNER_SHA256_MISMATCH"
}
if ($ActualT06ManifestFileSha -ne $ExpectedT06ManifestFileSha) {
    throw "T05_A1_R2_T06_MANIFEST_FILE_SHA256_MISMATCH"
}

$PriorFail = Get-Content -LiteralPath $PreviousFailedResult -Raw | ConvertFrom-Json
if ($PriorFail.artifact_id -ne $ExpectedPreviousFailId) {
    throw "T05_A1_R2_PREVIOUS_FAIL_ID_MISMATCH"
}
if ($PriorFail.semantic_payload.status -ne 'FAIL') {
    throw "T05_A1_R2_PREVIOUS_RESULT_NOT_FAIL"
}

Write-Host "T05_PREVIOUS_FAIL_PRESERVED=$($PriorFail.artifact_id)"
Write-Host "T05_PREVIOUS_FAIL_RERUN_REASON=HARNESS_FIXTURE_INVALID_WINDOW"

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne $ExpectedCommit) {
    throw "T05_A1_R2_CANDIDATE_COMMIT_MISMATCH"
}
if ($Tree -ne $ExpectedTree) {
    throw "T05_A1_R2_CANDIDATE_TREE_MISMATCH"
}
if ($Status) {
    throw "T05_A1_R2_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$T06AProfilePath = Join-Path $T06ARunDir 't06a-classification-runtime-profile.json'
$T06AProofPath = Join-Path $T06ARunDir 't06a-gate-proof-artifact.json'
$T06AResultPath = Join-Path $T06ARunDir 't06a-gate-result-manifest.json'

foreach ($Path in @($T06AProfilePath,$T06AProofPath,$T06AResultPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T05_A1_R2_T06A_PREREQUISITE_MISSING: $Path"
    }
}

$T06AProfile = Get-Content -LiteralPath $T06AProfilePath -Raw | ConvertFrom-Json
$T06AProof = Get-Content -LiteralPath $T06AProofPath -Raw | ConvertFrom-Json
$T06AResult = Get-Content -LiteralPath $T06AResultPath -Raw | ConvertFrom-Json

if ($T06AProfile.artifact_id -ne $ExpectedProfileId) {
    throw "T05_A1_R2_PROFILE_ID_MISMATCH"
}
if ($T06AProof.artifact_id -ne $ExpectedT06AProofId) {
    throw "T05_A1_R2_T06A_PROOF_ID_MISMATCH"
}
if ($T06AResult.artifact_id -ne $ExpectedT06AResultId) {
    throw "T05_A1_R2_T06A_RESULT_ID_MISMATCH"
}
if ($T06AResult.semantic_payload.status -ne 'PASS') {
    throw "T05_A1_R2_T06A_RESULT_NOT_PASS"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t05\official-run-$Stamp-T05-A1-R2-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t05-a1-r2-pyc'

try {
    & $Python $Gate `
        --repo $Repo `
        --foundation-control-db $FoundationDb `
        --t06a-run-dir $T06ARunDir `
        --output-dir $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T05_R2_PROCESS_EXIT_CODE=$Rc"
Write-Host "T05_R2_OUTPUT_ROOT=$OutputDir"

if ($Rc -ne 0) {
    throw "T05_A1_R2_FORMAL_FAILED exit_code=$Rc"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputDir -Directory)
$RunCount = ($RunDirs | Measure-Object).Count
if ($RunCount -ne 1) {
    throw "T05_A1_R2_RUN_DIRECTORY_COUNT_NOT_ONE count=$RunCount"
}

$RunDir = $RunDirs[0].FullName
$ProofPath = Join-Path $RunDir 't05-gate-proof-artifact.json'
$ResultPath = Join-Path $RunDir 't05-gate-result-manifest.json'
$EvidencePath = Join-Path $RunDir 't05-execution-evidence.json'
$MatrixPath = Join-Path $RunDir 't05-direct-matrix.json'
$PointerPath = Join-Path $RunDir 't05-pointer-switch-trace.json'
$IoPath = Join-Path $RunDir 't05-pure-core-io-proof.json'
$FreshnessPath = Join-Path $RunDir 't05-freshness-report.json'
$PytestPath = Join-Path $RunDir 't05-pytest.log'
$SummaryPath = Join-Path $RunDir 't05-summary.txt'

foreach ($Path in @(
    $ProofPath,$ResultPath,$EvidencePath,$MatrixPath,$PointerPath,
    $IoPath,$FreshnessPath,$PytestPath,$SummaryPath
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T05_A1_R2_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$Evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json
$Matrix = Get-Content -LiteralPath $MatrixPath -Raw | ConvertFrom-Json
$Pointer = Get-Content -LiteralPath $PointerPath -Raw | ConvertFrom-Json
$Io = Get-Content -LiteralPath $IoPath -Raw | ConvertFrom-Json
$Freshness = Get-Content -LiteralPath $FreshnessPath -Raw | ConvertFrom-Json

$CaseProperties = @($Matrix.cases.PSObject.Properties)
$CaseCount = ($CaseProperties | Measure-Object).Count
Write-Host "T05_R2_CASE_COUNT=$CaseCount"

if ($CaseCount -ne 12) {
    throw "T05_A1_R2_CASE_COUNT_NOT_12 count=$CaseCount"
}
foreach ($Case in $CaseProperties) {
    if ($Case.Value.status -ne 'PASS') {
        throw "T05_A1_R2_CASE_FAILURE: $($Case.Name)"
    }
}
if ($Matrix.all_pass -ne $true) {
    throw "T05_A1_R2_MATRIX_NOT_PASS"
}

$M10 = $Matrix.cases.'T05-M10'.trace
Write-Host "T05_R2_NEGATIVE_AGE_SOURCE_SLOT=$($M10.negative_age_source_slot)"
Write-Host "T05_R2_NEGATIVE_AGE_SOURCE_RETRIEVED_AT=$($M10.negative_age_source_retrieved_at_utc)"
Write-Host "T05_R2_NEGATIVE_AGE_EVALUATION_AT=$($M10.negative_evaluation_at_utc)"
Write-Host "T05_R2_COMPLETED_WINDOW_END=$($M10.completed_window_end_utc)"

if ($M10.snapshot_window_remained_valid -ne $true) {
    throw "T05_A1_R2_M10_WINDOW_NOT_VALID"
}
if ($M10.reason_code -ne 'negative_knowledge_age') {
    throw "T05_A1_R2_M10_WRONG_REASON"
}
if (-not $M10.negative_age_source_slot) {
    throw "T05_A1_R2_M10_SOURCE_SLOT_MISSING"
}

if ([int]$Evidence.pytest_exit_status -ne 0) {
    throw "T05_A1_R2_PYTEST_NOT_PASS"
}
if ([int]$Evidence.a1_immutable_overlay_artifact_count -le 0) {
    throw "T05_A1_R2_OVERLAY_NOT_RECORDED"
}
if ($Evidence.exact_profile.artifact_id -ne $ExpectedProfileId) {
    throw "T05_A1_R2_EVIDENCE_PROFILE_MISMATCH"
}
if ($Evidence.t06a_gate_result.artifact_id -ne $ExpectedT06AResultId) {
    throw "T05_A1_R2_EVIDENCE_T06A_RESULT_MISMATCH"
}
if ($Evidence.t06a_gate_proof.artifact_id -ne $ExpectedT06AProofId) {
    throw "T05_A1_R2_EVIDENCE_T06A_PROOF_MISMATCH"
}

if ($Io.attempt_count -ne 0) {
    throw "T05_A1_R2_PURE_CORE_IO_ATTEMPT_PRESENT"
}
if ((@($Io.runs) | Measure-Object).Count -ne 4) {
    throw "T05_A1_R2_PURE_CORE_RUN_COUNT_NOT_4"
}
if ($Pointer.mixed_generation_detected -ne $false) {
    throw "T05_A1_R2_MIXED_GENERATION_DETECTED"
}
if ([int]$Pointer.foundation_pointer_read_count -ne 0) {
    throw "T05_A1_R2_FOUNDATION_POINTER_READ_DETECTED"
}

if ($Proof.semantic_payload.proof_kind -ne 'REQUEST_ASSEMBLY_DETERMINISM') {
    throw "T05_A1_R2_PROOF_KIND_MISMATCH"
}
if ($Proof.semantic_payload.source_gate_id -ne 'T-05') {
    throw "T05_A1_R2_PROOF_SOURCE_GATE_MISMATCH"
}
if ($Proof.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit -or
    $Proof.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T05_A1_R2_PROOF_CANDIDATE_IDENTITY_MISMATCH"
}

if ($Result.semantic_payload.gate_id -ne 'T-05') {
    throw "T05_A1_R2_GATE_ID_MISMATCH"
}
if ($Result.semantic_payload.gate_contract_version -ne 'R14-T-05-v1') {
    throw "T05_A1_R2_GATE_CONTRACT_MISMATCH"
}
if ($Result.semantic_payload.status -ne 'PASS') {
    throw "T05_A1_R2_GATE_RESULT_NOT_PASS"
}
if ((@($Result.semantic_payload.decision_record_refs) | Measure-Object).Count -ne 0) {
    throw "T05_A1_R2_UNEXPECTED_DECISION_RECORD_REFS"
}

$InputIds = @($Result.semantic_payload.input_artifact_refs | ForEach-Object { $_.artifact_id })
if (($InputIds | Measure-Object).Count -ne 2 -or
    $InputIds -notcontains $ExpectedProfileId -or
    $InputIds -notcontains $ExpectedT06AResultId) {
    throw "T05_A1_R2_FORMAL_INPUT_SET_MISMATCH"
}

$ProofSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ProofPath).Hash.ToLowerInvariant()
$ResultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResultPath).Hash.ToLowerInvariant()
$EvidenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidencePath).Hash.ToLowerInvariant()
$MatrixSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $MatrixPath).Hash.ToLowerInvariant()
$PointerSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PointerPath).Hash.ToLowerInvariant()
$IoSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $IoPath).Hash.ToLowerInvariant()
$FreshnessSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $FreshnessPath).Hash.ToLowerInvariant()
$PytestSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PytestPath).Hash.ToLowerInvariant()
$SummarySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SummaryPath).Hash.ToLowerInvariant()

$CommitAfter = (& git -C $Repo rev-parse HEAD).Trim()
$TreeAfter = (& git -C $Repo show -s --format=%T HEAD).Trim()
$StatusAfter = & git -C $Repo status --porcelain

if ($CommitAfter -ne $ExpectedCommit -or $TreeAfter -ne $ExpectedTree -or $StatusAfter) {
    throw "T05_A1_R2_CANDIDATE_CHANGED_OR_DIRTY_AFTER_GATE"
}

Write-Host ""
Write-Host "T05_A1_R2_LAUNCHER_STATUS=PASS"
Write-Host "T05_FORMAL_GATE_EXECUTED=YES"
Write-Host "T05_FORMAL_STATUS=PASS"
Write-Host "T05_CASES_PASS=12/12"
Write-Host "T05_NEGATIVE_AGE_FIXTURE_WINDOW_VALID=YES"
Write-Host "T05_PURE_CORE_IO_ATTEMPTS=0"
Write-Host "T05_POINTER_SWITCH_MIXED_GENERATION=NO"
Write-Host "T05_FOUNDATION_POINTER_READS=0"
Write-Host "T05_A1_OVERLAY_ARTIFACT_COUNT=$($Evidence.a1_immutable_overlay_artifact_count)"
Write-Host "T05_GATE_PROOF_ID=$($Proof.artifact_id)"
Write-Host "T05_GATE_PROOF_CONTENT_SHA256=$($Proof.content_sha256)"
Write-Host "T05_GATE_PROOF_FILE_SHA256=$ProofSha"
Write-Host "T05_GATE_RESULT_ID=$($Result.artifact_id)"
Write-Host "T05_GATE_RESULT_CONTENT_SHA256=$($Result.content_sha256)"
Write-Host "T05_GATE_RESULT_FILE_SHA256=$ResultSha"
Write-Host "T05_EXECUTION_EVIDENCE_SHA256=$EvidenceSha"
Write-Host "T05_DIRECT_MATRIX_SHA256=$MatrixSha"
Write-Host "T05_POINTER_SWITCH_TRACE_SHA256=$PointerSha"
Write-Host "T05_PURE_CORE_IO_PROOF_SHA256=$IoSha"
Write-Host "T05_FRESHNESS_REPORT_SHA256=$FreshnessSha"
Write-Host "T05_PYTEST_LOG_SHA256=$PytestSha"
Write-Host "T05_SUMMARY_SHA256=$SummarySha"
Write-Host "T05_RUN_DIRECTORY=$RunDir"
Write-Host "OWNER_DECISION_REQUIRED=NO"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-07"
