$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Diag = 'C:\CaptivPortal-Lab\tools\t09-r4-real-input-verify-v7.py'
$ExpectedDiagSha = '5add4bfcae0a7369c29d244e8852cbd47683dd980783fc27de28fe8eb58a1246'

foreach ($Path in @($Python,$Diag)) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "T09_R4_V7_REQUIRED_PATH_MISSING:$Path" }
}

$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Diag).Hash.ToLowerInvariant()
Write-Host "T09_R4_V7_DIAG_SHA256=$Actual"
if ($Actual -ne $ExpectedDiagSha) { throw "T09_R4_V7_DIAG_SHA256_MISMATCH" }

& $Python -I -B $Diag
$Code = $LASTEXITCODE
Write-Host "T09_R4_V7_PROCESS_EXIT_CODE=$Code"
if ($Code -ne 0) { throw "T09_R4_V7_FAILED:$Code" }
Write-Host "T09_R4_V7_LAUNCHER_STATUS=PASS"
