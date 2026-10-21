$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Diag = 'C:\CaptivPortal-Lab\tools\taccept-r4-ttl-proof-forensics-v1.py'
$ExpectedSha = '989a26709e08582ff19b4e7312444411ce312f0ff5ee64b53e8736d5464e51ef'

foreach ($Path in @($Python,$Diag)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "TACCEPT_TTL_FORENSICS_REQUIRED_PATH_MISSING:$Path"
    }
}

$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Diag).Hash.ToLowerInvariant()
Write-Host "TACCEPT_TTL_FORENSICS_RUNNER_SHA256=$Actual"
if ($Actual -ne $ExpectedSha) {
    throw "TACCEPT_TTL_FORENSICS_RUNNER_SHA256_MISMATCH"
}

& $Python -I -B $Diag
$Code = $LASTEXITCODE
Write-Host "TACCEPT_TTL_FORENSICS_PROCESS_EXIT_CODE=$Code"
if ($Code -ne 0) {
    throw "TACCEPT_TTL_FORENSICS_FAILED:$Code"
}
Write-Host "TACCEPT_TTL_FORENSICS_LAUNCHER_STATUS=PASS"
