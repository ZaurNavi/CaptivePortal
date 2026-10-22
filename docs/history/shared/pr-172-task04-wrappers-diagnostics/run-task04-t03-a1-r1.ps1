$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t03-gate-a1-20261001.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$ExpectedSha = '4010e3766df422af7c4e9a1346af73c97a147e3f195675013c7432165c43874f'

if (-not (Test-Path -LiteralPath $Gate)) {
    throw "T03_A1_GATE_MISSING: $Gate"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "PYTHON_MISSING: $Python"
}
if (-not (Test-Path -LiteralPath $Repo)) {
    throw "A1_REPOSITORY_MISSING: $Repo"
}
if (-not (Test-Path -LiteralPath $FoundationDb)) {
    throw "FOUNDATION_CONTROL_DB_MISSING: $FoundationDb"
}

$ActualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
Write-Host "T03_A1_GATE_SHA256=$ActualSha"

if ($ActualSha -ne $ExpectedSha) {
    throw "T03_A1_GATE_SHA256_MISMATCH expected=$ExpectedSha actual=$ActualSha"
}

$T01Helper = 'C:\CaptivPortal-Lab\tools\task04-t01-gate-a1-20261001.py'
$ExpectedT01Sha = 'ac8a73606c8136fae3486ec63ee3ffe200852bbdbf53dc4b72144f369055f6b4'

if (-not (Test-Path -LiteralPath $T01Helper)) {
    throw "T03_A1_T01_HELPER_MISSING"
}

$ActualT01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T01Helper).Hash.ToLowerInvariant()
Write-Host "T03_A1_T01_HELPER_SHA256=$ActualT01Sha"

if ($ActualT01Sha -ne $ExpectedT01Sha) {
    throw "T03_A1_T01_HELPER_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne '8a39459be3ce7ed40e325736034245f0025cf249') {
    throw "T03_A1_CANDIDATE_COMMIT_MISMATCH"
}
if ($Tree -ne 'e2521f27c9f91978e381bce202ab3e3c83aa6dad') {
    throw "T03_A1_CANDIDATE_TREE_MISMATCH"
}
if ($Status) {
    throw "T03_A1_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t03\official-run-$Stamp-T03-A1-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t03-a1-pyc'

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

Write-Host "T03_PROCESS_EXIT_CODE=$Rc"
Write-Host "T03_OUTPUT_ROOT=$OutputDir"

if ($Rc -ne 0) {
    throw "T03_A1_FORMAL_FAILED exit_code=$Rc"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputDir -Directory)
if ($RunDirs.Count -ne 1) {
    throw "T03_A1_RUN_DIRECTORY_COUNT_NOT_ONE count=$($RunDirs.Count)"
}

$RunDir = $RunDirs[0].FullName
$ResultPath = Join-Path $RunDir 't03-gate-result-manifest.json'
$ProofPath = Join-Path $RunDir 't03-gate-proof-artifact.json'
$EvidencePath = Join-Path $RunDir 't03-execution-evidence.json'
$ArtifactsPath = Join-Path $RunDir 't03-artifacts.json'
$PytestPath = Join-Path $RunDir 't03-pytest.log'

foreach ($Path in @($ResultPath,$ProofPath,$EvidencePath,$ArtifactsPath,$PytestPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T03_A1_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
$Evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json

if ($Result.semantic_payload.gate_id -ne 'T-03') {
    throw "T03_A1_GATE_ID_MISMATCH"
}
if ($Result.semantic_payload.gate_contract_version -ne 'R14-T-03-v1') {
    throw "T03_A1_GATE_CONTRACT_MISMATCH"
}
if ($Result.semantic_payload.status -ne 'PASS') {
    throw "T03_A1_GATE_RESULT_NOT_PASS"
}
if ($Result.semantic_payload.candidate_repository_commit_sha -ne $Commit) {
    throw "T03_A1_GATE_COMMIT_MISMATCH"
}
if ($Result.semantic_payload.candidate_repository_tree_sha -ne $Tree) {
    throw "T03_A1_GATE_TREE_MISMATCH"
}
if (@($Result.semantic_payload.decision_record_refs).Count -ne 0) {
    throw "T03_A1_UNEXPECTED_DECISION_RECORD_REFS"
}
if ($Proof.semantic_payload.proof_kind -ne 'ORIGIN_ASSESSMENT_EXECUTION') {
    throw "T03_A1_PROOF_KIND_MISMATCH"
}
if ($Proof.semantic_payload.source_gate_id -ne 'T-03') {
    throw "T03_A1_PROOF_GATE_MISMATCH"
}

$Cases = $Evidence.matrix.cases.PSObject.Properties
if ($Cases.Count -ne 12) {
    throw "T03_A1_CASE_COUNT_NOT_TWELVE count=$($Cases.Count)"
}
foreach ($Case in $Cases) {
    if ($Case.Value.status -ne 'PASS') {
        throw "T03_A1_CASE_FAILURE: $($Case.Name)"
    }
}
if (-not $Evidence.matrix.all_pass) {
    throw "T03_A1_MATRIX_NOT_PASS"
}
if ($Evidence.pytest_exit_status -ne 0) {
    throw "T03_A1_PYTEST_NOT_PASS"
}

$ResultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResultPath).Hash.ToLowerInvariant()
$ProofSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ProofPath).Hash.ToLowerInvariant()
$EvidenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidencePath).Hash.ToLowerInvariant()
$ArtifactsSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArtifactsPath).Hash.ToLowerInvariant()
$PytestSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PytestPath).Hash.ToLowerInvariant()

Write-Host ""
Write-Host "T03_A1_LAUNCHER_STATUS=PASS"
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
Write-Host "T03_RUN_DIRECTORY=$RunDir"
Write-Host "OWNER_DECISION_REQUIRED=NO"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-04"
