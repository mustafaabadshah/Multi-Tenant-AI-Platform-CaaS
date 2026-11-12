<#
.SYNOPSIS
    Automated sequential live integration test runner for MM AI Platform (M05 BLK-01).

.DESCRIPTION
    Safely executes live container integration tests for PostgreSQL 16, pgvector,
    native PostgreSQL Full-Text Search, and Qdrant vector database.
    Enforces the mandatory 2048 MB available physical RAM threshold.

.PARAMETER Mode
    Execution mode: 'postgres', 'qdrant', or 'all' (default: 'all').

.PARAMETER Force
    Switch to bypass the host RAM safety threshold (use only in isolated CI runners).

.PARAMETER OutputDir
    Directory path to store test execution logs, junit results, and summaries.

.EXAMPLE
    .\run-live-integration-tests.ps1 -Mode all
    .\run-live-integration-tests.ps1 -Mode postgres -OutputDir ./test_logs
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("postgres", "qdrant", "all")]
    [string]$Mode = "all",

    [Parameter(Mandatory=$false)]
    [switch]$Force,

    [Parameter(Mandatory=$false)]
    [string]$OutputDir
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackendDir = Join-Path $RootDir "backend"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $RootDir ("test_results_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
}
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Write-Host "=========================================================="
Write-Host "  MM AI Platform -- Live Infrastructure Integration Runner"
Write-Host "  Execution Mode: $Mode"
Write-Host "  Output Directory: $OutputDir"
Write-Host "=========================================================="

# 1. Host Memory Preflight Check
$Mem = Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory
$FreeMB = [math]::Round($Mem.FreePhysicalMemory / 1024, 1)
Write-Host "Host Available Physical RAM: $FreeMB MB"

if ($FreeMB -lt 2048 -and -not $Force) {
    Write-Warning "Host available RAM ($FreeMB MB) is below the mandatory 2048 MB memory safety threshold."
    Write-Warning "To prevent system thrashing and instability, live container workloads are withheld."
    Write-Warning "To execute in an isolated CI runner with adequate memory, run with -Force."
    exit 2
}

# 2. Docker Daemon Connectivity Check
try {
    $DockerInfo = docker info 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker daemon is not running or unreachable. Please start Docker Desktop or the WSL2 backend."
        exit 1
    }
} catch {
    Write-Error "Docker client error: $_"
    exit 1
}

# Helper to test if a port is in use
function Test-PortOccupied([int]$Port) {
    try {
        $TcpClient = New-Object System.Net.Sockets.TcpClient
        $Connect = $TcpClient.BeginConnect("127.0.0.1", $Port, $null, $null)
        $Success = $Connect.AsyncWaitHandle.WaitOne(500, $false)
        if ($Success) {
            $TcpClient.EndConnect($Connect)
            $TcpClient.Close()
            return $true
        }
        $TcpClient.Close()
        return $false
    } catch {
        return $false
    }
}

$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$PostgresCompose = Join-Path $RootDir "docker-compose.m05-postgres.yml"
$QdrantCompose = Join-Path $RootDir "docker-compose.m05-qdrant.yml"

$PostgresPassed = $false
$QdrantPassed = $false
$OverallFailed = $false

# ==============================================================================
# 3. Stage 1: PostgreSQL 16 + pgvector Live Integration
# ==============================================================================
if ($Mode -eq "postgres" -or $Mode -eq "all") {
    Write-Host "`n[Stage: PostgreSQL] Checking port 55432..."
    if (Test-PortOccupied -Port 55432) {
        Write-Error "Port 55432 is already in use by another service. Aborting."
        exit 1
    }

    Write-Host "Starting isolated PostgreSQL 16 + pgvector container..."
    docker compose -f $PostgresCompose up -d

    Write-Host "Waiting for PostgreSQL service health check..."
    $Retries = 20
    $Healthy = $false
    while ($Retries -gt 0) {
        $HealthStatus = docker inspect --format="{{.State.Health.Status}}" m05_postgres_test 2>$null
        if ($HealthStatus -eq "healthy") {
            $Healthy = $true
            break
        }
        Start-Sleep -Seconds 2
        $Retries--
    }

    if (-not $Healthy) {
        Write-Error "PostgreSQL container failed to become healthy within timeout."
        docker logs m05_postgres_test | Out-File -FilePath (Join-Path $OutputDir "postgres_container_failure.log") -Encoding utf8
        docker compose -f $PostgresCompose down
        exit 1
    }

    Write-Host "Executing 12 PostgreSQL & pgvector integration test nodes..."
    $PgOutFile = Join-Path $OutputDir "postgres_test_output.txt"
    $PgJunit = Join-Path $OutputDir "postgres_test_junit.xml"
    Push-Location $BackendDir
    try {
        & $PythonExe -m pytest `
            tests/integration/test_postgres_connection.py `
            tests/integration/test_postgres_migrations.py `
            tests/integration/test_pgvector_operations.py `
            tests/integration/test_postgres_fts.py `
            tests/integration/test_postgres_tenant_isolation.py `
            --junitxml=$PgJunit `
            -v | Tee-Object -FilePath $PgOutFile
        if ($LASTEXITCODE -eq 0) {
            $PostgresPassed = $true
        } else {
            $OverallFailed = $true
        }
    } finally {
        Pop-Location
        docker logs m05_postgres_test | Out-File -FilePath (Join-Path $OutputDir "postgres_container_logs.txt") -Encoding utf8
        Write-Host "Stopping PostgreSQL container..."
        docker compose -f $PostgresCompose down
    }
}

# ==============================================================================
# 4. Stage 2: Qdrant Live Integration
# ==============================================================================
if ($Mode -eq "qdrant" -or $Mode -eq "all") {
    Write-Host "`n[Stage: Qdrant] Checking port 6333..."
    if (Test-PortOccupied -Port 6333) {
        Write-Error "Port 6333 is already in use by another service. Aborting."
        exit 1
    }

    Write-Host "Starting isolated Qdrant vector database container..."
    docker compose -f $QdrantCompose up -d

    Write-Host "Waiting for Qdrant service health check..."
    $Retries = 20
    $Healthy = $false
    while ($Retries -gt 0) {
        $HealthStatus = docker inspect --format="{{.State.Health.Status}}" m05_qdrant_test 2>$null
        if ($HealthStatus -eq "healthy") {
            $Healthy = $true
            break
        }
        Start-Sleep -Seconds 2
        $Retries--
    }

    if (-not $Healthy) {
        Write-Error "Qdrant container failed to become healthy within timeout."
        docker logs m05_qdrant_test | Out-File -FilePath (Join-Path $OutputDir "qdrant_container_failure.log") -Encoding utf8
        docker compose -f $QdrantCompose down
        exit 1
    }

    Write-Host "Executing 5 Qdrant live integration test nodes..."
    $QdOutFile = Join-Path $OutputDir "qdrant_test_output.txt"
    $QdJunit = Join-Path $OutputDir "qdrant_test_junit.xml"
    Push-Location $BackendDir
    try {
        & $PythonExe -m pytest `
            tests/integration/test_qdrant_live_integration.py `
            --junitxml=$QdJunit `
            -v | Tee-Object -FilePath $QdOutFile
        if ($LASTEXITCODE -eq 0) {
            $QdrantPassed = $true
        } else {
            $OverallFailed = $true
        }
    } finally {
        Pop-Location
        docker logs m05_qdrant_test | Out-File -FilePath (Join-Path $OutputDir "qdrant_container_logs.txt") -Encoding utf8
        Write-Host "Stopping Qdrant container..."
        docker compose -f $QdrantCompose down
    }
}

Write-Host "`n=========================================================="
Write-Host "  MM AI Platform -- Live Test Execution Summary"
Write-Host "=========================================================="
Write-Host "Mode: $Mode"
if ($Mode -eq "postgres" -or $Mode -eq "all") {
    Write-Host ("PostgreSQL Tests: " + ($(if ($PostgresPassed) { "PASSED" } else { "FAILED" })))
}
if ($Mode -eq "qdrant" -or $Mode -eq "all") {
    Write-Host ("Qdrant Tests:     " + ($(if ($QdrantPassed) { "PASSED" } else { "FAILED" })))
}
Write-Host "Artifacts saved to: $OutputDir"
Write-Host "=========================================================="

if ($OverallFailed) {
    exit 1
} else {
    exit 0
}
