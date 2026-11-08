<#
.SYNOPSIS
    Creates a verified, timestamped archive backup of the MM AI Platform storage directory.

.DESCRIPTION
    Archives all tenant-isolated uploaded files (PDF, DOCX, XLSX, images, etc.),
    computes SHA-256 checksums per file and for the archive, and generates a
    comprehensive inventory manifest for disaster recovery reconciliation.

.PARAMETER StoragePath
    Source storage directory path. Defaults to ./data/storage or $env:STORAGE_PATH.

.PARAMETER BackupDir
    Destination directory for backup archives and manifests. Defaults to ./backups.

.PARAMETER PairedDatabaseManifest
    Optional path to an accompanying database backup manifest to establish a paired snapshot.

.EXAMPLE
    .\backup-storage.ps1 -StoragePath "./data/storage" -BackupDir "./backups"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$StoragePath = $(if ($env:STORAGE_PATH) { $env:STORAGE_PATH } else { "./data/storage" }),

    [Parameter(Mandatory=$false)]
    [string]$BackupDir = "./backups",

    [Parameter(Mandatory=$false)]
    [string]$PairedDatabaseManifest = $null
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -Path $StoragePath)) {
    Write-Warning "Storage directory does not exist at: $StoragePath. Creating directory."
    New-Item -ItemType Directory -Path $StoragePath -Force | Out-Null
}

if (-not (Test-Path -Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$ArchiveFileName = "mmaip_storage_backup_${Timestamp}.zip"
$ArchiveFilePath = Join-Path -Path $BackupDir -ChildPath $ArchiveFileName
$ChecksumFilePath = "${ArchiveFilePath}.sha256"
$ManifestFilePath = "${ArchiveFilePath}.manifest.json"

Write-Host "=========================================================="
Write-Host "  MM AI Platform — Storage Disaster Recovery Backup"
Write-Host "  Timestamp:    $Timestamp"
Write-Host "  Source:       $StoragePath"
Write-Host "  Destination:  $ArchiveFilePath"
Write-Host "=========================================================="

# 1. Enumerate and hash all files in storage
$ResolvedStorage = (Resolve-Path $StoragePath).Path
$Files = Get-ChildItem -Path $ResolvedStorage -Recurse -File

$FileInventory = @()
$TotalBytes = 0

foreach ($f in $Files) {
    $RelativePath = $f.FullName.Substring($ResolvedStorage.Length).TrimStart("\", "/")
    $Hash = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash
    $Size = $f.Length
    $TotalBytes += $Size

    $FileInventory += @{
        relative_path = $RelativePath.Replace("\", "/")
        size_bytes    = $Size
        sha256        = $Hash
    }
}

Write-Host "Found $($Files.Count) files ($TotalBytes bytes) in storage directory."

# 2. Create compressed archive
if ($Files.Count -gt 0) {
    Write-Host "Creating compressed storage archive..."
    Compress-Archive -Path "$ResolvedStorage\*" -DestinationPath $ArchiveFilePath -Force
} else {
    # Create empty zip marker
    Write-Host "Storage directory is empty; creating empty backup archive..."
    $TempEmpty = Join-Path -Path $env:TEMP -ChildPath "empty_marker_$(New-Guid).txt"
    Set-Content -Path $TempEmpty -Value "EMPTY_MMAIP_STORAGE_BACKUP"
    Compress-Archive -Path $TempEmpty -DestinationPath $ArchiveFilePath -Force
    Remove-Item -Path $TempEmpty -Force
}

# 3. Compute SHA-256 for the archive file
$ArchiveHash = (Get-FileHash -Path $ArchiveFilePath -Algorithm SHA256).Hash
Set-Content -Path $ChecksumFilePath -Value "$ArchiveHash *$ArchiveFileName"

$ArchiveSize = (Get-Item $ArchiveFilePath).Length

# 4. Generate manifest linking to paired database backup if provided
$PairedInfo = $null
if ($PairedDatabaseManifest -and (Test-Path $PairedDatabaseManifest)) {
    try {
        $DbManifestContent = Get-Content -Path $PairedDatabaseManifest -Raw | ConvertFrom-Json
        $PairedInfo = @{
            database_manifest = (Resolve-Path $PairedDatabaseManifest).Path
            database_backup   = $DbManifestContent.backup_file
            database_sha256   = $DbManifestContent.sha256
        }
    } catch {
        Write-Warning "Could not parse paired database manifest: $_"
    }
}

$Manifest = @{
    timestamp          = (Get-Date).ToString("o")
    archive_file       = $ArchiveFileName
    archive_size_bytes = $ArchiveSize
    archive_sha256     = $ArchiveHash
    format             = "mmaip_storage_v1"
    total_files        = $Files.Count
    total_bytes        = $TotalBytes
    status             = "COMPLETED"
    paired_database    = $PairedInfo
    files              = $FileInventory
} | ConvertTo-Json -Depth 5

Set-Content -Path $ManifestFilePath -Value $Manifest

Write-Host "Storage backup completed successfully!"
Write-Host "  Archive Size: $ArchiveSize bytes"
Write-Host "  SHA-256:      $ArchiveHash"
Write-Host "  Files Saved:  $($Files.Count)"
Write-Host "  Manifest:     $ManifestFilePath"
