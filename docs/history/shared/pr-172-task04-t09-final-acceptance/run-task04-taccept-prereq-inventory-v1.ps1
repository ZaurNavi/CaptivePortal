$ErrorActionPreference = 'Stop'

$Python = 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe'
$Inventory = 'C:\CaptivPortal-Lab\tools\task04-taccept-prereq-inventory-v1.py'
$ExpectedSha = '6e20614d8d84557f8e084c5420e050a2864bea4f8be625ed5aeeeb46ee8d993f'

foreach ($Path in @($Python,$Inventory)) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "TACCEPT_INVENTORY_REQUIRED_PATH_MISSING:$Path" }
}

$Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Inventory).Hash.ToLowerInvariant()
Write-Host "TACCEPT_INVENTORY_RUNNER_SHA256=$Actual"
if ($Actual -ne $ExpectedSha) { throw "TACCEPT_INVENTORY_RUNNER_SHA256_MISMATCH" }

& $Python -I -B $Inventory
$Code = $LASTEXITCODE
Write-Host "TACCEPT_INVENTORY_PROCESS_EXIT_CODE=$Code"
if ($Code -ne 0) { throw "TACCEPT_INVENTORY_FAILED:$Code" }
Write-Host "TACCEPT_INVENTORY_LAUNCHER_STATUS=PASS"
