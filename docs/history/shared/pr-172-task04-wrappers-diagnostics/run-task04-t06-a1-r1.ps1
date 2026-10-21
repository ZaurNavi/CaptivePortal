$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t06-gate-a1-20261001.py'
$Registration = 'C:\CaptivPortal-Lab\tools\t06-implementation-identity-registration-a1-20261001.json'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$T01Helper = 'C:\CaptivPortal-Lab\tools\task04-t01-gate-a1-20261001.py'

$ExpectedGateSha = '0d2b5f4c8543a6ab578d1a4c84f613650dc4e72e497c6485c618b5c87f1dca61'
$ExpectedRegistrationSha = '5dcbd6bb79157e046f1795f2c2789d4fbc799685a71a9dc4281dc058dd1809c6'
$ExpectedArchitectureSha = '115991601919fa1748ab47c613f5c6dff0a12101f4f47654ca1cebbfa7e696b5'
$ExpectedT01Sha = 'ac8a73606c8136fae3486ec63ee3ffe200852bbdbf53dc4b72144f369055f6b4'

$ArchitectureCandidates = @(
    'C:\CaptivPortal-Lab\tools\DEVICE-FINGERPRINT-03A-R2_TASK-04_ARCHITECTURE_DECISION_R14_FINAL_REPAIRED_ACCEPTED_TTL_TOPOLOGY_REGISTERED.md',
    'C:\Users\Zaur Navi\Downloads\DEVICE-FINGERPRINT-03A-R2_TASK-04_ARCHITECTURE_DECISION_R14_FINAL_REPAIRED_ACCEPTED_TTL_TOPOLOGY_REGISTERED.md'
)

foreach ($Path in @($Gate,$Registration,$Python,$Repo,$FoundationDb,$T01Helper)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T06_REQUIRED_PATH_MISSING: $Path"
    }
}

$Architecture = $null
foreach ($Candidate in $ArchitectureCandidates) {
    if (Test-Path -LiteralPath $Candidate) {
        $CandidateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Candidate).Hash.ToLowerInvariant()
        if ($CandidateSha -eq $ExpectedArchitectureSha) {
            $Architecture = $Candidate
            break
        }
    }
}

if (-not $Architecture) {
    throw "T06_EXACT_R14_ARCHITECTURE_FILE_NOT_FOUND"
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
$ActualRegistrationSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Registration).Hash.ToLowerInvariant()
$ActualArchitectureSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Architecture).Hash.ToLowerInvariant()
$ActualT01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $T01Helper).Hash.ToLowerInvariant()

Write-Host "T06_A1_GATE_SHA256=$ActualGateSha"
Write-Host "T06_A1_REGISTRATION_SHA256=$ActualRegistrationSha"
Write-Host "T06_A1_ARCHITECTURE_SHA256=$ActualArchitectureSha"
Write-Host "T06_A1_ARCHITECTURE_PATH=$Architecture"
Write-Host "T06_A1_T01_HELPER_SHA256=$ActualT01Sha"

if ($ActualGateSha -ne $ExpectedGateSha) {
    throw "T06_A1_GATE_SHA256_MISMATCH"
}
if ($ActualRegistrationSha -ne $ExpectedRegistrationSha) {
    throw "T06_A1_REGISTRATION_SHA256_MISMATCH"
}
if ($ActualArchitectureSha -ne $ExpectedArchitectureSha) {
    throw "T06_A1_ARCHITECTURE_SHA256_MISMATCH"
}
if ($ActualT01Sha -ne $ExpectedT01Sha) {
    throw "T06_A1_T01_HELPER_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne '8a39459be3ce7ed40e325736034245f0025cf249') {
    throw "T06_A1_CANDIDATE_COMMIT_MISMATCH"
}
if ($Tree -ne 'e2521f27c9f91978e381bce202ab3e3c83aa6dad') {
    throw "T06_A1_CANDIDATE_TREE_MISMATCH"
}
if ($Status) {
    throw "T06_A1_CANDIDATE_WORKTREE_NOT_CLEAN"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t06\official-run-$Stamp-T06-A1-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t06-a1-pyc'

try {
    & $Python $Gate `
        --repo $Repo `
        --foundation-control-db $FoundationDb `
        --implementation-identity-registration $Registration `
        --architecture-contract $Architecture `
        --output-dir $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T06_PROCESS_EXIT_CODE=$Rc"
Write-Host "T06_OUTPUT_ROOT=$OutputDir"

if ($Rc -ne 0) {
    throw "T06_A1_FORMAL_FAILED exit_code=$Rc"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputDir -Directory)
$RunCount = ($RunDirs | Measure-Object).Count
if ($RunCount -ne 1) {
    throw "T06_A1_RUN_DIRECTORY_COUNT_NOT_ONE count=$RunCount"
}

$RunDir = $RunDirs[0].FullName
$ManifestPath = Join-Path $RunDir 't06-manifest.json'
$ResultPath = Join-Path $RunDir 't06-gate-result-manifest.json'
$BuildIdentityPath = Join-Path $RunDir 't06-build-identity.json'
$InventoryPath = Join-Path $RunDir 't06-implementation-inventory.json'
$SummaryPath = Join-Path $RunDir 't06-summary.txt'

foreach ($Path in @($ManifestPath,$ResultPath,$BuildIdentityPath,$InventoryPath,$SummaryPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T06_A1_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$BuildIdentity = Get-Content -LiteralPath $BuildIdentityPath -Raw | ConvertFrom-Json
$Inventory = Get-Content -LiteralPath $InventoryPath -Raw | ConvertFrom-Json

if ($Manifest.artifact_type -ne 'ClassifierArtifactManifest') {
    throw "T06_A1_MANIFEST_TYPE_MISMATCH"
}
if ($Manifest.semantic_payload.repository_commit_sha -ne $Commit) {
    throw "T06_A1_MANIFEST_COMMIT_MISMATCH"
}
if ($Manifest.semantic_payload.repository_tree_sha -ne $Tree) {
    throw "T06_A1_MANIFEST_TREE_MISMATCH"
}
if ($Manifest.semantic_payload.classification_engine_semver -ne '1.0.0') {
    throw "T06_A1_ENGINE_VERSION_MISMATCH"
}
if ($Manifest.semantic_payload.artifact_canonical_json_version -ne 'ArtifactCanonicalJsonV1') {
    throw "T06_A1_ARTIFACT_CANONICAL_VERSION_MISMATCH"
}

$Adapters = @($Manifest.semantic_payload.adapter_implementation_identities)
$AdapterCount = ($Adapters | Measure-Object).Count
Write-Host "T06_ADAPTER_IMPLEMENTATION_COUNT=$AdapterCount"

if ($AdapterCount -ne 8) {
    throw "T06_A1_ADAPTER_IMPLEMENTATION_COUNT_MISMATCH count=$AdapterCount"
}

if ($Result.semantic_payload.gate_id -ne 'T-06') {
    throw "T06_A1_GATE_ID_MISMATCH"
}
if ($Result.semantic_payload.gate_contract_version -ne 'R14-T-06-v1') {
    throw "T06_A1_GATE_CONTRACT_MISMATCH"
}
if ($Result.semantic_payload.status -ne 'PASS') {
    throw "T06_A1_GATE_RESULT_NOT_PASS"
}
if ($Result.semantic_payload.candidate_repository_commit_sha -ne $Commit) {
    throw "T06_A1_GATE_COMMIT_MISMATCH"
}
if ($Result.semantic_payload.candidate_repository_tree_sha -ne $Tree) {
    throw "T06_A1_GATE_TREE_MISMATCH"
}
if ((@($Result.semantic_payload.decision_record_refs) | Measure-Object).Count -ne 0) {
    throw "T06_A1_UNEXPECTED_DECISION_RECORD_REFS"
}

$Outputs = @($Result.semantic_payload.output_artifact_refs)
if (($Outputs | Measure-Object).Count -ne 1) {
    throw "T06_A1_OUTPUT_REF_COUNT_NOT_ONE"
}
if ($Outputs[0].artifact_id -ne $Manifest.artifact_id) {
    throw "T06_A1_OUTPUT_MANIFEST_ID_MISMATCH"
}
if ($Outputs[0].content_sha256 -ne $Manifest.content_sha256) {
    throw "T06_A1_OUTPUT_MANIFEST_DIGEST_MISMATCH"
}

if ($BuildIdentity.identity_registration_sha256 -ne $ExpectedRegistrationSha) {
    throw "T06_A1_BUILD_IDENTITY_REGISTRATION_SHA_MISMATCH"
}
if ($BuildIdentity.architecture_document_sha256 -ne $ExpectedArchitectureSha) {
    throw "T06_A1_BUILD_IDENTITY_ARCHITECTURE_SHA_MISMATCH"
}

$InventoryEntries = @($Inventory.entries)
$InventoryCount = ($InventoryEntries | Measure-Object).Count
if ($InventoryCount -ne 8) {
    throw "T06_A1_IMPLEMENTATION_INVENTORY_COUNT_MISMATCH count=$InventoryCount"
}

$ManifestSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ManifestPath).Hash.ToLowerInvariant()
$ResultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResultPath).Hash.ToLowerInvariant()
$BuildIdentitySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $BuildIdentityPath).Hash.ToLowerInvariant()
$InventorySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $InventoryPath).Hash.ToLowerInvariant()
$SummarySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SummaryPath).Hash.ToLowerInvariant()

$CommitAfter = (& git -C $Repo rev-parse HEAD).Trim()
$TreeAfter = (& git -C $Repo show -s --format=%T HEAD).Trim()
$StatusAfter = & git -C $Repo status --porcelain

if ($CommitAfter -ne $Commit -or $TreeAfter -ne $Tree -or $StatusAfter) {
    throw "T06_A1_CANDIDATE_CHANGED_OR_DIRTY_AFTER_GATE"
}

Write-Host ""
Write-Host "T06_A1_LAUNCHER_STATUS=PASS"
Write-Host "T06_FORMAL_GATE_EXECUTED=YES"
Write-Host "T06_FORMAL_STATUS=PASS"
Write-Host "CLASSIFIER_ARTIFACT_MANIFEST_ID=$($Manifest.artifact_id)"
Write-Host "CLASSIFIER_ARTIFACT_MANIFEST_CONTENT_SHA256=$($Manifest.content_sha256)"
Write-Host "CLASSIFIER_ARTIFACT_MANIFEST_FILE_SHA256=$ManifestSha"
Write-Host "T06_GATE_RESULT_ID=$($Result.artifact_id)"
Write-Host "T06_GATE_RESULT_CONTENT_SHA256=$($Result.content_sha256)"
Write-Host "T06_GATE_RESULT_FILE_SHA256=$ResultSha"
Write-Host "T06_BUILD_IDENTITY_SHA256=$BuildIdentitySha"
Write-Host "T06_IMPLEMENTATION_INVENTORY_SHA256=$InventorySha"
Write-Host "T06_SUMMARY_SHA256=$SummarySha"
Write-Host "T06_RUN_DIRECTORY=$RunDir"
Write-Host "OWNER_DECISION_REQUIRED=NO"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-06A"
