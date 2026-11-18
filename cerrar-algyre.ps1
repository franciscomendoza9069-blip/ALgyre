$ErrorActionPreference = 'Stop'
$algyrePidFile = Join-Path $PSScriptRoot 'data\server.pid'
if (Test-Path -LiteralPath $algyrePidFile) {
    $algyreSavedPid = [int](Get-Content -LiteralPath $algyrePidFile)
    $algyreRunning = Get-CimInstance Win32_Process -Filter "ProcessId = $algyreSavedPid" -ErrorAction SilentlyContinue
    $algyreExpectedExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $algyreExpectedApp = Join-Path $PSScriptRoot 'app.py'
    if ($algyreRunning -and $algyreRunning.ExecutablePath -eq $algyreExpectedExe -and $algyreRunning.CommandLine.Contains($algyreExpectedApp)) {
        Stop-Process -Id $algyreSavedPid
    }
}
