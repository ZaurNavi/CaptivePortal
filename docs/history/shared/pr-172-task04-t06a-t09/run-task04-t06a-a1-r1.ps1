$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t06a-gate-a1-20261001.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'

$T01Helper = 'C:\CaptivPortal-Lab\tools\task04-t01-gate-a1-20261001.py'
$T06Runner = 'C:\CaptivPortal-Lab\tools\task04-t06-gate-a1-20261001.py'
$T06RunDir = 'C:\CaptivPortal-Lab\official-runs\task04\t06\official-run-20261001T121859Z-T06-A1-01\6ca9f53d-1b46-44f3-b4fe-1a2dced4c8a8'

$ExpectedGateSha = 'cd3f22eec438c02b2ef11b9d1febd32aed7508130f6b1ab45caf77b7610567ed'
$ExpectedT01Sha = 'ac8a73606c8136fae3486ec63ee3ffe200852bbdbf53dc4b72144f369055f6b4'
$ExpectedT06RunnerSha = '0d2b5f4c8543a6ab578d1a4c84f613650dc4e72e497c6485c618b5c87f1dca61'
$ExpectedT06ManifestFileSha = 'd0f651952d4e425acbee57d6b1219e676bc60147b43def5033611300e57428c9'
$ExpectedT06ResultFileSha = 'b92e39508967901a3b9d3fd934870f2d8371ce8d5c37312b6761c4a1c00ec010'

$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'

$ExpectedFoundationProfile = 'FoundationRuntimeProfile:v1:sha256:9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5'
$ExpectedKnowledgeBundle = 'KnowledgeBundle:v1:sha256:70c39dcb9ebca5b07f80b0846c394b244c6f700fc4c738e43625f767de0eb660'
$ExpectedPolicy = 'ClassificationPolicy:v1:sha256:5d6c6edab7cfb88bcb42d4badf9bd53dc78f458eae12b4e8b05878fb7f3256c8'
$ExpectedEacs = 'EvidenceAdapterContractSet:v1:sha256:c9711a816fddae6a8d22f2a07c8561fc363c76f7b39f95cde62b66d9957ef32f'
$ExpectedClassifier = 'ClassifierArtifactManifest:v1:sha256:3a1aadd86fbf90c7a0d97f7310a18090c69d755b9a50b2034aa3c289c56bd957'
$ExpectedT06Result = 'GateResultManifest:v1:sha256:250b29ca6c64d7ea8c082ea798c93bf8a684ac7b7479b9f1e167618e40faf70c'

foreach ($Path in @(
    $Gate,$Python,$Repo,$FoundationDb,$T01Helper,$T06Runner,$T06RunDir
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T06A_REQUIRED_PATH_MISSING: $Path"
    }
}

$T06ManifestPath = Join-Path $T06RunDir 't06-manifest.json'
$T06ResultPath = Join-Path $T06RunDir 't06-gate-result-manifest.json'

foreach ($Path in @($T06ManifestPath,$T06ResultPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T06A_T06_PREREQUISITE_FILE_MISSING: $Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualT01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T01Helper).Hash.ToLowerInvariant()
$ActualT06RunnerSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T06Runner).Hash.ToLowerInvariant()
$ActualT06ManifestFileSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T06ManifestPath).Hash.ToLowerInvariant()
$ActualT06ResultFileSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T06ResultPath).Hash.ToLowerInvariant()

Write-Host "T06A_A1_GATE_SHA256=$ActualGateSha"
Write-Host "T06A_A1_T01_HELPER_SHA256=$ActualT01Sha"
Write-Host "T06A_A1_T06_RUNNER_SHA256=$ActualT06RunnerSha"
Write-Host "T06A_A1_T06_MANIFEST_FILE_SHA256=$ActualT06ManifestFileSha"
Write-Host "T06A_A1_T06_RESULT_FILE_SHA256=$ActualT06ResultFileSha"

if ($ActualGateSha -ne $ExpectedGateSha) {
    throw "T06A_A1_GATE_SHA256_MISMATCH"
}
if ($ActualT01Sha -ne $ExpectedT01Sha) {
    throw "T06A_A1_T01_HELPER_SHA256_MISMATCH"
}
if ($ActualT06RunnerSha -ne $ExpectedT06RunnerSha) {
    throw "T06A_A1_T06_RUNNER_SHA256_MISMATCH"
}
if ($ActualT06ManifestFileSha -ne $ExpectedT06ManifestFileSha) {
    throw "T06A_A1_T06_MANIFEST_FILE_SHA256_MISMATCH"
}
if ($ActualT06ResultFileSha -ne $ExpectedT06ResultFileSha) {
    throw "T06A_A1_T06_RESULT_FILE_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne $ExpectedCommit) {
    throw "T06A_A1_CANDIDATE_COMMIT_MISMATCH"
}
if ($Tree -ne $ExpectedTree) {
    throw "T06A_A1_CANDIDATE_TREE_MISMATCH"
}
if ($Status) {
    throw "T06A_A1_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$T06Manifest = Get-Content -LiteralPath $T06ManifestPath -Raw | ConvertFrom-Json
$T06Result = Get-Content -LiteralPath $T06ResultPath -Raw | ConvertFrom-Json

if ($T06Manifest.artifact_id -ne $ExpectedClassifier) {
    throw "T06A_A1_T06_MANIFEST_ID_MISMATCH"
}
if ($T06Result.artifact_id -ne $ExpectedT06Result) {
    throw "T06A_A1_T06_RESULT_ID_MISMATCH"
}
if ($T06Result.semantic_payload.status -ne 'PASS') {
    throw "T06A_A1_T06_NOT_PASS"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t06a\official-run-$Stamp-T06A-A1-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t06a-a1-pyc'

try {
    & $Python $Gate `
        --repo $Repo `
        --foundation-control-db $FoundationDb `
        --t06-run-dir $T06RunDir `
        --output-dir $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T06A_PROCESS_EXIT_CODE=$Rc"
Write-Host "T06A_OUTPUT_ROOT=$OutputDir"

if ($Rc -ne 0) {
    throw "T06A_A1_FORMAL_FAILED exit_code=$Rc"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputDir -Directory)
$RunCount = ($RunDirs | Measure-Object).Count

if ($RunCount -ne 1) {
    throw "T06A_A1_RUN_DIRECTORY_COUNT_NOT_ONE count=$RunCount"
}

$RunDir = $RunDirs[0].FullName

$ProfilePath = Join-Path $RunDir 't06a-classification-runtime-profile.json'
$ProofPath = Join-Path $RunDir 't06a-gate-proof-artifact.json'
$ResultPath = Join-Path $RunDir 't06a-gate-result-manifest.json'
$ReportPath = Join-Path $RunDir 't06a-compatibility-report.json'
$GraphPath = Join-Path $RunDir 't06a-dependency-graph.json'
$EvidencePath = Join-Path $RunDir 't06a-execution-evidence.json'
$SummaryPath = Join-Path $RunDir 't06a-summary.txt'

foreach ($Path in @(
    $ProfilePath,$ProofPath,$ResultPath,$ReportPath,
    $GraphPath,$EvidencePath,$SummaryPath
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T06A_A1_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Profile = Get-Content -LiteralPath $ProfilePath -Raw | ConvertFrom-Json
$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$Report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
$Graph = Get-Content -LiteralPath $GraphPath -Raw | ConvertFrom-Json
$Evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json

if ($Profile.artifact_type -ne 'ClassificationRuntimeProfile') {
    throw "T06A_PROFILE_TYPE_MISMATCH"
}

$P = $Profile.semantic_payload

if ([int]$P.classification_runtime_profile_contract_version -ne 1) {
    throw "T06A_PROFILE_CONTRACT_VERSION_MISMATCH"
}
if ($P.foundation_runtime_profile.artifact_id -ne $ExpectedFoundationProfile) {
    throw "T06A_FOUNDATION_PROFILE_REF_MISMATCH"
}
if ($P.knowledge_bundle.artifact_id -ne $ExpectedKnowledgeBundle) {
    throw "T06A_KNOWLEDGE_BUNDLE_REF_MISMATCH"
}
if ($P.classification_policy.artifact_id -ne $ExpectedPolicy) {
    throw "T06A_POLICY_REF_MISMATCH"
}
if ($P.evidence_adapter_contract_set.artifact_id -ne $ExpectedEacs) {
    throw "T06A_EACS_REF_MISMATCH"
}
if ($P.classifier_artifact_manifest.artifact_id -ne $ExpectedClassifier) {
    throw "T06A_CLASSIFIER_REF_MISMATCH"
}

$Checks = @($Report.checks)
$CheckCount = ($Checks | Measure-Object).Count
Write-Host "T06A_COMPATIBILITY_CHECK_COUNT=$CheckCount"

if ($CheckCount -ne 9) {
    throw "T06A_COMPATIBILITY_CHECK_COUNT_NOT_9 count=$CheckCount"
}
foreach ($Check in $Checks) {
    if ($Check.status -ne 'PASS') {
        throw "T06A_COMPATIBILITY_CHECK_FAILED: $($Check.check_id)"
    }
}
if ($Report.all_pass -ne $true) {
    throw "T06A_COMPATIBILITY_REPORT_NOT_PASS"
}
if ($null -ne $Report.failure_code) {
    throw "T06A_UNEXPECTED_FAILURE_CODE=$($Report.failure_code)"
}

if ($null -ne $Graph.cycle_witness) {
    throw "T06A_DEPENDENCY_CYCLE_PRESENT"
}

$NodeCount = [int]$Graph.node_count
$TopoCount = (@($Graph.topological_order) | Measure-Object).Count
Write-Host "T06A_DEPENDENCY_NODE_COUNT=$NodeCount"
Write-Host "T06A_TOPOLOGICAL_ORDER_COUNT=$TopoCount"

if ($NodeCount -le 0 -or $TopoCount -ne $NodeCount) {
    throw "T06A_TOPOLOGICAL_ORDER_INCOMPLETE"
}

$AcceptanceNodes = @(
    $Graph.nodes | Where-Object { $_.artifact_type -eq 'Task04AcceptanceManifest' }
)
if (($AcceptanceNodes | Measure-Object).Count -ne 0) {
    throw "T06A_ACCEPTANCE_BACK_REFERENCE_PRESENT"
}

if ($Evidence.compatibility_all_pass -ne $true) {
    throw "T06A_EVIDENCE_COMPATIBILITY_NOT_PASS"
}
if ($Evidence.dependency_graph_acyclic -ne $true) {
    throw "T06A_EVIDENCE_GRAPH_NOT_ACYCLIC"
}
if ($Evidence.no_acceptance_back_reference -ne $true) {
    throw "T06A_EVIDENCE_ACCEPTANCE_BACKREF_FAILURE"
}

if ($Evidence.knowledge_bundle.artifact_id -ne $ExpectedKnowledgeBundle) {
    throw "T06A_EVIDENCE_KB_MISMATCH"
}
if ($Evidence.classification_policy.artifact_id -ne $ExpectedPolicy) {
    throw "T06A_EVIDENCE_POLICY_MISMATCH"
}
if ($Evidence.evidence_adapter_contract_set.artifact_id -ne $ExpectedEacs) {
    throw "T06A_EVIDENCE_EACS_MISMATCH"
}
if ($Evidence.classifier_artifact_manifest.artifact_id -ne $ExpectedClassifier) {
    throw "T06A_EVIDENCE_CLASSIFIER_MISMATCH"
}
if ($Evidence.t06_gate_result.artifact_id -ne $ExpectedT06Result) {
    throw "T06A_EVIDENCE_T06_RESULT_MISMATCH"
}

if ($Proof.semantic_payload.proof_kind -ne 'CLASSIFICATION_PROFILE_COMPATIBILITY') {
    throw "T06A_PROOF_KIND_MISMATCH"
}
if ($Proof.semantic_payload.source_gate_id -ne 'T-06A') {
    throw "T06A_PROOF_SOURCE_GATE_MISMATCH"
}
if ($Proof.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit) {
    throw "T06A_PROOF_COMMIT_MISMATCH"
}
if ($Proof.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T06A_PROOF_TREE_MISMATCH"
}

if ($Result.semantic_payload.gate_id -ne 'T-06A') {
    throw "T06A_GATE_ID_MISMATCH"
}
if ($Result.semantic_payload.gate_contract_version -ne 'R14-T-06A-v1') {
    throw "T06A_GATE_CONTRACT_MISMATCH"
}
if ($Result.semantic_payload.status -ne 'PASS') {
    throw "T06A_GATE_RESULT_NOT_PASS"
}
if ($Result.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit) {
    throw "T06A_RESULT_COMMIT_MISMATCH"
}
if ($Result.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T06A_RESULT_TREE_MISMATCH"
}
if ((@($Result.semantic_payload.decision_record_refs) | Measure-Object).Count -ne 0) {
    throw "T06A_UNEXPECTED_DECISION_RECORD_REFS"
}

$OutputRefs = @($Result.semantic_payload.output_artifact_refs)
if (($OutputRefs | Measure-Object).Count -ne 2) {
    throw "T06A_OUTPUT_REF_COUNT_NOT_2"
}

$OutputIds = @($OutputRefs | ForEach-Object { $_.artifact_id })
if ($OutputIds -notcontains $Profile.artifact_id) {
    throw "T06A_PROFILE_NOT_IN_OUTPUT_REFS"
}
if ($OutputIds -notcontains $Proof.artifact_id) {
    throw "T06A_PROOF_NOT_IN_OUTPUT_REFS"
}

$ProfileSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ProfilePath).Hash.ToLowerInvariant()
$ProofSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ProofPath).Hash.ToLowerInvariant()
$ResultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResultPath).Hash.ToLowerInvariant()
$ReportSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ReportPath).Hash.ToLowerInvariant()
$GraphSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $GraphPath).Hash.ToLowerInvariant()
$EvidenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidencePath).Hash.ToLowerInvariant()
$SummarySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SummaryPath).Hash.ToLowerInvariant()

$CommitAfter = (& git -C $Repo rev-parse HEAD).Trim()
$TreeAfter = (& git -C $Repo show -s --format=%T HEAD).Trim()
$StatusAfter = & git -C $Repo status --porcelain

if ($CommitAfter -ne $ExpectedCommit -or $TreeAfter -ne $ExpectedTree -or $StatusAfter) {
    throw "T06A_CANDIDATE_CHANGED_OR_DIRTY_AFTER_GATE"
}

Write-Host ""
Write-Host "T06A_A1_LAUNCHER_STATUS=PASS"
Write-Host "T06A_FORMAL_GATE_EXECUTED=YES"
Write-Host "T06A_FORMAL_STATUS=PASS"
Write-Host "T06A_COMPATIBILITY_CHECKS_PASS=9/9"
Write-Host "T06A_DEPENDENCY_GRAPH_ACYCLIC=YES"
Write-Host "T06A_ACCEPTANCE_BACK_REFERENCE=NO"
Write-Host "CLASSIFICATION_RUNTIME_PROFILE_ID=$($Profile.artifact_id)"
Write-Host "CLASSIFICATION_RUNTIME_PROFILE_CONTENT_SHA256=$($Profile.content_sha256)"
Write-Host "CLASSIFICATION_RUNTIME_PROFILE_FILE_SHA256=$ProfileSha"
Write-Host "T06A_GATE_PROOF_ID=$($Proof.artifact_id)"
Write-Host "T06A_GATE_PROOF_CONTENT_SHA256=$($Proof.content_sha256)"
Write-Host "T06A_GATE_PROOF_FILE_SHA256=$ProofSha"
Write-Host "T06A_GATE_RESULT_ID=$($Result.artifact_id)"
Write-Host "T06A_GATE_RESULT_CONTENT_SHA256=$($Result.content_sha256)"
Write-Host "T06A_GATE_RESULT_FILE_SHA256=$ResultSha"
Write-Host "T06A_COMPATIBILITY_REPORT_SHA256=$ReportSha"
Write-Host "T06A_DEPENDENCY_GRAPH_SHA256=$GraphSha"
Write-Host "T06A_EXECUTION_EVIDENCE_SHA256=$EvidenceSha"
Write-Host "T06A_SUMMARY_SHA256=$SummarySha"
Write-Host "T06A_RUN_DIRECTORY=$RunDir"
Write-Host "OWNER_DECISION_REQUIRED=NO"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-05"
