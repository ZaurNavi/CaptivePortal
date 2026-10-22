$ErrorActionPreference = 'Stop'

$Gate = 'C:\CaptivPortal-Lab\tools\task04-t07-gate-a1-20261002.py'
$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'
$FoundationDb = 'C:\CaptivPortal-Lab\foundation-control-plane\device-fingerprint-control-plane.sqlite3'
$T06ARunDir = 'C:\CaptivPortal-Lab\official-runs\task04\t06a\official-run-20261001T124442Z-T06A-A1-01\fe25e9fc-7b03-485b-ae68-0f806fd96af6'

$ExpectedGateSha = 'bbe90933dd4526f4b0cb3c1db65ada38161de0147c476a5be2105bcb7cecf9ac'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'
$ExpectedProfileId = 'ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c'
$ExpectedT06AResultId = 'GateResultManifest:v1:sha256:cd102f0fca7adb9e09ce1ff69d2109b34691e7362fd071a0617fc300547db406'
$ExpectedT06AProofId = 'GateProofArtifact:v1:sha256:6e404961cce296382f03b37e54111b6d535a1e1c44432a8e8f6269290bf64267'
$ExpectedTask01Sha = '79cfcfb8c463c235af1d7dfe4f49a8e9ef491a25749ccbeeded85b88f2ee90f9'

foreach ($Path in @($Gate,$Python,$Repo,$FoundationDb,$T06ARunDir)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T07_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualGateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
Write-Host "T07_A1_GATE_SHA256=$ActualGateSha"

if ($ActualGateSha -ne $ExpectedGateSha) {
    throw "T07_A1_GATE_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"

if ($Commit -ne $ExpectedCommit) {
    throw "T07_A1_CANDIDATE_COMMIT_MISMATCH"
}
if ($Tree -ne $ExpectedTree) {
    throw "T07_A1_CANDIDATE_TREE_MISMATCH"
}
if ($Status) {
    throw "T07_A1_CANDIDATE_WORKTREE_NOT_CLEAN"
}

# Resolve the exact accepted Task-01 fixture by immutable byte identity.
# Historical T-08 pins this same database SHA; any byte-identical retained copy
# is semantically the same read-only input.
$DbCandidates = @()
$DbCandidates += @(Get-ChildItem -LiteralPath 'C:\CaptivPortal-Lab' -Recurse -File -Filter '*.sqlite3' -ErrorAction SilentlyContinue)
$DbCandidates += @(Get-ChildItem -LiteralPath 'C:\CaptivPortal-Lab' -Recurse -File -Filter '*.db' -ErrorAction SilentlyContinue)
$DbCandidates = @($DbCandidates | Sort-Object FullName -Unique)

$Task01Matches = @()
foreach ($File in $DbCandidates) {
    try {
        $Digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $File.FullName -ErrorAction Stop).Hash.ToLowerInvariant()
    }
    catch {
        continue
    }
    if ($Digest -eq $ExpectedTask01Sha) {
        $Task01Matches += $File.FullName
    }
}

Write-Host "T07_TASK01_EXACT_MATCH_COUNT=$(($Task01Matches | Measure-Object).Count)"
foreach ($Match in $Task01Matches) {
    Write-Host "T07_TASK01_EXACT_MATCH=$Match"
}

if (($Task01Matches | Measure-Object).Count -lt 1) {
    throw "T07_ACCEPTED_TASK01_DB_NOT_FOUND_BY_SHA256"
}

# Deterministic selection: prefer a retained source outside transient run/tmp trees.
$Preferred = @($Task01Matches | Where-Object {
    $_ -notmatch '\\official-runs\\' -and
    $_ -notmatch '\\tmp\\' -and
    $_ -notmatch '\\pytest-' -and
    $_ -notmatch '\\task01-disposable\.sqlite3$'
} | Sort-Object)

if (($Preferred | Measure-Object).Count -gt 0) {
    $Task01Db = $Preferred[0]
}
else {
    $Task01Db = (@($Task01Matches | Sort-Object))[0]
}

$Task01Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Task01Db).Hash.ToLowerInvariant()
Write-Host "T07_TASK01_DB=$Task01Db"
Write-Host "T07_TASK01_DB_SHA256=$Task01Sha"

if ($Task01Sha -ne $ExpectedTask01Sha) {
    throw "T07_TASK01_DB_SHA256_MISMATCH"
}

$T06AProfilePath = Join-Path $T06ARunDir 't06a-classification-runtime-profile.json'
$T06AProofPath = Join-Path $T06ARunDir 't06a-gate-proof-artifact.json'
$T06AResultPath = Join-Path $T06ARunDir 't06a-gate-result-manifest.json'

foreach ($Path in @($T06AProfilePath,$T06AProofPath,$T06AResultPath)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T07_T06A_PREREQUISITE_MISSING: $Path"
    }
}

$T06AProfile = Get-Content -LiteralPath $T06AProfilePath -Raw | ConvertFrom-Json
$T06AProof = Get-Content -LiteralPath $T06AProofPath -Raw | ConvertFrom-Json
$T06AResult = Get-Content -LiteralPath $T06AResultPath -Raw | ConvertFrom-Json

if ($T06AProfile.artifact_id -ne $ExpectedProfileId) {
    throw "T07_PROFILE_ID_MISMATCH"
}
if ($T06AProof.artifact_id -ne $ExpectedT06AProofId) {
    throw "T07_T06A_PROOF_ID_MISMATCH"
}
if ($T06AResult.artifact_id -ne $ExpectedT06AResultId -or
    $T06AResult.semantic_payload.status -ne 'PASS') {
    throw "T07_T06A_RESULT_MISMATCH"
}

$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$OutputDir = "C:\CaptivPortal-Lab\official-runs\task04\t07\official-run-$Stamp-T07-A1-01"

$env:PYTHONPYCACHEPREFIX = 'C:\CaptivPortal-Lab\tmp\task04-t07-a1-pyc'

try {
    & $Python $Gate `
        --repo $Repo `
        --foundation-control-db $FoundationDb `
        --task01-db $Task01Db `
        --t06a-run-dir $T06ARunDir `
        --output-dir $OutputDir
    $Rc = $LASTEXITCODE
}
finally {
    Remove-Item Env:PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
}

Write-Host "T07_PROCESS_EXIT_CODE=$Rc"
Write-Host "T07_OUTPUT_ROOT=$OutputDir"

if ($Rc -ne 0) {
    throw "T07_A1_FORMAL_FAILED exit_code=$Rc"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputDir -Directory)
$RunCount = ($RunDirs | Measure-Object).Count
if ($RunCount -ne 1) {
    throw "T07_A1_RUN_DIRECTORY_COUNT_NOT_ONE count=$RunCount"
}

$RunDir = $RunDirs[0].FullName
$ResultPath = Join-Path $RunDir 't07-gate-result-manifest.json'
$ProofPath = Join-Path $RunDir 't07-gate-proof-artifact.json'
$EvidencePath = Join-Path $RunDir 't07-execution-evidence.json'
$CorePath = Join-Path $RunDir 't07-persistence-core.json'
$InventoryPath = Join-Path $RunDir 't07-classification-db-inventory.json'
$ReplayPath = Join-Path $RunDir 't07-audit-replay-report.json'
$GcPath = Join-Path $RunDir 't07-gc-report.json'
$GuardPath = Join-Path $RunDir 't07-production-admission-guard.json'
$PytestPath = Join-Path $RunDir 't07-pytest.log'
$SummaryPath = Join-Path $RunDir 't07-summary.txt'

foreach ($Path in @(
    $ResultPath,$ProofPath,$EvidencePath,$CorePath,$InventoryPath,
    $ReplayPath,$GcPath,$GuardPath,$PytestPath,$SummaryPath
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T07_A1_EXPECTED_OUTPUT_MISSING: $Path"
    }
}

$Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$Proof = Get-Content -LiteralPath $ProofPath -Raw | ConvertFrom-Json
$Evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json
$Inventory = Get-Content -LiteralPath $InventoryPath -Raw | ConvertFrom-Json
$Replay = Get-Content -LiteralPath $ReplayPath -Raw | ConvertFrom-Json
$Gc = Get-Content -LiteralPath $GcPath -Raw | ConvertFrom-Json
$Guard = Get-Content -LiteralPath $GuardPath -Raw | ConvertFrom-Json

$CaseProps = @($Evidence.direct_matrix.PSObject.Properties)
$CaseCount = ($CaseProps | Measure-Object).Count
Write-Host "T07_CASE_COUNT=$CaseCount"

if ($CaseCount -ne 12) {
    throw "T07_A1_CASE_COUNT_NOT_12 count=$CaseCount"
}
foreach ($Case in $CaseProps) {
    if ($Case.Value.status -ne 'PASS') {
        throw "T07_A1_CASE_FAILURE: $($Case.Name)"
    }
}
if ($Evidence.all_pass -ne $true) {
    throw "T07_A1_MATRIX_NOT_PASS"
}
if ([int]$Evidence.pytest_exit_status -ne 0) {
    throw "T07_A1_PYTEST_NOT_PASS"
}
if ($Evidence.exact_profile.artifact_id -ne $ExpectedProfileId) {
    throw "T07_A1_EVIDENCE_PROFILE_MISMATCH"
}
if ($Evidence.t06a_gate_result.artifact_id -ne $ExpectedT06AResultId) {
    throw "T07_A1_EVIDENCE_T06A_RESULT_MISMATCH"
}
if ($Evidence.t06a_gate_proof.artifact_id -ne $ExpectedT06AProofId) {
    throw "T07_A1_EVIDENCE_T06A_PROOF_MISMATCH"
}
if ([int]$Evidence.a1_immutable_overlay_artifact_count -ne 17) {
    throw "T07_A1_OVERLAY_COUNT_NOT_17 count=$($Evidence.a1_immutable_overlay_artifact_count)"
}

if ($Inventory.accepted_task01_db_sha256_before -ne $ExpectedTask01Sha -or
    $Inventory.accepted_task01_db_sha256_after -ne $ExpectedTask01Sha) {
    throw "T07_A1_TASK01_BYTE_IDENTITY_MISMATCH"
}
if ([int]$Inventory.dangling_ref_scan_result.dangling_count -ne 0) {
    throw "T07_A1_DANGLING_REF_PRESENT"
}

if ($Replay.replay_exact -ne $true -or [int]$Replay.wall_clock_read_count -ne 0) {
    throw "T07_A1_LEVEL_B_REPLAY_MISMATCH"
}
if ([int]$Gc.dangling_edges_after_gc -ne 0) {
    throw "T07_A1_GC_DANGLING_EDGE"
}

if ($Guard.unadmitted_exact_p.classification_committed -ne $false -or
    $Guard.unadmitted_exact_p.reason_code -ne 'production_profile_not_admitted') {
    throw "T07_A1_PRODUCTION_ADMISSION_GUARD_MISMATCH"
}
if ($Guard.production_activation -ne $false) {
    throw "T07_A1_UNEXPECTED_PRODUCTION_ACTIVATION"
}

if ($Proof.semantic_payload.proof_kind -ne 'CLASSIFICATION_AUDIT_PERSISTENCE' -or
    $Proof.semantic_payload.source_gate_id -ne 'T-07') {
    throw "T07_A1_PROOF_CONTRACT_MISMATCH"
}
if ($Proof.semantic_payload.candidate_repository_commit_sha -ne $ExpectedCommit -or
    $Proof.semantic_payload.candidate_repository_tree_sha -ne $ExpectedTree) {
    throw "T07_A1_PROOF_CANDIDATE_MISMATCH"
}

if ($Result.semantic_payload.gate_id -ne 'T-07' -or
    $Result.semantic_payload.gate_contract_version -ne 'R14-T-07-v1' -or
    $Result.semantic_payload.status -ne 'PASS') {
    throw "T07_A1_GATE_RESULT_CONTRACT_MISMATCH"
}
if ((@($Result.semantic_payload.decision_record_refs) | Measure-Object).Count -ne 0) {
    throw "T07_A1_UNEXPECTED_DECISION_RECORD_REFS"
}

$InputIds = @($Result.semantic_payload.input_artifact_refs | ForEach-Object { $_.artifact_id })
if (($InputIds | Measure-Object).Count -ne 4 -or
    $InputIds -notcontains $ExpectedProfileId -or
    $InputIds -notcontains $ExpectedT06AResultId) {
    throw "T07_A1_FORMAL_INPUT_SET_MISMATCH"
}

$ResultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ResultPath).Hash.ToLowerInvariant()
$ProofSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ProofPath).Hash.ToLowerInvariant()
$EvidenceSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $EvidencePath).Hash.ToLowerInvariant()
$CoreSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $CorePath).Hash.ToLowerInvariant()
$InventorySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $InventoryPath).Hash.ToLowerInvariant()
$ReplaySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ReplayPath).Hash.ToLowerInvariant()
$GcSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $GcPath).Hash.ToLowerInvariant()
$GuardSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $GuardPath).Hash.ToLowerInvariant()
$PytestSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $PytestPath).Hash.ToLowerInvariant()
$SummarySha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SummaryPath).Hash.ToLowerInvariant()

$CommitAfter = (& git -C $Repo rev-parse HEAD).Trim()
$TreeAfter = (& git -C $Repo show -s --format=%T HEAD).Trim()
$StatusAfter = & git -C $Repo status --porcelain
if ($CommitAfter -ne $ExpectedCommit -or $TreeAfter -ne $ExpectedTree -or $StatusAfter) {
    throw "T07_A1_CANDIDATE_CHANGED_OR_DIRTY_AFTER_GATE"
}

Write-Host ""
Write-Host "T07_A1_LAUNCHER_STATUS=PASS"
Write-Host "T07_FORMAL_GATE_EXECUTED=YES"
Write-Host "T07_FORMAL_STATUS=PASS"
Write-Host "T07_CASES_PASS=12/12"
Write-Host "T07_LEVEL_B_REPLAY_EXACT=YES"
Write-Host "T07_REPLAY_WALL_CLOCK_READS=0"
Write-Host "T07_GC_DANGLING_EDGES=0"
Write-Host "T07_PRODUCTION_PROFILE_ADMITTED=NO"
Write-Host "T07_PRODUCTION_ACTIVATION=NO"
Write-Host "T07_A1_OVERLAY_ARTIFACT_COUNT=$($Evidence.a1_immutable_overlay_artifact_count)"
Write-Host "T07_GATE_PROOF_ID=$($Proof.artifact_id)"
Write-Host "T07_GATE_PROOF_CONTENT_SHA256=$($Proof.content_sha256)"
Write-Host "T07_GATE_PROOF_FILE_SHA256=$ProofSha"
Write-Host "T07_GATE_RESULT_ID=$($Result.artifact_id)"
Write-Host "T07_GATE_RESULT_CONTENT_SHA256=$($Result.content_sha256)"
Write-Host "T07_GATE_RESULT_FILE_SHA256=$ResultSha"
Write-Host "T07_EXECUTION_EVIDENCE_SHA256=$EvidenceSha"
Write-Host "T07_PERSISTENCE_CORE_SHA256=$CoreSha"
Write-Host "T07_DB_INVENTORY_SHA256=$InventorySha"
Write-Host "T07_AUDIT_REPLAY_SHA256=$ReplaySha"
Write-Host "T07_GC_REPORT_SHA256=$GcSha"
Write-Host "T07_PRODUCTION_GUARD_SHA256=$GuardSha"
Write-Host "T07_PYTEST_LOG_SHA256=$PytestSha"
Write-Host "T07_SUMMARY_SHA256=$SummarySha"
Write-Host "T07_RUN_DIRECTORY=$RunDir"
Write-Host "OWNER_DECISION_REQUIRED=NO"
Write-Host "PRODUCTION_ACTION=NO"
Write-Host "NEXT=T-08"
