$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t04-gate-a1-20261001.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'

$ExpectedGateSha = '41b93d6578ce67ac52b2fd054fac5e229cac7e2e38980e0f3fbcaf2ac699a45d'
$T01Helper = 'C:\CaptivPortal-Lab\tools\task04-t01-gate-a1-20261001.py'
$ExpectedT01Sha = 'ac8a73606c8136fae3486ec63ee3ffe200852bbdbf53dc4b72144f369055f6b4'

foreach ($Path in @($Gate,$Python,$Repo,$FoundationDb,$T01Helper)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T04_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualT01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T01Helper).Hash.ToLowerInvariant()

Write-Host "T04_A1_GATE_SHA256=$ActualGateSha"
Write-Host "T04_A1_T01_HELPER_SHA256=$ActualT01Sha"

if ($ActualGateSha -ne $ExpectedGateSha) {
    throw "T04_A1_GATE_SHA256_MISMATCH"
}
if ($ActualT01Sha -ne $ExpectedT01Sha) {
    throw "T04_A1_T01_HELPER_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne '8a39459be3ce7ed40e325736034245f0025cf249') {
    throw "T04_A1_CANDIDATE_COMMIT_MISMATCH"
}
if ($Tree -ne 'e2521f27c9f91978e381bce202ab3e3c83aa6dad') {
    throw "T04_A1_CANDIDATE_TREE_MISMATCH"
}
if ($Status) {
    throw "T04_A1_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t04\official-run-$Stamp-T04-A1-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t04-a1-pyc'

try {
    & $Python $Gate `
        --repo $Repo `
        --foundation-control-db $FoundationDb `
        --output-dir $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T04_PROCESS_EXIT_CODE=$Rc"
Write-Host "T04_OUTPUT_ROOT=$OutputDir"

if ($Rc -ne 0) {
    throw "T04_A1_FORMAL_FAILED exit_code=$Rc"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputDir -Directory)
$RunCount = ($RunDirs | Measure-Object).Count
if ($RunCount -ne 1) {
    throw "T04_A1_RUN_DIRECTORY_COUNT_NOT_ONE count=$RunCount"
}

$RunDir = $RunDirs[0].FullName

$ResultPath = Join-Path $RunDir 't04-gate-result-manifest.json'
$ProofPath = Join-Path $RunDir 't04-gate-proof-artifact.json'
$EvidencePath = Join-Path $RunDir 't04-execution-evidence.json'
$ArtifactsPath = Join-Path $RunDir 't04-artifacts.json'
$VectorsPath = Join-Path $RunDir 't04-vector-results.json'
$PytestPath = Join-Path $RunDir 't04-pytest.log'
$SummaryPath = Join-Path $RunDir 't04-summary.txt'

foreach ($Path in @(
    $ResultPath,$ProofPath,$EvidencePath,$ArtifactsPath,
    $VectorsPath,$PytestPath,$SummaryPath
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T04_A1_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
$Evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json
$Vectors = Get-Content -LiteralPath $VectorsPath -Raw | ConvertFrom-Json

if ($Result.semantic_payload.gate_id -ne 'T-04') {
    throw "T04_GATE_ID_MISMATCH"
}
if ($Result.semantic_payload.gate_contract_version -ne 'R14-T-04-v1') {
    throw "T04_GATE_CONTRACT_MISMATCH"
}
if ($Result.semantic_payload.status -ne 'PASS') {
    throw "T04_GATE_RESULT_NOT_PASS"
}
if ($Result.semantic_payload.candidate_repository_commit_sha -ne $Commit) {
    throw "T04_GATE_COMMIT_MISMATCH"
}
if ($Result.semantic_payload.candidate_repository_tree_sha -ne $Tree) {
    throw "T04_GATE_TREE_MISMATCH"
}
if ((@($Result.semantic_payload.decision_record_refs) | Measure-Object).Count -ne 0) {
    throw "T04_UNEXPECTED_DECISION_RECORD_REFS"
}

if ($Proof.semantic_payload.proof_kind -ne 'FUSION_EXECUTION') {
    throw "T04_PROOF_KIND_MISMATCH"
}
if ($Proof.semantic_payload.source_gate_id -ne 'T-04') {
    throw "T04_PROOF_SOURCE_GATE_MISMATCH"
}

$CaseProperties = @($Evidence.scenario_matrix.cases.PSObject.Properties)
$CaseCount = ($CaseProperties | Measure-Object).Count

Write-Host "T04_CASE_COUNT=$CaseCount"

if ($CaseCount -ne 10) {
    throw "T04_CASE_COUNT_NOT_TEN count=$CaseCount"
}

$ExpectedCases = 1..10 | ForEach-Object { 'T04-M{0:d2}' -f $_ }
$ActualCases = @($CaseProperties | ForEach-Object { $_.Name } | Sort-Object)

if (($ActualCases -join ',') -ne (($ExpectedCases | Sort-Object) -join ',')) {
    throw "T04_CASE_SET_MISMATCH actual=$($ActualCases -join ',')"
}

foreach ($Case in $CaseProperties) {
    if ($Case.Value.status -ne 'PASS') {
        throw "T04_CASE_FAILURE: $($Case.Name)"
    }
}

if ($Evidence.scenario_matrix.all_pass -ne $true) {
    throw "T04_SCENARIO_MATRIX_NOT_PASS"
}

if ([int]$Evidence.pytest_exit_status -ne 0) {
    throw "T04_PYTEST_NOT_PASS"
}

$VectorRows = @($Vectors.vectors)
$VectorCount = ($VectorRows | Measure-Object).Count

Write-Host "T04_POLICY_VECTOR_COUNT=$VectorCount"

if ([int]$Vectors.cell_count -ne 40) {
    throw "T04_POLICY_CELL_COUNT_NOT_40"
}
if ($VectorCount -ne 40) {
    throw "T04_POLICY_VECTOR_COUNT_NOT_40"
}
if ($Vectors.all_pass -ne $true) {
    throw "T04_POLICY_VECTORS_NOT_PASS"
}
foreach ($Row in $VectorRows) {
    if ($Row.status -ne 'PASS') {
        throw "T04_POLICY_VECTOR_FAILURE"
    }
}

$ResultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResultPath).Hash.ToLowerInvariant()
$ProofSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ProofPath).Hash.ToLowerInvariant()
$EvidenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidencePath).Hash.ToLowerInvariant()
$ArtifactsSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArtifactsPath).Hash.ToLowerInvariant()
$VectorsSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $VectorsPath).Hash.ToLowerInvariant()
$PytestSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PytestPath).Hash.ToLowerInvariant()
$SummarySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SummaryPath).Hash.ToLowerInvariant()

$CommitAfter = (& git -C $Repo rev-parse HEAD).Trim()
$TreeAfter = (& git -C $Repo show -s --format=%T HEAD).Trim()
$StatusAfter = & git -C $Repo status --porcelain

if ($CommitAfter -ne $Commit -or $TreeAfter -ne $Tree -or $StatusAfter) {
    throw "T04_CANDIDATE_CHANGED_OR_DIRTY_AFTER_GATE"
}

Write-Host ""
Write-Host "T04_A1_LAUNCHER_STATUS=PASS"
Write-Host "T04_FORMAL_GATE_EXECUTED=YES"
Write-Host "T04_FORMAL_STATUS=PASS"
Write-Host "T04_CASES_PASS=10/10"
Write-Host "T04_POLICY_VECTORS_PASS=40/40"
Write-Host "T04_GATE_RESULT_ID=$($Result.artifact_id)"
Write-Host "T04_GATE_RESULT_CONTENT_SHA256=$($Result.content_sha256)"
Write-Host "T04_GATE_RESULT_FILE_SHA256=$ResultSha"
Write-Host "T04_GATE_PROOF_ID=$($Proof.artifact_id)"
Write-Host "T04_GATE_PROOF_CONTENT_SHA256=$($Proof.content_sha256)"
Write-Host "T04_GATE_PROOF_FILE_SHA256=$ProofSha"
Write-Host "T04_EXECUTION_EVIDENCE_SHA256=$EvidenceSha"
Write-Host "T04_ARTIFACTS_SHA256=$ArtifactsSha"
Write-Host "T04_VECTOR_RESULTS_SHA256=$VectorsSha"
Write-Host "T04_PYTEST_LOG_SHA256=$PytestSha"
Write-Host "T04_SUMMARY_SHA256=$SummarySha"
Write-Host "T04_RUN_DIRECTORY=$RunDir"
Write-Host "OWNER_DECISION_REQUIRED=NO"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-06"
