$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Diag = 'C:\CaptivPortal-Lab\tools\t09-r4-semantic-failure-diag-v5.py'
$ExpectedDiagSha = 'f2c11a35967efac61cf211e7e5c7f43a75d7a60b864a39ad952db41f91e72df8'

foreach ($Path in @($Python, $Diag)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "REQUIRED_FILE_MISSING: $Path" }
}

$ActualDiagSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Diag).Hash.ToLowerInvariant()
Write-Host "T09_R4_SEMANTIC_DIAG_SHA256=$ActualDiagSha"
if ($ActualDiagSha -ne $ExpectedDiagSha) { throw 'T09_R4_SEMANTIC_DIAG_SHA256_MISMATCH' }

& $Python -I -B $Diag
$Code = $LASTEXITCODE
Write-Host "T09_R4_SEMANTIC_DIAG_PROCESS_EXIT_CODE=$Code"
if ($Code -ne 0) { throw "T09_R4_SEMANTIC_DIAG_FAILED:$Code" }
Write-Host 'T09_R4_SEMANTIC_DIAG_LAUNCHER_STATUS=PASS'
