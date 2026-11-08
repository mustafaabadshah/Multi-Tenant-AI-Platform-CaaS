<#
.SYNOPSIS
    Orchestrates a coordinated, paired backup of PostgreSQL database and storage files.

.DESCRIPTION
    Executes PostgreSQL database dump and storage archive, generating a unified
    disaster recovery manifest linking database snapshot and storage snapshot.

.PARAMETER DatabaseUrl
    PostgreSQL connection string. Defaults to $env:DATABASE_SYNC_URL or $env:DATABASE_URL.

.PARAMETER StoragePath
    Storage directory. Defaults to ./data/storage or $env:STORAGE_PATH.

.PARAMETER BackupDir
    Destination backup directory. Defaults to ./backups.

.EXAMPLE
    .\backup-paired.ps1
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$DatabaseUrl = $(if ($env:DATABASE_SYNC_URL) { $env:DATABASE_SYNC_URL } else { $env:DATABASE_URL }),

    [Parameter(Mandatory=$false)]
    [string]$StoragePath = $(if ($env:STORAGE_PATH) { $env:STORAGE_PATH } else { "./data/storage" }),

    [Parameter(Mandatory=$false)]
    [string]$BackupDir = "./backups"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
Write-Host "=========================================================="
Write-Host "  MM AI Platform — Paired Disaster Recovery Backup"
Write-Host "  Timestamp: $Timestamp"
Write-Host "=========================================================="

# 1. Run PostgreSQL Backup
$DbBackupScript = Join-Path -Path $PSScriptRoot -ChildPath "backup-postgres.ps1"
Write-Host "Step 1: Executing PostgreSQL database backup..."
& $DbBackupScript -DatabaseUrl $DatabaseUrl -BackupDir $BackupDir

# Locate the newly created DB manifest
$DbManifests = Get-ChildItem -Path $BackupDir -Filter "mmaip_backup_*.manifest.json" | Sort-Object LastWriteTime -Descending
$LatestDbManifest = $DbManifests[0].FullName
$DbManifestData = Get-Content -Path $LatestDbManifest -Raw | ConvertFrom-Json

# 2. Run Storage Backup paired with the DB manifest
$StorageBackupScript = Join-Path -Path $PSScriptRoot -ChildPath "backup-storage.ps1"
Write-Host "Step 2: Executing file storage backup..."
& $StorageBackupScript -StoragePath $StoragePath -BackupDir $BackupDir -PairedDatabaseManifest $LatestDbManifest

# Locate the newly created Storage manifest
$StorageManifests = Get-ChildItem -Path $BackupDir -Filter "mmaip_storage_backup_*.manifest.json" | Sort-Object LastWriteTime -Descending
$LatestStorageManifest = $StorageManifests[0].FullName
$StorageManifestData = Get-Content -Path $LatestStorageManifest -Raw | ConvertFrom-Json

# 3. Create Paired Coordination Manifest
$PairedManifestPath = Join-Path -Path $BackupDir -ChildPath "mmaip_paired_backup_${Timestamp}.manifest.json"
$PairedManifest = @{
    paired_backup_id   = "paired_${Timestamp}"
    timestamp          = (Get-Date).ToString("o")
    status             = "COMPLETED"
    database = @{
        backup_file = $DbManifestData.backup_file
        size_bytes  = $DbManifestData.size_bytes
        sha256      = $DbManifestData.sha256
        format      = $DbManifestData.format
        manifest    = $LatestDbManifest
    }
    storage = @{
        archive_file = $StorageManifestData.archive_file
        size_bytes   = $StorageManifestData.archive_size_bytes
        sha256       = $StorageManifestData.archive_sha256
        total_files  = $StorageManifestData.total_files
        total_bytes  = $StorageManifestData.total_bytes
        manifest     = $LatestStorageManifest
    }
} | ConvertTo-Json -Depth 5

Set-Content -Path $PairedManifestPath -Value $PairedManifest

Write-Host "=========================================================="
Write-Host " [PASS] Paired Disaster Recovery Backup Completed!" -ForegroundColor Green
Write-Host "  Paired Manifest: $PairedManifestPath"
Write-Host "  Database Dump:   $($DbManifestData.backup_file)"
Write-Host "  Storage Archive: $($StorageManifestData.archive_file)"
Write-Host "=========================================================="
