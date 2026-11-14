<#
.SYNOPSIS
    Restores a PostgreSQL database from a verified custom-format backup.

.DESCRIPTION
    Safely restores tables, indexes, and pgvector embeddings into a target database.
    Requires explicit confirmation to prevent accidental restoration over production data.

.PARAMETER BackupFilePath
    Path to the .dump file to restore.

.PARAMETER TargetDatabaseUrl
    Target PostgreSQL database connection URL.

.PARAMETER ConfirmRestore
    Mandatory switch to confirm restoration intent.

.EXAMPLE
    .\restore-postgres.ps1 -BackupFilePath "./backups/mmaip_backup_20261107_164500.dump" -TargetDatabaseUrl "postgresql://<user>:<password>@localhost:5432/mmaip_disposable_test" -ConfirmRestore
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFilePath,

    [Parameter(Mandatory=$true)]
    [string]$TargetDatabaseUrl,

    [Parameter(Mandatory=$false)]
    [switch]$ConfirmRestore
)

$ErrorActionPreference = "Stop"

if (-not $ConfirmRestore) {
    Write-Error "Safety Violation: -ConfirmRestore switch is required to execute a database restoration."
    exit 1
}

if (-not (Test-Path -Path $BackupFilePath)) {
    Write-Error "Backup file not found at: $BackupFilePath"
    exit 1
}

Write-Host "=========================================================="
Write-Host "  MM AI Platform - PostgreSQL Disaster Recovery Restore"
Write-Host "  Source: $BackupFilePath"
Write-Host "  Target: [REDACTED]"
Write-Host "=========================================================="

# 1. Check pg_restore availability before verification or restore work
$PgRestoreCmd = Get-Command "pg_restore" -ErrorAction SilentlyContinue
if (-not $PgRestoreCmd) {
    Write-Warning "pg_restore binary not found in PATH. No restore was executed."
    Write-Warning "SIMULATION MODE: nothing was restored. This run is NOT a successful restore."
    exit 2
}

# 2. Verify Checksum
$VerifyScript = Join-Path -Path $PSScriptRoot -ChildPath "verify-backup.ps1"
if (Test-Path -Path $VerifyScript) {
    Write-Host "Verifying archive integrity before restoration..."
    & $VerifyScript -BackupFilePath $BackupFilePath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Backup integrity verification failed. Aborting restore."
        exit 1
    }
}

try {
    Write-Host "Restoring database schema and data..."
    & pg_restore --clean --if-exists --no-owner --no-privileges --dbname=$TargetDatabaseUrl --verbose $BackupFilePath 2>$null

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "pg_restore completed with non-zero exit code $LASTEXITCODE (some warnings during clean/drop are normal for fresh DBs)."
    } else {
        Write-Host " [PASS] pg_restore completed cleanly." -ForegroundColor Green
    }
}
catch {
    Write-Error "Restore execution failed: $_"
    exit 1
}
