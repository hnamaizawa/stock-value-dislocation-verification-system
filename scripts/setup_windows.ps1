param(
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Test-PythonExecutable {
    param([string]$Executable)

    if ([string]::IsNullOrWhiteSpace($Executable)) {
        return $false
    }

    if (-not (Test-Path -LiteralPath $Executable)) {
        return $false
    }

    try {
        $versionText = & $Executable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }

        $parts = $versionText.Trim().Split('.')
        if ($parts.Count -lt 2) {
            return $false
        }

        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        return (($major -gt 3) -or (($major -eq 3) -and ($minor -ge 11)))
    }
    catch {
        return $false
    }
}

function Find-PythonExecutable {
    $candidates = New-Object System.Collections.Generic.List[string]

    $versionFolder = "Python" + $PythonVersion.Replace('.', '')
    $knownPaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\$versionFolder\python.exe"),
        (Join-Path $env:ProgramFiles "$versionFolder\python.exe")
    )

    if (${env:ProgramFiles(x86)}) {
        $knownPaths += (Join-Path ${env:ProgramFiles(x86)} "$versionFolder\python.exe")
    }

    foreach ($path in $knownPaths) {
        if ($path) {
            $candidates.Add($path)
        }
    }

    $searchRoots = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python"),
        $env:ProgramFiles
    )

    if (${env:ProgramFiles(x86)}) {
        $searchRoots += ${env:ProgramFiles(x86)}
    }

    foreach ($root in $searchRoots) {
        if (-not $root -or -not (Test-Path -LiteralPath $root)) {
            continue
        }

        Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "Python3*" } |
            ForEach-Object {
                $candidate = Join-Path $_.FullName "python.exe"
                $candidates.Add($candidate)
            }
    }

    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source) {
        $candidates.Add($pythonCommand.Source)
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-PythonExecutable -Executable $candidate) {
            return $candidate
        }
    }

    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
        foreach ($selector in @("-$PythonVersion", "-3")) {
            try {
                $resolved = & $pyCommand.Source $selector -c "import sys; print(sys.executable)" 2>$null
                if (($LASTEXITCODE -eq 0) -and $resolved) {
                    $resolvedPath = $resolved.Trim()
                    if (Test-PythonExecutable -Executable $resolvedPath) {
                        return $resolvedPath
                    }
                }
            }
            catch {
                # Continue to the next selector.
            }
        }
    }

    return $null
}

function Invoke-CheckedCommand {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage Exit code: $LASTEXITCODE"
    }
}

Write-Host "=== Stock Value Dislocation Verification System Setup ===" -ForegroundColor Cyan
Write-Host "Project folder: $ProjectRoot"

$pythonExe = Find-PythonExecutable

if (-not $pythonExe) {
    Write-Host "Python 3.11 or newer was not found." -ForegroundColor Yellow

    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "WinGet was not found. Install Python 3.12 from python.org, select Add Python to PATH, and run setup_windows.cmd again."
    }

    Write-Host "Installing Python 3.12 with WinGet..." -ForegroundColor Yellow
    & $winget.Source install --id Python.Python.3.12 --exact --scope user --silent --accept-source-agreements --accept-package-agreements
    if (($LASTEXITCODE -ne 0) -and ($LASTEXITCODE -ne 3010)) {
        throw "Python installation failed. Exit code: $LASTEXITCODE"
    }

    Start-Sleep -Seconds 2
    $pythonExe = Find-PythonExecutable
}

if (-not $pythonExe) {
    throw "Python was installed but python.exe could not be located. Close this window, sign out of Windows once, and run setup_windows.cmd again."
}

Write-Host "Python executable: $pythonExe" -ForegroundColor Green
Invoke-CheckedCommand -Executable $pythonExe -Arguments @("--version") -FailureMessage "Python could not be started."

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    Invoke-CheckedCommand -Executable $pythonExe -Arguments @("-m", "venv", ".venv") -FailureMessage "Virtual environment creation failed."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "The virtual environment was not created correctly."
}

Write-Host "Upgrading pip..." -ForegroundColor Yellow
Invoke-CheckedCommand -Executable $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") -FailureMessage "pip upgrade failed."

Write-Host "Installing project packages..." -ForegroundColor Yellow
Invoke-CheckedCommand -Executable $venvPython -Arguments @("-m", "pip", "install", "-e", ".[dashboard,dev]") -FailureMessage "Package installation failed."

if ((Test-Path -LiteralPath ".env.example") -and (-not (Test-Path -LiteralPath ".env"))) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}

Write-Host "Running tests..." -ForegroundColor Yellow
Invoke-CheckedCommand -Executable $venvPython -Arguments @("-m", "pytest", "-q") -FailureMessage "Tests failed."

$marker = Join-Path $ProjectRoot ".setup_complete"
Set-Content -LiteralPath $marker -Value (Get-Date -Format "yyyy-MM-dd HH:mm:ss") -Encoding ASCII

Write-Host ""
Write-Host "Setup completed successfully." -ForegroundColor Green
Write-Host "Next, double-click start_dashboard.cmd for actual-data search or run_demo.cmd for sample data."
