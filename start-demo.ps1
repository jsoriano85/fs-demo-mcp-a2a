# Start Ollama (if needed), the five Python servers, and the report UI.
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Missing $Python. Create the virtual environment before starting the demo."
    exit 1
}

function Test-Listening([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Start-DemoWindow([string]$Title, [string]$Command) {
    Start-Process -FilePath "powershell.exe" -WorkingDirectory $Root -ArgumentList @(
        "-NoExit",
        "-NoProfile",
        "-Command",
        "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location -LiteralPath '$Root'; $Command"
    )
    Write-Output "Started $Title"
}

if (Test-Listening 11434) {
    Write-Output "Ollama is already running."
} else {
    $ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path -LiteralPath $ollama) {
        Start-Process -FilePath $ollama
        Write-Output "Started Ollama."
    } else {
        Write-Warning "Ollama is not running and was not found. The coordinator needs it."
    }
}

$servers = @(
    @{ Title = "mcp"; Module = "mcp_server"; Port = 8000 },
    @{ Title = "coordinator"; Module = "coordinator_agent"; Port = 8001 },
    @{ Title = "diagnosis"; Module = "diagnosis_agent"; Port = 8002 },
    @{ Title = "repair"; Module = "repair_agent"; Port = 8003 },
    @{ Title = "fetch"; Module = "fetch_agent"; Port = 8004 }
)

foreach ($server in $servers) {
    if (Test-Listening $server.Port) {
        Write-Output "$($server.Title) is already running on port $($server.Port)."
        continue
    }
    Start-DemoWindow $server.Title "& '$Python' -m $($server.Module)"
}

if (Test-Listening 5173) {
    Write-Output "The UI is already running on port 5173."
} else {
    $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
    $uiCommand = if ($pnpm) { "pnpm --dir ui dev" } else { "corepack pnpm --dir ui dev" }
    Start-DemoWindow "ui" $uiCommand
}

Write-Output "Open http://127.0.0.1:5173 when the UI window is ready."
