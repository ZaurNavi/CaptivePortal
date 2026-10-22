$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Diag = 'C:\CaptivPortal-Lab\tools\taccept-r3-lineage-forensics-v1.py'
$ExpectedSha = '031e85d89f08eb65a6a4cb8ab12c17bac4d803fcb2d8465dffa1b976aca59102'

foreach ($Path in @($Python,$Diag)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "TACCEPT_FORENSICS_REQUIRED_PATH_MISSING:$Path"
    }
}

$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Diag).Hash.ToLowerInvariant()
Write-Host "TACCEPT_FORENSICS_RUNNER_SHA256=$Actual"
if ($Actual -ne $ExpectedSha) {
    throw "TACCEPT_FORENSICS_RUNNER_SHA256_MISMATCH"
}

& $Python -I -B $Diag
$Code = $LASTEXITCODE
Write-Host "TACCEPT_FORENSICS_PROCESS_EXIT_CODE=$Code"
if ($Code -ne 0) {
    throw "TACCEPT_FORENSICS_FAILED:$Code"
}
Write-Host "TACCEPT_FORENSICS_LAUNCHER_STATUS=PASS"
