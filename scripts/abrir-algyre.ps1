param([switch]$NoBrowser, [ValidateRange(1024, 65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$algyreRoot = Split-Path -Parent $PSScriptRoot
$algyrePython = Join-Path $algyreRoot '.venv\Scripts\python.exe'
$algyreUrl = "http://127.0.0.1:$Port"
# This launcher always opens this folder's private installation.
$env:ALGYRE_MODE = 'local'
$env:ALGYRE_PORT = [string]$Port
$env:ALGYRE_DATA_DIR = Join-Path $algyreRoot 'data'
$algyreAlreadyRunning = $false
try {
    $algyreStatus = Invoke-RestMethod -Uri ($algyreUrl + '/api/status') -TimeoutSec 2
    $algyreAlreadyRunning = $null -ne $algyreStatus.configured
} catch { }
if (-not $algyreAlreadyRunning) {
    if (-not (Test-Path -LiteralPath $algyrePython)) {
        python -m venv (Join-Path $algyreRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno. Instala Python 3.11 o posterior.' }
    }
    # Missing modules must return an exit code, not write a Python traceback:
    # Windows PowerShell 5 treats that stderr as a terminating error.
    & $algyrePython -c "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ['flask','pypdf','reportlab','waitress','openpyxl','defusedxml']) else 1)"
    $algyreNeedsPackages = $LASTEXITCODE -ne 0
    $algyreRequirements = Join-Path $algyreRoot 'requirements-lock.txt'
    $algyreHasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $algyreFingerprint = [BitConverter]::ToString($algyreHasher.ComputeHash([System.IO.File]::ReadAllBytes($algyreRequirements))).Replace('-', '')
    } finally { $algyreHasher.Dispose() }
    $algyreMarker = Join-Path $algyreRoot '.venv\algyre-requirements.sha256'
    $algyreSavedFingerprint = if (Test-Path -LiteralPath $algyreMarker) { (Get-Content -LiteralPath $algyreMarker -Raw).Trim() } else { '' }
    if ($algyreNeedsPackages -or $algyreSavedFingerprint -ne $algyreFingerprint) {
        & $algyrePython -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar el instalador de dependencias. Revisa tu instalación de Python.' }
        & $algyrePython -m pip install --disable-pip-version-check -r $algyreRequirements
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
        $algyreFingerprint | Set-Content -LiteralPath $algyreMarker
    }
    $algyreLog = Join-Path $algyreRoot 'data'
    New-Item -ItemType Directory -Path $algyreLog -Force | Out-Null
    $algyreProcess = Start-Process -FilePath $algyrePython -ArgumentList @('"' + (Join-Path $algyreRoot 'app.py') + '"') -WorkingDirectory $algyreRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $algyreLog 'server.log') -RedirectStandardError (Join-Path $algyreLog 'server-error.log')
    $algyreProcess.Id | Set-Content -LiteralPath (Join-Path $algyreLog 'server.pid')
    for ($algyreAttempt = 0; $algyreAttempt -lt 30; $algyreAttempt++) {
        Start-Sleep -Milliseconds 400
        try {
            $algyreReady = Invoke-RestMethod -Uri ($algyreUrl + '/api/status') -TimeoutSec 2
            if ($null -ne $algyreReady.configured) { $algyreAlreadyRunning = $true; break }
        } catch { }
        if ($algyreProcess.HasExited) { break }
    }
    if (-not $algyreAlreadyRunning) { throw 'No se pudo iniciar ALgyre. Consulta data\server-error.log.' }
}
if (-not $NoBrowser) { Start-Process $algyreUrl }
