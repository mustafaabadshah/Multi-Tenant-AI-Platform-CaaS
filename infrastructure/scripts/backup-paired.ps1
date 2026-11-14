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
Write-Host "  MM AI Platform - Paired Disaster Recovery Backup"
Write-Host "  Timestamp: $Timestamp"
Write-Host "=========================================================="

# Artifacts older than this point belong to a previous run and are rejected.
$RunStart = (Get-Date).AddSeconds(-2)

# 1. Run PostgreSQL Backup
$DbBackupScript = Join-Path -Path $PSScriptRoot -ChildPath "backup-postgres.ps1"
Write-Host "Step 1: Executing PostgreSQL database backup..."
& $DbBackupScript -DatabaseUrl $DatabaseUrl -BackupDir $BackupDir
if ($LASTEXITCODE -ne 0) {
    Write-Error "Database backup failed with exit code $LASTEXITCODE. No paired manifest was written."
    exit 1
}

# Locate and validate the manifest produced by this run only
$DbManifests = @(Get-ChildItem -Path $BackupDir -Filter "mmaip_backup_*.manifest.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
if ($DbManifests.Count -eq 0) {
    Write-Error "No database backup manifest was produced. No paired manifest was written."
    exit 1
}
$LatestDbManifest = $DbManifests[0].FullName
if ($DbManifests[0].LastWriteTime -lt $RunStart) {
    Write-Error "Stale database manifest detected (not written by this run): $LatestDbManifest. No paired manifest was written."
    exit 1
}
$DbManifestData = Get-Content -Path $LatestDbManifest -Raw | ConvertFrom-Json
if (-not $DbManifestData.backup_file) {
    Write-Error "Database manifest does not reference a backup file: $LatestDbManifest"
    exit 1
}
$DbBackupFilePath = Join-Path -Path $BackupDir -ChildPath $DbManifestData.backup_file
if (-not (Test-Path -Path $DbBackupFilePath)) {
    Write-Error "Database backup artifact is missing: $DbBackupFilePath. No paired manifest was written."
    exit 1
}
$DbBackupItem = Get-Item -Path $DbBackupFilePath
if ($DbBackupItem.LastWriteTime -lt $RunStart) {
    Write-Error "Stale database backup artifact detected (not written by this run): $DbBackupFilePath. No paired manifest was written."
    exit 1
}
if ($DbBackupItem.Length -ne [long]$DbManifestData.size_bytes) {
    Write-Error "Database backup size mismatch: manifest=$($DbManifestData.size_bytes) actual=$($DbBackupItem.Length). No paired manifest was written."
    exit 1
}
$DbBackupHash = (Get-FileHash -Path $DbBackupFilePath -Algorithm SHA256).Hash
if ($DbBackupHash -ne $DbManifestData.sha256) {
    Write-Error "Database backup SHA-256 mismatch for $DbBackupFilePath. No paired manifest was written."
    exit 1
}

# 2. Run Storage Backup paired with the DB manifest
$StorageBackupScript = Join-Path -Path $PSScriptRoot -ChildPath "backup-storage.ps1"
Write-Host "Step 2: Executing file storage backup..."
& $StorageBackupScript -StoragePath $StoragePath -BackupDir $BackupDir -PairedDatabaseManifest $LatestDbManifest
if ($LASTEXITCODE -ne 0) {
    Write-Error "Storage backup failed with exit code $LASTEXITCODE. No paired manifest was written."
    exit 1
}

# Locate and validate the manifest produced by this run only
$StorageManifests = @(Get-ChildItem -Path $BackupDir -Filter "mmaip_storage_backup_*.manifest.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
if ($StorageManifests.Count -eq 0) {
    Write-Error "No storage backup manifest was produced. No paired manifest was written."
    exit 1
}
$LatestStorageManifest = $StorageManifests[0].FullName
if ($StorageManifests[0].LastWriteTime -lt $RunStart) {
    Write-Error "Stale storage manifest detected (not written by this run): $LatestStorageManifest. No paired manifest was written."
    exit 1
}
$StorageManifestData = Get-Content -Path $LatestStorageManifest -Raw | ConvertFrom-Json
if (-not $StorageManifestData.archive_file) {
    Write-Error "Storage manifest does not reference an archive file: $LatestStorageManifest"
    exit 1
}
$StorageArchivePath = Join-Path -Path $BackupDir -ChildPath $StorageManifestData.archive_file
if (-not (Test-Path -Path $StorageArchivePath)) {
    Write-Error "Storage backup artifact is missing: $StorageArchivePath. No paired manifest was written."
    exit 1
}
$StorageArchiveItem = Get-Item -Path $StorageArchivePath
if ($StorageArchiveItem.LastWriteTime -lt $RunStart) {
    Write-Error "Stale storage backup artifact detected (not written by this run): $StorageArchivePath. No paired manifest was written."
    exit 1
}
if ($StorageArchiveItem.Length -ne [long]$StorageManifestData.archive_size_bytes) {
    Write-Error "Storage archive size mismatch: manifest=$($StorageManifestData.archive_size_bytes) actual=$($StorageArchiveItem.Length). No paired manifest was written."
    exit 1
}
$StorageArchiveHash = (Get-FileHash -Path $StorageArchivePath -Algorithm SHA256).Hash
if ($StorageArchiveHash -ne $StorageManifestData.archive_sha256) {
    Write-Error "Storage archive SHA-256 mismatch for $StorageArchivePath. No paired manifest was written."
    exit 1
}

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
