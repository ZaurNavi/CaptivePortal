$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Diag = 'C:\CaptivPortal-Lab\tools\t09-r4-task01-membership-diag-v6.py'

$ExpectedDiagSha = '246827c3724a9d2a19aa2e2553023dc636a730d13d5a85a9e7c846bdab0ac4d7'

foreach ($Path in @($Python,$Diag)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "T09_R4_V6_REQUIRED_PATH_MISSING: $Path"
    }
}

$ActualDiagSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Diag).Hash.ToLowerInvariant()
Write-Host "T09_R4_V6_DIAG_SHA256=$ActualDiagSha"
if ($ActualDiagSha -ne $ExpectedDiagSha) {
    throw "T09_R4_V6_DIAG_SHA256_MISMATCH"
}

& $Python -I -B $Diag
$Code = $LASTEXITCODE
Write-Host "T09_R4_V6_PROCESS_EXIT_CODE=$Code"
if ($Code -ne 0) {
    throw "T09_R4_V6_FAILED:$Code"
}
Write-Host "T09_R4_V6_LAUNCHER_STATUS=PASS"
