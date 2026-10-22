$ErrorActionPreference = 'Stop'

$OutputRoot = 'C:\CaptivPortal-Lab\official-runs\task04\t08\official-run-20261002T054636Z-T08-A1-01'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$Gate = 'C:\CaptivPortal-Lab\tools\task04-t08-gate-a1-20261002.py'
$T07Helper = 'C:\CaptivPortal-Lab\tools\task04-t07-gate-a1-20261002.py'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$Task01Db = 'C:\CaptivPortal-Lab\gates\task04\t07\inputs\task01-source-r2.sqlite3'

$ExpectedGateSha = '2c9d1f5a1580cdbb849f01d1bf776b0664ce08caa0e522f77dc0410c7ee83b24'
$ExpectedT07Sha = 'bbe90933dd4526f4b0cb3c1db65ada38161de0147c476a5be2105bcb7cecf9ac'
$ExpectedTask01Sha = '79cfcfb8c463c235af1d7dfe4f49a8e9ef491a25749ccbeeded85b88f2ee90f9'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'
$ExpectedProfileId = 'ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c'
$ExpectedT06AResultId = 'GateResultManifest:v1:sha256:cd102f0fca7adb9e09ce1ff69d2109b34691e7362fd071a0617fc300547db406'
$ExpectedT06AProofId = 'GateProofArtifact:v1:sha256:6e404961cce296382f03b37e54111b6d535a1e1c44432a8e8f6269290bf64267'

foreach ($Path in @(
    $OutputRoot,$Repo,$Gate,$T07Helper,$FoundationDb,$Task01Db
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T08_POSTVALIDATION_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualT07Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T07Helper).Hash.ToLowerInvariant()
$ActualTask01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Task01Db).Hash.ToLowerInvariant()

Write-Host "T08_GATE_SHA256=$ActualGateSha"
Write-Host "T08_T07_HELPER_SHA256=$ActualT07Sha"
Write-Host "T08_TASK01_DB_SHA256=$ActualTask01Sha"

if ($ActualGateSha -ne $ExpectedGateSha) {
    throw "T08_GATE_SHA256_MISMATCH"
}
if ($ActualT07Sha -ne $ExpectedT07Sha) {
    throw "T08_T07_HELPER_SHA256_MISMATCH"
}
if ($ActualTask01Sha -ne $ExpectedTask01Sha) {
    throw "T08_TASK01_DB_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne $ExpectedCommit) {
    throw "T08_CANDIDATE_COMMIT_MISMATCH"
}
if ($Tree -ne $ExpectedTree) {
    throw "T08_CANDIDATE_TREE_MISMATCH"
}
if ($Status) {
    throw "T08_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputRoot -Directory)
$RunCount = ($RunDirs | Measure-Object).Count
Write-Host "T08_RUN_DIRECTORY_COUNT=$RunCount"

if ($RunCount -ne 1) {
    throw "T08_RUN_DIRECTORY_COUNT_NOT_ONE count=$RunCount"
}

$RunDir = $RunDirs[0].FullName

$ResultPath = Join-Path $RunDir 't08-gate-result-manifest.json'
$ProofPath = Join-Path $RunDir 't08-gate-proof-artifact.json'
$EvidencePath = Join-Path $RunDir 't08-execution-evidence.json'
$MatrixPath = Join-Path $RunDir 't08-fault-network-matrix.json'
$NetworkPath = Join-Path $RunDir 't08-network-denial-report.json'
$IsolationPath = Join-Path $RunDir 't08-isolation-report.json'
$StaticPath = Join-Path $RunDir 't08-static-cloud-path-report.json'
$PytestPath = Join-Path $RunDir 't08-pytest.log'
$SummaryPath = Join-Path $RunDir 't08-summary.txt'

foreach ($Path in @(
    $ResultPath,$ProofPath,$EvidencePath,$MatrixPath,$NetworkPath,
    $IsolationPath,$StaticPath,$PytestPath,$SummaryPath
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T08_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
$Evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json
$Matrix = Get-Content -LiteralPath $MatrixPath -Raw | ConvertFrom-Json
$Network = Get-Content -LiteralPath $NetworkPath -Raw | ConvertFrom-Json
$Isolation = Get-Content -LiteralPath $IsolationPath -Raw | ConvertFrom-Json
$Static = Get-Content -LiteralPath $StaticPath -Raw | ConvertFrom-Json

$CaseProps = @($Matrix.PSObject.Properties)
$CaseCount = ($CaseProps | Measure-Object).Count
Write-Host "T08_CASE_COUNT=$CaseCount"

if ($CaseCount -ne 9) {
    throw "T08_CASE_COUNT_NOT_9 count=$CaseCount"
}
foreach ($Case in $CaseProps) {
    if ($Case.Value.status -ne 'PASS') {
        throw "T08_CASE_FAILURE: $($Case.Name)"
    }
}

if ($Evidence.all_pass -ne $true) {
    throw "T08_EVIDENCE_ALL_PASS_FALSE"
}
if ([int]$Evidence.pytest_exit_status -ne 0) {
    throw "T08_PYTEST_NOT_PASS"
}
if ([int]$Evidence.network_attempt_count -ne 0) {
    throw "T08_EVIDENCE_NETWORK_ATTEMPTS_NONZERO"
}
if ([int]$Evidence.a1_immutable_overlay_artifact_count -ne 17) {
    throw "T08_A1_OVERLAY_COUNT_NOT_17"
}
if ($Evidence.exact_profile.artifact_id -ne $ExpectedProfileId) {
    throw "T08_EVIDENCE_PROFILE_MISMATCH"
}
if ($Evidence.t06a_gate_result.artifact_id -ne $ExpectedT06AResultId) {
    throw "T08_EVIDENCE_T06A_RESULT_MISMATCH"
}
if ($Evidence.t06a_gate_proof.artifact_id -ne $ExpectedT06AProofId) {
    throw "T08_EVIDENCE_T06A_PROOF_MISMATCH"
}

# IMPORTANT:
# NetworkGuard.enabled is an "activated during matrix" flag in this runner.
# __exit__ restores every patched socket/DNS function but intentionally does not
# set enabled=False. Therefore the retained report is expected to say True.
if ($Network.network_guard_enabled -ne $true) {
    throw "T08_NETWORK_GUARD_WAS_NOT_ACTIVATED"
}
if ([int]$Network.network_attempt_count -ne 0) {
    throw "T08_NETWORK_ATTEMPT_PRESENT"
}
if ((@($Network.attempted_destinations) | Measure-Object).Count -ne 0) {
    throw "T08_NETWORK_DESTINATION_ATTEMPT_RECORDED"
}

Write-Host "T08_NETWORK_GUARD_ACTIVATED_DURING_MATRIX=YES"
Write-Host "T08_NETWORK_ATTEMPTS=0"

if ($Isolation.foundation_sha_before -ne $Isolation.foundation_sha_after) {
    throw "T08_FOUNDATION_DB_BYTE_IDENTITY_FAIL"
}
if ($Isolation.task01_sha_before -ne $Isolation.task01_sha_after) {
    throw "T08_TASK01_DB_BYTE_IDENTITY_FAIL"
}
if ($Isolation.repository_unchanged -ne $true) {
    throw "T08_REPOSITORY_ISOLATION_FAIL"
}
if ($Isolation.auth_capport_dependency_absent -ne $true) {
    throw "T08_AUTH_CAPPORT_ISOLATION_FAIL"
}

if ((@($Static.auth_capport_classification_dependency) | Measure-Object).Count -ne 0) {
    throw "T08_STATIC_AUTH_CAPPORT_DEPENDENCY_PRESENT"
}
if ((@($Static.fingerbank_runtime_identifier_files) | Measure-Object).Count -ne 0) {
    throw "T08_STATIC_FINGERBANK_RUNTIME_IDENTIFIER_PRESENT"
}

if ($Proof.artifact_type -ne 'GateProofArtifact') {
    throw "T08_PROOF_TYPE_MISMATCH"
}
if ($Proof.semantic_payload.proof_kind -ne 'OFFLINE_FAILURE_ISOLATION') {
    throw "T08_PROOF_KIND_MISMATCH"
}
if ($Proof.semantic_payload.source_gate_id -ne 'T-08') {
    throw "T08_PROOF_SOURCE_GATE_MISMATCH"
}
if ($Proof.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit -or
    $Proof.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T08_PROOF_CANDIDATE_MISMATCH"
}

if ($Result.artifact_type -ne 'GateResultManifest') {
    throw "T08_RESULT_TYPE_MISMATCH"
}
if ($Result.semantic_payload.gate_id -ne 'T-08') {
    throw "T08_GATE_ID_MISMATCH"
}
if ($Result.semantic_payload.gate_contract_version -ne 'R14-T-08-v1') {
    throw "T08_GATE_CONTRACT_MISMATCH"
}
if ($Result.semantic_payload.status -ne 'PASS') {
    throw "T08_GATE_RESULT_NOT_PASS"
}
if ($Result.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit -or
    $Result.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T08_RESULT_CANDIDATE_MISMATCH"
}
if ((@($Result.semantic_payload.decision_record_refs) | Measure-Object).Count -ne 0) {
    throw "T08_UNEXPECTED_DECISION_RECORD_REFS"
}

$InputIds = @($Result.semantic_payload.input_artifact_refs | ForEach-Object { $_.artifact_id })
if (($InputIds | Measure-Object).Count -ne 2 -or
    $InputIds -notcontains $ExpectedProfileId -or
    $InputIds -notcontains $ExpectedT06AResultId) {
    throw "T08_FORMAL_INPUT_SET_MISMATCH"
}

$SummaryText = Get-Content -LiteralPath $SummaryPath -Raw
if ($SummaryText -notmatch 'GATE_EXECUTION_STATUS=PASS') {
    throw "T08_SUMMARY_NOT_PASS"
}
if ($SummaryText -notmatch 'FAILURE_CODE=NONE') {
    throw "T08_SUMMARY_FAILURE_CODE_NOT_NONE"
}

$ResultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResultPath).Hash.ToLowerInvariant()
$ProofSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ProofPath).Hash.ToLowerInvariant()
$EvidenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidencePath).Hash.ToLowerInvariant()
$MatrixSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $MatrixPath).Hash.ToLowerInvariant()
$NetworkSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $NetworkPath).Hash.ToLowerInvariant()
$IsolationSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $IsolationPath).Hash.ToLowerInvariant()
$StaticSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $StaticPath).Hash.ToLowerInvariant()
$PytestSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PytestPath).Hash.ToLowerInvariant()
$SummarySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SummaryPath).Hash.ToLowerInvariant()

$CommitAfter = (& git -C $Repo rev-parse HEAD).Trim()
$TreeAfter = (& git -C $Repo show -s --format=%T HEAD).Trim()
$StatusAfter = & git -C $Repo status --porcelain

if ($CommitAfter -ne $ExpectedCommit -or $TreeAfter -ne $ExpectedTree -or $StatusAfter) {
    throw "T08_CANDIDATE_CHANGED_OR_DIRTY"
}

Write-Host ""
Write-Host "T08_POSTVALIDATION_STATUS=PASS"
Write-Host "T08_FORMAL_GATE_RERUN=NO"
Write-Host "T08_FORMAL_GATE_EXECUTED=YES"
Write-Host "T08_FORMAL_STATUS=PASS"
Write-Host "T08_CASES_PASS=9/9"
Write-Host "T08_NETWORK_GUARD_REPORT_SEMANTICS=ACTIVATED_DURING_MATRIX"
Write-Host "T08_NETWORK_ATTEMPTS=0"
Write-Host "T08_AUTH_CAPPORT_CLASSIFICATION_DEPENDENCY=NO"
Write-Host "T08_FINGERBANK_RUNTIME_IDENTIFIER=NO"
Write-Host "T08_FOUNDATION_DB_BYTE_IDENTITY=PASS"
Write-Host "T08_TASK01_DB_BYTE_IDENTITY=PASS"
Write-Host "T08_A1_OVERLAY_ARTIFACT_COUNT=$($Evidence.a1_immutable_overlay_artifact_count)"
Write-Host "T08_GATE_PROOF_ID=$($Proof.artifact_id)"
Write-Host "T08_GATE_PROOF_CONTENT_SHA256=$($Proof.content_sha256)"
Write-Host "T08_GATE_PROOF_FILE_SHA256=$ProofSha"
Write-Host "T08_GATE_RESULT_ID=$($Result.artifact_id)"
Write-Host "T08_GATE_RESULT_CONTENT_SHA256=$($Result.content_sha256)"
Write-Host "T08_GATE_RESULT_FILE_SHA256=$ResultSha"
Write-Host "T08_EXECUTION_EVIDENCE_SHA256=$EvidenceSha"
Write-Host "T08_MATRIX_SHA256=$MatrixSha"
Write-Host "T08_NETWORK_REPORT_SHA256=$NetworkSha"
Write-Host "T08_ISOLATION_REPORT_SHA256=$IsolationSha"
Write-Host "T08_STATIC_REPORT_SHA256=$StaticSha"
Write-Host "T08_PYTEST_LOG_SHA256=$PytestSha"
Write-Host "T08_SUMMARY_SHA256=$SummarySha"
Write-Host "T08_RUN_DIRECTORY=$RunDir"
Write-Host "OWNER_DECISION_REQUIRED=NO"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-09"
