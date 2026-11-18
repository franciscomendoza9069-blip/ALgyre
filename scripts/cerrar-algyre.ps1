$ErrorActionPreference = 'Stop'
$algyreRoot = Split-Path -Parent $PSScriptRoot
$algyrePidFile = Join-Path $algyreRoot 'data\server.pid'
if (Test-Path -LiteralPath $algyrePidFile) {
    $algyreSavedPid = [int](Get-Content -LiteralPath $algyrePidFile)
    $algyreRunning = Get-CimInstance Win32_Process -Filter "ProcessId = $algyreSavedPid" -ErrorAction SilentlyContinue
    $algyreExpectedExe = Join-Path $algyreRoot '.venv\Scripts\python.exe'
    $algyreExpectedApp = Join-Path $algyreRoot 'app.py'
    if ($algyreRunning -and $algyreRunning.ExecutablePath -eq $algyreExpectedExe -and $algyreRunning.CommandLine.Contains($algyreExpectedApp)) {
        Stop-Process -Id $algyreSavedPid
    }
}
