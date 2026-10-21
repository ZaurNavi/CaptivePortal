$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Diag = 'C:\CaptivPortal-Lab\tools\t09-r4-real-input-verify-v7.1.py'
$ExpectedDiagSha = 'f8ca49da0b3c5f08292d87f72fd1b2ad782db7c9e7002986f02dc17d39959cc2'

foreach ($Path in @($Python,$Diag)) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "T09_R4_V71_REQUIRED_PATH_MISSING:$Path" }
}

$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Diag).Hash.ToLowerInvariant()
Write-Host "T09_R4_V71_DIAG_SHA256=$Actual"
if ($Actual -ne $ExpectedDiagSha) { throw "T09_R4_V71_DIAG_SHA256_MISMATCH" }

& $Python -I -B $Diag
$Code = $LASTEXITCODE
Write-Host "T09_R4_V71_PROCESS_EXIT_CODE=$Code"
if ($Code -ne 0) { throw "T09_R4_V71_FAILED:$Code" }
Write-Host "T09_R4_V71_LAUNCHER_STATUS=PASS"
