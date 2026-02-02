# EMS 2.0 Stop Script
# Stops all running EMS services

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  EMS 2.0 Stop Script" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Kill uvicorn processes (backend)
Write-Host "[1/3] Stopping Backend (uvicorn)..." -ForegroundColor Yellow
$uvicornProcesses = Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue
$pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*"
}

if ($uvicornProcesses -or $pythonProcesses) {
    $uvicornProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    $pythonProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] Backend stopped" -ForegroundColor Green
} else {
    Write-Host "  [OK] Backend not running" -ForegroundColor Gray
}

# Kill node processes (frontend - vite)
Write-Host "`n[2/3] Stopping Frontend (node/vite)..." -ForegroundColor Yellow
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue

if ($nodeProcesses) {
    # Be careful - only kill vite-related node processes
    # Check command line for vite
    $nodeProcesses | ForEach-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
            if ($cmdLine -like "*vite*" -or $cmdLine -like "*frontend*") {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                Write-Host "  Stopped node process: $($_.Id)" -ForegroundColor Gray
            }
        } catch {}
    }
    Write-Host "  [OK] Frontend stopped" -ForegroundColor Green
} else {
    Write-Host "  [OK] Frontend not running" -ForegroundColor Gray
}

# Optionally stop Ollama (don't stop by default as user might want it running)
Write-Host "`n[3/3] Ollama status..." -ForegroundColor Yellow
$ollamaProcess = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if ($ollamaProcess) {
    Write-Host "  [INFO] Ollama is running (not stopped - may be used by other apps)" -ForegroundColor Gray
    Write-Host "  To stop Ollama manually: Stop-Process -Name ollama" -ForegroundColor Gray
} else {
    Write-Host "  [OK] Ollama not running" -ForegroundColor Gray
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  All EMS services stopped" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
