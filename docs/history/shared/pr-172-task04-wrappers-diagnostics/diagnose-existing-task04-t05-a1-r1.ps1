$ErrorActionPreference = 'Stop'

$OutputRoot = 'C:\CaptivPortal-Lab\official-runs\task04\t05\official-run-20261001T125331Z-T05-A1-01'

if (-not (Test-Path -LiteralPath $OutputRoot)) {
    throw "T05_DIAG_OUTPUT_ROOT_MISSING: $OutputRoot"
}

$RunDirs = @(Get-ChildItem -LiteralPath $OutputRoot -Directory)
$RunCount = ($RunDirs | Measure-Object).Count

Write-Host "T05_DIAG_RUN_DIRECTORY_COUNT=$RunCount"

if ($RunCount -ne 1) {
    throw "T05_DIAG_RUN_DIRECTORY_COUNT_NOT_ONE count=$RunCount"
}

$RunDir = $RunDirs[0].FullName
Write-Host "T05_DIAG_RUN_DIRECTORY=$RunDir"

$SummaryPath = Join-Path $RunDir 't05-summary.txt'
$MatrixPath = Join-Path $RunDir 't05-direct-matrix.json'
$EvidencePath = Join-Path $RunDir 't05-execution-evidence.json'
$PytestPath = Join-Path $RunDir 't05-pytest.log'
$ResultPath = Join-Path $RunDir 't05-gate-result-manifest.json'
$ProofPath = Join-Path $RunDir 't05-gate-proof-artifact.json'
$PointerPath = Join-Path $RunDir 't05-pointer-switch-trace.json'
$IoPath = Join-Path $RunDir 't05-pure-core-io-proof.json'
$FreshnessPath = Join-Path $RunDir 't05-freshness-report.json'

foreach ($Path in @(
    $SummaryPath,$MatrixPath,$EvidencePath,$PytestPath,$ResultPath,
    $PointerPath,$IoPath,$FreshnessPath
)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Host "T05_DIAG_MISSING=$Path"
    }
}

if (Test-Path -LiteralPath $SummaryPath) {
    Write-Host ""
    Write-Host "=== T05 SUMMARY ==="
    Get-Content -LiteralPath $SummaryPath
}

$Matrix = $null
if (Test-Path -LiteralPath $MatrixPath) {
    $Matrix = Get-Content -LiteralPath $MatrixPath -Raw | ConvertFrom-Json

    Write-Host ""
    Write-Host "=== T05 DIRECT MATRIX ==="
    Write-Host "T05_MATRIX_ALL_PASS=$($Matrix.all_pass)"
    Write-Host "T05_MATRIX_FAILURE_CODE=$($Matrix.failure_code)"
    Write-Host "T05_MATRIX_FAILURE_DETAIL=$($Matrix.failure_detail)"

    $CaseProperties = @($Matrix.cases.PSObject.Properties)
    Write-Host "T05_MATRIX_CASE_COUNT=$(($CaseProperties | Measure-Object).Count)"
    foreach ($Case in $CaseProperties) {
        Write-Host "T05_CASE=$($Case.Name)|STATUS=$($Case.Value.status)"
    }
}

if (Test-Path -LiteralPath $EvidencePath) {
    $Evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json

    Write-Host ""
    Write-Host "=== T05 EXECUTION EVIDENCE ==="
    Write-Host "T05_EVIDENCE_FAILURE_CODE=$($Evidence.failure_code)"
    Write-Host "T05_PYTEST_EXIT_STATUS=$($Evidence.pytest_exit_status)"
    Write-Host "T05_EXACT_PROFILE_ID=$($Evidence.exact_profile.artifact_id)"
    Write-Host "T05_T06A_RESULT_ID=$($Evidence.t06a_gate_result.artifact_id)"
    Write-Host "T05_T06A_PROOF_ID=$($Evidence.t06a_gate_proof.artifact_id)"
    Write-Host "T05_A1_OVERLAY_ARTIFACT_COUNT=$($Evidence.a1_immutable_overlay_artifact_count)"

    if ($Evidence.matrix_statuses) {
        foreach ($P in @($Evidence.matrix_statuses.PSObject.Properties)) {
            Write-Host "T05_EVIDENCE_CASE=$($P.Name)|STATUS=$($P.Value)"
        }
    }
}

if (Test-Path -LiteralPath $ResultPath) {
    $Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json

    Write-Host ""
    Write-Host "=== T05 FORMAL RESULT ==="
    Write-Host "T05_GATE_RESULT_ID=$($Result.artifact_id)"
    Write-Host "T05_GATE_RESULT_STATUS=$($Result.semantic_payload.status)"
    Write-Host "T05_GATE_RESULT_CONTRACT=$($Result.semantic_payload.gate_contract_version)"
    Write-Host "T05_GATE_RESULT_OUTPUT_COUNT=$((@($Result.semantic_payload.output_artifact_refs) | Measure-Object).Count)"
    Write-Host "T05_GATE_RESULT_DECISION_REF_COUNT=$((@($Result.semantic_payload.decision_record_refs) | Measure-Object).Count)"
}

Write-Host ""
Write-Host "T05_PROOF_EXISTS=$(Test-Path -LiteralPath $ProofPath)"

if (Test-Path -LiteralPath $PointerPath) {
    $Pointer = Get-Content -LiteralPath $PointerPath -Raw | ConvertFrom-Json
    Write-Host "T05_POINTER_TRACE_PROPERTY_COUNT=$((@($Pointer.PSObject.Properties) | Measure-Object).Count)"
}

if (Test-Path -LiteralPath $IoPath) {
    $Io = Get-Content -LiteralPath $IoPath -Raw | ConvertFrom-Json
    if ($null -ne $Io.attempt_count) {
        Write-Host "T05_PURE_CORE_IO_ATTEMPT_COUNT=$($Io.attempt_count)"
    }
}

if (Test-Path -LiteralPath $FreshnessPath) {
    $Freshness = Get-Content -LiteralPath $FreshnessPath -Raw | ConvertFrom-Json
    Write-Host "T05_FRESHNESS_PROPERTY_COUNT=$((@($Freshness.PSObject.Properties) | Measure-Object).Count)"
}

if (Test-Path -LiteralPath $PytestPath) {
    Write-Host ""
    Write-Host "=== T05 PYTEST TAIL ==="
    Get-Content -LiteralPath $PytestPath -Tail 80
}

Write-Host ""
Write-Host "=== T05 FILE SHA256 ==="
foreach ($Path in @(
    $SummaryPath,$MatrixPath,$EvidencePath,$PytestPath,$ResultPath,
    $PointerPath,$IoPath,$FreshnessPath
)) {
    if (Test-Path -LiteralPath $Path) {
        $Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
        Write-Host "$([IO.Path]::GetFileName($Path))=$Sha"
    }
}

Write-Host ""
Write-Host "T05_DIAGNOSTIC_STATUS=PASS"
Write-Host "T05_FORMAL_GATE_RERUN=NO"
Write-Host "PRODUCTION_ACTION=NO"
