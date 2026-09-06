$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment is not ready. Run setup_windows.cmd first."
}

$Today = Get-Date -Format "yyyy-MM-dd"
& $Python -m value_dislocation.cli screen --config config/default.yaml --as-of $Today
if ($LASTEXITCODE -ne 0) { throw "Screen command failed." }

& $Python -m value_dislocation.cli propose-orders --config config/default.yaml
if ($LASTEXITCODE -ne 0) { throw "Order proposal command failed." }

Write-Host "Completed. Review the outputs folder. No order was sent to SBI Securities."
