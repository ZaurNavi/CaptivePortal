$ErrorActionPreference = 'Stop'

$OutputRoot = 'C:\CaptivPortal-Lab\official-runs\task04\t09\phase-b-20261002T074414Z-T09-A1-R2-01'
$Gate = 'C:\CaptivPortal-Lab\tools\task04-t09-phase-b-a1-r2-20261002.py'
$Repo = 'C:\CaptivPortal-Lab\coder-task04-t09-utility-repair-a1'

$ExpectedGateSha = 'fceb54dc653978f8aaaa9720ab9441c844748c971ff40e5920046563da1df1c8'
$ExpectedCommit = '8a39459be3ce7ed40e325736034245f0025cf249'
$ExpectedTree = 'e2521f27c9f91978e381bce202ab3e3c83aa6dad'

foreach ($Path in @($OutputRoot,$Gate,$Repo)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_WORKER_DIAG_REQUIRED_PATH_MISSING: $Path"
    }
}

$GateSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Gate).Hash.ToLowerInvariant()
Write-Host "T09_WORKER_DIAG_GATE_SHA256=$GateSha"
if ($GateSha -ne $ExpectedGateSha) {
    throw "T09_WORKER_DIAG_GATE_SHA256_MISMATCH"
}

$Commit = (& git -C $Repo rev-parse HEAD).Trim()
$Tree = (& git -C $Repo show -s --format=%T HEAD).Trim()
$Status = & git -C $Repo status --porcelain

Write-Host "CANDIDATE_COMMIT=$Commit"
Write-Host "CANDIDATE_TREE=$Tree"
Write-Host "CANDIDATE_WORKTREE_CLEAN=$(if ($Status) {'NO'} else {'YES'})"

if ($Commit -ne $ExpectedCommit -or $Tree -ne $ExpectedTree -or $Status) {
    throw "T09_WORKER_DIAG_CANDIDATE_IDENTITY_FAILURE"
}

$StdoutPath = Join-Path $OutputRoot 'worker-1-stdout.log'
$StderrPath = Join-Path $OutputRoot 'worker-1-stderr.log'
$WorkerDir = Join-Path $OutputRoot 'worker-1'

Write-Host ""
Write-Host "=== WORKER-1 PARENT LOG FILES ==="

foreach ($Path in @($StdoutPath,$StderrPath)) {
    if (Test-Path -LiteralPath $Path) {
        $Info = Get-Item -LiteralPath $Path
        $Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
        Write-Host "$($Info.Name)|BYTES=$($Info.Length)|SHA256=$Sha"
    }
    else {
        Write-Host "MISSING=$Path"
    }
}

if (Test-Path -LiteralPath $StdoutPath) {
    Write-Host ""
    Write-Host "=== WORKER-1 STDOUT ==="
    Get-Content -LiteralPath $StdoutPath
}

if (Test-Path -LiteralPath $StderrPath) {
    Write-Host ""
    Write-Host "=== WORKER-1 STDERR ==="
    Get-Content -LiteralPath $StderrPath
}

Write-Host ""
Write-Host "=== WORKER-1 DIRECTORY INVENTORY ==="

if (Test-Path -LiteralPath $WorkerDir) {
    $Files = @(Get-ChildItem -LiteralPath $WorkerDir -Recurse -File | Sort-Object FullName)
    Write-Host "WORKER_1_FILE_COUNT=$(($Files | Measure-Object).Count)"
    foreach ($File in $Files) {
        $Rel = $File.FullName.Substring($WorkerDir.Length).TrimStart('\')
        $Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $File.FullName).Hash.ToLowerInvariant()
        Write-Host "WORKER_1_FILE=$Rel|BYTES=$($File.Length)|SHA256=$Sha"
    }
}
else {
    Write-Host "WORKER_1_DIRECTORY_EXISTS=NO"
}

$RequestPath = Join-Path $WorkerDir 'request-1.json'
$ResultPath = Join-Path $WorkerDir 'result-1.json'
$ComparisonPath = Join-Path $WorkerDir 'comparison-1.json'
$CompletionPath = Join-Path $WorkerDir 'worker-completion.json'
$ClassificationDbPath = Join-Path $WorkerDir 'classification.sqlite3'
$CompatibilityPath = Join-Path $WorkerDir 'compatibility-report.json'

Write-Host ""
Write-Host "=== WORKER-1 STAGE MARKERS ==="
Write-Host "WORKER_1_REQUEST_EXISTS=$(Test-Path -LiteralPath $RequestPath)"
Write-Host "WORKER_1_RESULT_EXISTS=$(Test-Path -LiteralPath $ResultPath)"
Write-Host "WORKER_1_COMPARISON_EXISTS=$(Test-Path -LiteralPath $ComparisonPath)"
Write-Host "WORKER_1_COMPLETION_EXISTS=$(Test-Path -LiteralPath $CompletionPath)"
Write-Host "WORKER_1_CLASSIFICATION_DB_EXISTS=$(Test-Path -LiteralPath $ClassificationDbPath)"
Write-Host "WORKER_1_COMPATIBILITY_REPORT_EXISTS=$(Test-Path -LiteralPath $CompatibilityPath)"

if (Test-Path -LiteralPath $RequestPath) {
    $Request = Get-Content -LiteralPath $RequestPath -Raw | ConvertFrom-Json
    Write-Host "WORKER_1_REQUEST_ID=$($Request.artifact_id)"
}
if (Test-Path -LiteralPath $ResultPath) {
    $Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
    Write-Host "WORKER_1_RESULT_ID=$($Result.artifact_id)"
    Write-Host "WORKER_1_RESULT_GLOBAL_STATUS=$($Result.semantic_payload.global_classification_status)"
    Write-Host "WORKER_1_PLATFORM=$($Result.semantic_payload.platform_result.status)|$($Result.semantic_payload.platform_result.canonical_value_id)|$($Result.semantic_payload.platform_result.support_level)"
    Write-Host "WORKER_1_DEVICE_CLASS=$($Result.semantic_payload.device_class_result.status)|$($Result.semantic_payload.device_class_result.canonical_value_id)|$($Result.semantic_payload.device_class_result.support_level)"
}
if (Test-Path -LiteralPath $ComparisonPath) {
    $Cmp = Get-Content -LiteralPath $ComparisonPath -Raw | ConvertFrom-Json
    Write-Host "WORKER_1_COMPARISON_ID=$($Cmp.artifact_id)"
    Write-Host "WORKER_1_COMPARISON_OUTCOME=$($Cmp.semantic_payload.overall_validation_outcome)"
}

Write-Host ""
Write-Host "T09_WORKER_DIAGNOSTIC_STATUS=PASS"
Write-Host "T09_PHASE_B_RERUN=NO"
Write-Host "PRODUCTION_ACTION=NO"
