[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $venvPython) {
    $pythonExe = $venvPython
    $pythonPrefixArgs = @()
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $pythonExe = "py.exe"
    $pythonPrefixArgs = @("-3.11")
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    $pythonExe = "python.exe"
    $pythonPrefixArgs = @()
} else {
    throw "Python 3.11 was not found. Create .venv and install backend/requirements.txt first."
}

& $pythonExe @pythonPrefixArgs -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "DocTrace requires Python 3.11. Create .venv with Python 3.11 and install backend/requirements.txt."
}

$backendJob = Start-Job -Name "doctrace-backend" -ArgumentList $projectRoot, $pythonExe, $pythonPrefixArgs -ScriptBlock {
    param($root, $exe, $prefixArgs)
    Set-Location -LiteralPath $root
    & $exe @prefixArgs -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE -ne 0) { throw "Backend exited with code $LASTEXITCODE." }
}

$frontendJob = Start-Job -Name "doctrace-frontend" -ArgumentList $projectRoot -ScriptBlock {
    param($root)
    Set-Location -LiteralPath $root
    & npm.cmd run dev
    if ($LASTEXITCODE -ne 0) { throw "Frontend exited with code $LASTEXITCODE." }
}

$jobs = @($backendJob, $frontendJob)
Write-Host "DocTrace backend: http://127.0.0.1:8000"
Write-Host "DocTrace frontend: see the Vite URL below"
Write-Host "Press Ctrl+C to stop both servers."

try {
    while (($jobs | Where-Object State -eq "Running").Count -eq $jobs.Count) {
        Wait-Job -Job $jobs -Any -Timeout 1 | Out-Null
        $jobs | Receive-Job
    }

    $jobs | Receive-Job
    $failed = $jobs | Where-Object State -eq "Failed"
    if ($failed) {
        throw "A DocTrace development server stopped unexpectedly: $($failed.Name -join ', ')."
    }
} finally {
    $jobs | Where-Object State -eq "Running" | Stop-Job
    $jobs | Receive-Job -ErrorAction SilentlyContinue
    $jobs | Remove-Job -Force
}
