$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Lab = "C:\CaptivPortal-Lab"
$ControlDb = Join-Path $Lab "foundation-control-plane\device-fingerprint-control-plane.sqlite3"
$RunDir = Join-Path $Lab "official-runs\task04\taccept\official-run-20261003T072401Z-TACCEPT-A1-R6-01"
$Lock = Join-Path $RunDir "taccept-lock.json"
$ExpectedLockSha = "cf23d5f1b52581bab096e13c9c12e18722feca3297ab79f1f6955a90d4e39d12"

$ExpectedCrpId = "ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
$ExpectedAcceptanceId = "Task04AcceptanceManifest:v1:sha256:ca2712fbd643b332594990e67dc95ec017507d2d4d51d61f549d357bad18ca54"
$ExpectedClassificationRpmId = "RuntimeProfileAdmissionManifest:v1:sha256:7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
$ExpectedFoundationProfileId = "FoundationRuntimeProfile:v1:sha256:9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
$ExpectedFoundationRpmId = "RuntimeProfileAdmissionManifest:v1:sha256:95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
$ExpectedFoundationAdmissionId = "FoundationAdmissionManifest:v1:sha256:44f2b26b297c7c126a7b224b8db8f88873893a0cc6819e4e18f6106af00de4ff"

$Python = "C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

if (-not (Test-Path -LiteralPath $ControlDb)) { throw "CONTROL_DB_MISSING: $ControlDb" }
if (-not (Test-Path -LiteralPath $Lock)) { throw "TACCEPT_LOCK_MISSING: $Lock" }

$LockSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Lock).Hash.ToLowerInvariant()
if ($LockSha -ne $ExpectedLockSha) {
    throw "TACCEPT_LOCK_SHA_MISMATCH actual=$LockSha expected=$ExpectedLockSha"
}

$LockObj = Get-Content -Raw -LiteralPath $Lock | ConvertFrom-Json

function Require-Equal([string]$Name, $Actual, $Expected) {
    if ($Actual -ne $Expected) {
        throw "$Name mismatch. actual=$Actual expected=$Expected"
    }
}

Require-Equal "LOCK_STATUS" $LockObj.status "PASS"
Require-Equal "LOCK_UPDATE_CLASS" $LockObj.update_class "INITIAL_CLASSIFICATION"
Require-Equal "LOCK_PRODUCTION_ACTIVATION" ([bool]$LockObj.production_activation) $false
if ($null -ne $LockObj.classification_active_pointer_after) {
    throw "LOCK_CLASSIFICATION_POINTER_NOT_NULL"
}
Require-Equal "LOCK_CRP" $LockObj.classification_runtime_profile.artifact_id $ExpectedCrpId
Require-Equal "LOCK_ACCEPTANCE" $LockObj.task04_acceptance_manifest.artifact_id $ExpectedAcceptanceId
Require-Equal "LOCK_CLASSIFICATION_RPM" $LockObj.classification_runtime_profile_admission_manifest.artifact_id $ExpectedClassificationRpmId
Require-Equal "LOCK_FOUNDATION_RPM" $LockObj.foundation_runtime_profile_admission_manifest.artifact_id $ExpectedFoundationRpmId
Require-Equal "LOCK_FOUNDATION_ADMISSION" $LockObj.foundation_admission_manifest.artifact_id $ExpectedFoundationAdmissionId

$SourceDbSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ControlDb).Hash.ToLowerInvariant()
Require-Equal "CONTROL_DB_SHA_VS_TACCEPT_LOCK" $SourceDbSha $LockObj.control_db_sha256_after

$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$OutDir = Join-Path $Lab "artifacts\TASK04-PROD-ACTIVATION-SEED-$Stamp"
New-Item -ItemType Directory -Path $OutDir | Out-Null

$SeedDb = Join-Path $OutDir "task04-production-control-plane-seed.sqlite3"
$Manifest = Join-Path $OutDir "task04-production-control-plane-seed-manifest.json"
$QueryJson = Join-Path $OutDir "task04-production-control-plane-seed-query.json"

$PyCode = @'
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
out = Path(sys.argv[3])

if dst.exists():
    raise SystemExit("SEED_DB_ALREADY_EXISTS")

source = sqlite3.connect(f"{src.resolve().as_uri()}?mode=ro", uri=True)
source.row_factory = sqlite3.Row
source.execute("PRAGMA query_only=ON")
target = sqlite3.connect(dst)
try:
    source.backup(target)
finally:
    target.close()
    source.close()

conn = sqlite3.connect(f"{dst.resolve().as_uri()}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
try:
    quick = conn.execute("PRAGMA quick_check").fetchone()[0]
    pointers = [dict(r) for r in conn.execute(
        "SELECT profile_kind,runtime_profile_id,runtime_profile_digest,"
        "activation_record_id,activation_generation_id,updated_at_utc "
        "FROM active_pointers ORDER BY profile_kind"
    )]
    artifact_ids = {
        r["artifact_id"]: dict(r)
        for r in conn.execute(
            "SELECT artifact_id,artifact_type,content_sha256 "
            "FROM artifacts"
        )
    }
    activation_counts = {
        r["profile_kind"]: r["n"]
        for r in conn.execute(
            "SELECT profile_kind,COUNT(*) AS n FROM activations GROUP BY profile_kind"
        )
    }
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )]
finally:
    conn.close()

payload = {
    "quick_check": quick,
    "active_pointers": pointers,
    "activation_counts": activation_counts,
    "tables": tables,
    "artifacts": artifact_ids,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
'@

$PyFile = Join-Path $OutDir "_make_seed.py"
Set-Content -LiteralPath $PyFile -Value $PyCode -Encoding UTF8
& $Python $PyFile $ControlDb $SeedDb $QueryJson
if ($LASTEXITCODE -ne 0) { throw "PYTHON_SEED_EXPORT_FAILED exit=$LASTEXITCODE" }
Remove-Item -LiteralPath $PyFile -Force

$Query = Get-Content -Raw -LiteralPath $QueryJson | ConvertFrom-Json
Require-Equal "SEED_QUICK_CHECK" $Query.quick_check "ok"

$FoundationPointers = @($Query.active_pointers | Where-Object { $_.profile_kind -eq "foundation" })
$ClassificationPointers = @($Query.active_pointers | Where-Object { $_.profile_kind -eq "classification" })
if ($FoundationPointers.Count -ne 1) { throw "FOUNDATION_POINTER_COUNT=$($FoundationPointers.Count)" }
if ($ClassificationPointers.Count -ne 0) { throw "CLASSIFICATION_POINTER_COUNT=$($ClassificationPointers.Count)" }
Require-Equal "FOUNDATION_POINTER_PROFILE" $FoundationPointers[0].runtime_profile_id $ExpectedFoundationProfileId

foreach ($Id in @(
    $ExpectedCrpId,
    $ExpectedAcceptanceId,
    $ExpectedClassificationRpmId,
    $ExpectedFoundationProfileId,
    $ExpectedFoundationRpmId,
    $ExpectedFoundationAdmissionId
)) {
    if (-not $Query.artifacts.PSObject.Properties.Name.Contains($Id)) {
        throw "REQUIRED_ARTIFACT_MISSING: $Id"
    }
}

$SeedSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SeedDb).Hash.ToLowerInvariant()
if ($SeedSha -ne $SourceDbSha) {
    # sqlite3 backup may produce byte-different but semantically identical files because
    # page layout/header counters can differ. This is not an error. Record both hashes.
    $ByteIdentity = $false
} else {
    $ByteIdentity = $true
}

$ManifestObj = [ordered]@{
    manifest_version = 1
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    source_control_db = $ControlDb
    source_control_db_sha256 = $SourceDbSha
    taccept_lock = $Lock
    taccept_lock_sha256 = $LockSha
    taccept_lock_control_db_sha256_after = [string]$LockObj.control_db_sha256_after
    seed_db = $SeedDb
    seed_db_sha256 = $SeedSha
    seed_byte_identical_to_source = $ByteIdentity
    quick_check = [string]$Query.quick_check
    foundation_pointer_count = $FoundationPointers.Count
    foundation_runtime_profile_id = [string]$FoundationPointers[0].runtime_profile_id
    classification_pointer_count = $ClassificationPointers.Count
    classification_active = $false
    required_artifacts = @(
        $ExpectedCrpId,
        $ExpectedAcceptanceId,
        $ExpectedClassificationRpmId,
        $ExpectedFoundationProfileId,
        $ExpectedFoundationRpmId,
        $ExpectedFoundationAdmissionId
    )
    production_activation = $false
    status = "ACTIVATION_SEED_PREPARED_INACTIVE"
}
$ManifestObj | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Manifest -Encoding UTF8

Write-Host ""
Write-Host "TASK04_ACTIVATION_SEED_PREP=PASS"
Write-Host "SOURCE_CONTROL_DB=$ControlDb"
Write-Host "SOURCE_CONTROL_DB_SHA256=$SourceDbSha"
Write-Host "TACCEPT_LOCK_SHA256=$LockSha"
Write-Host "SEED_DB=$SeedDb"
Write-Host "SEED_DB_SHA256=$SeedSha"
Write-Host "SEED_BYTE_IDENTICAL_TO_SOURCE=$ByteIdentity"
Write-Host "FOUNDATION_POINTER_COUNT=$($FoundationPointers.Count)"
Write-Host "FOUNDATION_PROFILE=$($FoundationPointers[0].runtime_profile_id)"
Write-Host "CLASSIFICATION_POINTER_COUNT=$($ClassificationPointers.Count)"
Write-Host "CLASSIFICATION_ACTIVATION=NO"
Write-Host "MANIFEST=$Manifest"
Write-Host "QUERY_JSON=$QueryJson"
Write-Host "OUT_DIR=$OutDir"
