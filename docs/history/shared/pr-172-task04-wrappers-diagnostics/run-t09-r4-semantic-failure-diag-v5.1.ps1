$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Diag = 'C:\CaptivPortal-Lab\tools\t09-r4-semantic-failure-diag-v5.1.py'
$ExpectedDiagSha = '77636659f07c746f971ba84667faf32b1b1bfe90e6e5dccb547f56e01c779cfa'

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
