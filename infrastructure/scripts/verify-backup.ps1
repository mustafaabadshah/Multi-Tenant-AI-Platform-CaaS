<#
.SYNOPSIS
    Verifies the integrity and TOC archive structure of a PostgreSQL backup file.

.DESCRIPTION
    Validates SHA-256 checksum against recorded value and runs pg_restore --list to
    verify table table-of-contents without restoring into a live database.

.PARAMETER BackupFilePath
    Path to the .dump file to verify.

.EXAMPLE
    .\verify-backup.ps1 -BackupFilePath "./backups/mmaip_backup_20261107_164500.dump"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFilePath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -Path $BackupFilePath)) {
    Write-Error "Backup file not found at: $BackupFilePath"
    exit 1
}

Write-Host "=========================================================="
Write-Host "  MM AI Platform - Backup Integrity Verification"
Write-Host "  Target: $BackupFilePath"
Write-Host "=========================================================="

# 1. Compute and verify SHA-256
$ActualHash = (Get-FileHash -Path $BackupFilePath -Algorithm SHA256).Hash
Write-Host "Computed SHA-256: $ActualHash"

$ChecksumFile = "${BackupFilePath}.sha256"
if (Test-Path -Path $ChecksumFile) {
    $ExpectedContent = Get-Content -Path $ChecksumFile -Raw
    $ExpectedHash = ($ExpectedContent -split "\s+")[0].Trim()
    if ($ActualHash.ToLower() -eq $ExpectedHash.ToLower()) {
        Write-Host " [PASS] Checksum matches recorded value: $ExpectedHash" -ForegroundColor Green
    } else {
        Write-Error " [FAIL] Checksum mismatch! Expected: $ExpectedHash, Got: $ActualHash"
        exit 1
    }
} else {
    Write-Warning "No companion .sha256 checksum file found. Verification based solely on file integrity."
}

# 2. Check pg_restore --list
$PgRestoreCmd = Get-Command "pg_restore" -ErrorAction SilentlyContinue
if (-not $PgRestoreCmd) {
    Write-Warning "pg_restore binary not found in PATH. Archive TOC check was not performed."
    Write-Warning "PARTIAL VERIFICATION: checksum-only result. This is NOT a full backup verification."
    exit 2
}

try {
    Write-Host "Inspecting archive Table of Contents (TOC) via pg_restore --list..."
    $Toc = & pg_restore --list $BackupFilePath 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pg_restore --list failed. The dump file may be corrupted."
        exit 1
    }

    $TableEntries = ($Toc | Where-Object { $_ -match "TABLE DATA" }).Count
    Write-Host " [PASS] Archive TOC readable. Found $TableEntries table data blocks." -ForegroundColor Green
}
catch {
    Write-Error "Failed to read archive TOC: $_"
    exit 1
}
