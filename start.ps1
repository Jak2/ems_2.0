# EMS 2.0 Startup Script
# Run this script from the project root: .\start.ps1
# Starts backend and frontend in separate PowerShell windows (no Windows Terminal tabs)

param(
    [switch]$SkipInstall,    # Skip npm install and pip install
    [switch]$FrontendOnly,   # Only start frontend
    [switch]$BackendOnly     # Only start backend
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = Get-Location }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  EMS 2.0 Startup Script" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# ============================================
# 1. CHECK AND START MONGODB
# ============================================
function Start-MongoDB {
    Write-Host "[1/5] Checking MongoDB..." -ForegroundColor Yellow

    $mongoService = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue

    if ($mongoService) {
        if ($mongoService.Status -eq "Running") {
            Write-Host "  [OK] MongoDB is already running" -ForegroundColor Green
        } else {
            Write-Host "  [!] MongoDB is stopped. Starting..." -ForegroundColor Yellow
            try {
                Start-Service -Name "MongoDB" -ErrorAction Stop
                Write-Host "  [OK] MongoDB started successfully" -ForegroundColor Green
            } catch {
                Write-Host "  [ERROR] Failed to start MongoDB. Run as Administrator or start manually." -ForegroundColor Red
                Write-Host "  Command: net start MongoDB" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "  [WARN] MongoDB service not found. Checking if mongod is running..." -ForegroundColor Yellow
        $mongodProcess = Get-Process -Name "mongod" -ErrorAction SilentlyContinue
        if ($mongodProcess) {
            Write-Host "  [OK] mongod process is running" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] MongoDB not running. Start it manually or install as service." -ForegroundColor Yellow
        }
    }
}

# ============================================
# 2. CHECK AND START POSTGRESQL
# ============================================
function Start-PostgreSQL {
    Write-Host "`n[2/5] Checking PostgreSQL..." -ForegroundColor Yellow

    $pgServiceNames = @("postgresql-x64-16", "postgresql-x64-15", "postgresql-x64-14", "postgresql", "PostgreSQL")
    $pgService = $null

    foreach ($name in $pgServiceNames) {
        $pgService = Get-Service -Name $name -ErrorAction SilentlyContinue
        if ($pgService) {
            Write-Host "  Found PostgreSQL service: $name" -ForegroundColor Gray
            break
        }
    }

    if ($pgService) {
        if ($pgService.Status -eq "Running") {
            Write-Host "  [OK] PostgreSQL is already running" -ForegroundColor Green
        } else {
            Write-Host "  [!] PostgreSQL is stopped. Starting..." -ForegroundColor Yellow
            try {
                Start-Service -Name $pgService.Name -ErrorAction Stop
                Write-Host "  [OK] PostgreSQL started successfully" -ForegroundColor Green
            } catch {
                Write-Host "  [ERROR] Failed to start PostgreSQL. Run as Administrator or start manually." -ForegroundColor Red
                Write-Host "  Command: net start $($pgService.Name)" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "  [WARN] PostgreSQL service not found. Checking if postgres is running..." -ForegroundColor Yellow
        $pgProcess = Get-Process -Name "postgres" -ErrorAction SilentlyContinue
        if ($pgProcess) {
            Write-Host "  [OK] postgres process is running" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] PostgreSQL not running. Start it manually." -ForegroundColor Yellow
        }
    }
}

# ============================================
# 3. CHECK OLLAMA AND CONFIGURED MODEL
# ============================================
function Start-OllamaModel {
    Write-Host "`n[3/5] Checking Ollama and LLM model..." -ForegroundColor Yellow

    $envFile = Join-Path $ProjectRoot "backend\.env"
    $configuredModel = "qwen2.5:7b-instruct"

    if (Test-Path $envFile) {
        $envLines = Get-Content $envFile
        foreach ($line in $envLines) {
            if ($line -match "^OLLAMA_MODEL\s*=\s*(.+)$") {
                $modelValue = $Matches[1].Trim().Trim('"').Trim("'")
                if ($modelValue) { $configuredModel = $modelValue }
                break
            }
        }
    }

    Write-Host "  Configured model: $configuredModel" -ForegroundColor Gray

    $ollamaPath = Get-Command "ollama" -ErrorAction SilentlyContinue
    if (-not $ollamaPath) {
        Write-Host "  [ERROR] Ollama not found in PATH. Please install Ollama first." -ForegroundColor Red
        Write-Host "  Download from: https://ollama.ai" -ForegroundColor Gray
        return
    }

    try {
        $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
        Write-Host "  [OK] Ollama server is running" -ForegroundColor Green
    } catch {
        Write-Host "  [!] Ollama server not running. Starting..." -ForegroundColor Yellow
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "  [OK] Ollama server started" -ForegroundColor Green
    }

    Write-Host "  Checking running models..." -ForegroundColor Gray
    try {
        $runningModels = & ollama ps 2>&1
        if ($runningModels -match $configuredModel.Split(":")[0]) {
            Write-Host "  [OK] Model $configuredModel is loaded" -ForegroundColor Green
        } else {
            $localModels = & ollama list 2>&1
            if ($localModels -match $configuredModel.Split(":")[0]) {
                Write-Host "  [OK] Model found locally and ready" -ForegroundColor Green
            } else {
                Write-Host "  Pulling model (this may take a while)..." -ForegroundColor Yellow
                & ollama pull $configuredModel
                Write-Host "  [OK] Model pulled successfully" -ForegroundColor Green
            }
        }
    } catch {
        Write-Host "  [WARN] Could not check model status" -ForegroundColor Yellow
    }
}

# ============================================
# 4 & 5. START BACKEND AND FRONTEND IN SEPARATE POWERSHELL WINDOWS
# ============================================
function Start-Services {
    param(
        [bool]$StartBackend = $true,
        [bool]$StartFrontend = $true
    )

    # Simpler behavior: always open backend and frontend in separate PowerShell windows
    if ($StartBackend) { Start-BackendWindow }
    if ($StartFrontend) { Start-FrontendWindow }
}

# Fallback functions for systems without Windows Terminal
function Start-BackendWindow {
    Write-Host "`n[4/5] Starting Backend..." -ForegroundColor Yellow
    $backendPath = Join-Path $ProjectRoot "backend"
    $commands = @()
    if (-not $SkipInstall) {
        $commands += "pip install -r requirements.txt"
    }
    $commands += "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    $script = "Set-Location '$backendPath'; " + ($commands -join "; ")
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $script
    Write-Host "  [OK] Backend window opened" -ForegroundColor Green
}

function Start-FrontendWindow {
    Write-Host "`n[5/5] Starting Frontend..." -ForegroundColor Yellow
    $frontendPath = Join-Path $ProjectRoot "frontend"
    $commands = @()
    if (-not $SkipInstall) {
        $commands += "npm install"
    }
    $commands += "npm run dev"
    $script = "Set-Location '$frontendPath'; " + ($commands -join "; ")
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $script
    Write-Host "  [OK] Frontend window opened" -ForegroundColor Green
}

# ============================================
# MAIN EXECUTION
# ============================================

# Check databases and Ollama
Start-MongoDB
Start-PostgreSQL
Start-OllamaModel

# Start services based on flags
if ($FrontendOnly) {
    Start-Services -StartBackend $false -StartFrontend $true
} elseif ($BackendOnly) {
    Start-Services -StartBackend $true -StartFrontend $false
} else {
    Start-Services -StartBackend $true -StartFrontend $true
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Startup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nServices:" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Gray
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Gray
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "`nUsage:" -ForegroundColor White
Write-Host "  .\start.ps1              # Start all (2 tabs)" -ForegroundColor Gray
Write-Host "  .\start.ps1 -SkipInstall # Skip npm/pip install" -ForegroundColor Gray
Write-Host "  .\start.ps1 -BackendOnly # Only backend tab" -ForegroundColor Gray
Write-Host "  .\start.ps1 -FrontendOnly # Only frontend tab" -ForegroundColor Gray
Write-Host ""
