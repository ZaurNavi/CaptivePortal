$ErrorActionPreference = 'Stop'

$OutputRoot = 'C:\CaptivPortal-Lab\official-runs\task04\t03\official-run-20261001T120322Z-T03-A1-01'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'

$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'

if (-not (Test-Path -LiteralPath $OutputRoot)) {
    throw "T03_EXISTING_OUTPUT_ROOT_MISSING: $OutputRoot"
}

if (-not (Test-Path -LiteralPath $Repo)) {
    throw "T03_REPOSITORY_MISSING: $Repo"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

if ($Commit -ne $ExpectedCommit) {
    throw "T03_CANDIDATE_COMMIT_MISMATCH"
}

if ($Tree -ne $ExpectedTree) {
    throw "T03_CANDIDATE_TREE_MISMATCH"
}

if ($Status) {
    throw "T03_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputRoot -Directory)

if (($RunDirs | Measure-Object).Count -ne 1) {
    throw "T03_EXISTING_RUN_DIRECTORY_COUNT_NOT_ONE count=$(($RunDirs | Measure-Object).Count)"
}

$RunDir = $RunDirs[0].FullName

$ResultPath = Join-Path $RunDir 't03-gate-result-manifest.json'
$ProofPath = Join-Path $RunDir 't03-gate-proof-artifact.json'
$EvidencePath = Join-Path $RunDir 't03-execution-evidence.json'
$ArtifactsPath = Join-Path $RunDir 't03-artifacts.json'
$PytestPath = Join-Path $RunDir 't03-pytest.log'
$SummaryPath = Join-Path $RunDir 't03-summary.txt'

foreach ($Path in @(
    $ResultPath,
    $ProofPath,
    $EvidencePath,
    $ArtifactsPath,
    $PytestPath,
    $SummaryPath
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T03_EXISTING_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
$Evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json

if ($Result.artifact_type -ne 'GateResultManifest') {
    throw "T03_RESULT_ARTIFACT_TYPE_MISMATCH"
}

if ($Result.semantic_payload.gate_id -ne 'T-03') {
    throw "T03_GATE_ID_MISMATCH"
}

if ($Result.semantic_payload.gate_contract_version -ne 'R14-T-03-v1') {
    throw "T03_GATE_CONTRACT_MISMATCH"
}

if ($Result.semantic_payload.status -ne 'PASS') {
    throw "T03_GATE_RESULT_NOT_PASS"
}

if ($Result.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit) {
    throw "T03_GATE_COMMIT_MISMATCH"
}

if ($Result.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T03_GATE_TREE_MISMATCH"
}

$DecisionRefs = @($Result.semantic_payload.decision_record_refs)
if (($DecisionRefs | Measure-Object).Count -ne 0) {
    throw "T03_UNEXPECTED_DECISION_RECORD_REFS"
}

if ($Proof.artifact_type -ne 'GateProofArtifact') {
    throw "T03_PROOF_ARTIFACT_TYPE_MISMATCH"
}

if ($Proof.semantic_payload.proof_kind -ne 'ORIGIN_ASSESSMENT_EXECUTION') {
    throw "T03_PROOF_KIND_MISMATCH"
}

if ($Proof.semantic_payload.source_gate_id -ne 'T-03') {
    throw "T03_PROOF_SOURCE_GATE_MISMATCH"
}

if ($Proof.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit) {
    throw "T03_PROOF_COMMIT_MISMATCH"
}

if ($Proof.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T03_PROOF_TREE_MISMATCH"
}

$CaseProperties = @($Evidence.matrix.cases.PSObject.Properties)
$CaseCount = ($CaseProperties | Measure-Object).Count

Write-Host "T03_CASE_COUNT=$CaseCount"

if ($CaseCount -ne 12) {
    throw "T03_CASE_COUNT_NOT_TWELVE count=$CaseCount"
}

$ExpectedCaseNames = 1..12 | ForEach-Object { 'T03-M{0:d2}' -f $_ }
$ActualCaseNames = @($CaseProperties | ForEach-Object { $_.Name } | Sort-Object)

if (($ActualCaseNames -join ',') -ne (($ExpectedCaseNames | Sort-Object) -join ',')) {
    throw "T03_CASE_SET_MISMATCH actual=$($ActualCaseNames -join ',')"
}

foreach ($Case in $CaseProperties) {
    if ($Case.Value.status -ne 'PASS') {
        throw "T03_CASE_FAILURE: $($Case.Name)"
    }
}

if ($Evidence.matrix.all_pass -ne $true) {
    throw "T03_MATRIX_NOT_PASS"
}

if ([int]$Evidence.pytest_exit_status -ne 0) {
    throw "T03_PYTEST_NOT_PASS"
}

$ResultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResultPath).Hash.ToLowerInvariant()
$ProofSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ProofPath).Hash.ToLowerInvariant()
$EvidenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidencePath).Hash.ToLowerInvariant()
$ArtifactsSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArtifactsPath).Hash.ToLowerInvariant()
$PytestSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PytestPath).Hash.ToLowerInvariant()
$SummarySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SummaryPath).Hash.ToLowerInvariant()

# Final repository immutability check.
$CommitAfter = (& git -C $Repo rev-parse HEAD).Trim()
$TreeAfter = (& git -C $Repo show -s --format=%T HEAD).Trim()
$StatusAfter = & git -C $Repo status --porcelain

if ($CommitAfter -ne $ExpectedCommit) {
    throw "T03_CANDIDATE_COMMIT_CHANGED"
}

if ($TreeAfter -ne $ExpectedTree) {
    throw "T03_CANDIDATE_TREE_CHANGED"
}

if ($StatusAfter) {
    throw "T03_CANDIDATE_WORKTREE_DIRTY"
}

Write-Host ""
Write-Host "T03_POSTVALIDATION_STATUS=PASS"
Write-Host "T03_FORMAL_GATE_RERUN=NO"
Write-Host "T03_FORMAL_GATE_EXECUTED=YES"
Write-Host "T03_FORMAL_STATUS=PASS"
Write-Host "T03_CASES_PASS=12/12"
Write-Host "T03_GATE_RESULT_ID=$($Result.artifact_id)"
Write-Host "T03_GATE_RESULT_CONTENT_SHA256=$($Result.content_sha256)"
Write-Host "T03_GATE_RESULT_FILE_SHA256=$ResultSha"
Write-Host "T03_GATE_PROOF_ID=$($Proof.artifact_id)"
Write-Host "T03_GATE_PROOF_CONTENT_SHA256=$($Proof.content_sha256)"
Write-Host "T03_GATE_PROOF_FILE_SHA256=$ProofSha"
Write-Host "T03_EXECUTION_EVIDENCE_SHA256=$EvidenceSha"
Write-Host "T03_ARTIFACTS_SHA256=$ArtifactsSha"
Write-Host "T03_PYTEST_LOG_SHA256=$PytestSha"
Write-Host "T03_SUMMARY_SHA256=$SummarySha"
Write-Host "T03_RUN_DIRECTORY=$RunDir"
Write-Host "OWNER_DECISION_REQUIRED=NO"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-04"
