$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Diag = 'C:\CaptivPortal-Lab\tools\taccept-r4-ttl-proof-forensics-v1.1.py'
$ExpectedSha = '84f3f07a02ca05bfe636ed84031c616f3750da46feafc2861db0c8266c781237'

foreach ($Path in @($Python,$Diag)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "TACCEPT_TTL_FORENSICS_V11_REQUIRED_PATH_MISSING:$Path"
    }
}

$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Diag).Hash.ToLowerInvariant()
Write-Host "TACCEPT_TTL_FORENSICS_V11_RUNNER_SHA256=$Actual"
if ($Actual -ne $ExpectedSha) {
    throw "TACCEPT_TTL_FORENSICS_V11_RUNNER_SHA256_MISMATCH"
}

& $Python -I -B $Diag
$Code = $LASTEXITCODE
Write-Host "TACCEPT_TTL_FORENSICS_V11_PROCESS_EXIT_CODE=$Code"
if ($Code -ne 0) {
    throw "TACCEPT_TTL_FORENSICS_V11_FAILED:$Code"
}
Write-Host "TACCEPT_TTL_FORENSICS_V11_LAUNCHER_STATUS=PASS"
