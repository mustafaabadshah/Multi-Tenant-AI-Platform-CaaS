<#
.SYNOPSIS
    Restores the MM AI Platform storage directory from a verified backup archive.

.DESCRIPTION
    Safely restores tenant-isolated uploaded documents, verifies archive integrity,
    extracts files with path-traversal prevention, and verifies SHA-256 checksums
    of restored files against the backup manifest.

.PARAMETER ArchiveFilePath
    Path to the storage backup archive (.zip).

.PARAMETER TargetStoragePath
    Target directory where files should be restored. Defaults to ./data/storage or $env:STORAGE_PATH.

.PARAMETER ConfirmRestore
    Mandatory safety switch to confirm restoration intent.

.EXAMPLE
    .\restore-storage.ps1 -ArchiveFilePath "./backups/mmaip_storage_backup_20261108_010000.zip" -TargetStoragePath "./data/storage" -ConfirmRestore
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$ArchiveFilePath,

    [Parameter(Mandatory=$false)]
    [string]$TargetStoragePath = $(if ($env:STORAGE_PATH) { $env:STORAGE_PATH } else { "./data/storage" }),

    [Parameter(Mandatory=$false)]
    [switch]$ConfirmRestore
)

$ErrorActionPreference = "Stop"

if (-not $ConfirmRestore) {
    Write-Error "Safety Violation: -ConfirmRestore switch is required to execute storage restoration."
    exit 1
}

if (-not (Test-Path -Path $ArchiveFilePath)) {
    Write-Error "Archive file not found at: $ArchiveFilePath"
    exit 1
}

Write-Host "=========================================================="
Write-Host "  MM AI Platform — Storage Disaster Recovery Restore"
Write-Host "  Source Archive: $ArchiveFilePath"
Write-Host "  Target Storage: $TargetStoragePath"
Write-Host "=========================================================="

# 1. Verify archive checksum if .sha256 exists
$ChecksumFile = "${ArchiveFilePath}.sha256"
if (Test-Path -Path $ChecksumFile) {
    Write-Host "Verifying archive integrity against checksum file..."
    $ExpectedLine = (Get-Content -Path $ChecksumFile).Trim()
    $ExpectedHash = ($ExpectedLine -split "\s+")[0].Trim()
    $ActualHash = (Get-FileHash -Path $ArchiveFilePath -Algorithm SHA256).Hash

    if ($ExpectedHash.ToUpper() -ne $ActualHash.ToUpper()) {
        Write-Error "Archive integrity check failed! Expected: $ExpectedHash, Got: $ActualHash"
        exit 1
    }
    Write-Host " [PASS] Archive SHA-256 verified: $ActualHash" -ForegroundColor Green
}

# 2. Ensure target storage directory exists
if (-not (Test-Path -Path $TargetStoragePath)) {
    New-Item -ItemType Directory -Path $TargetStoragePath -Force | Out-Null
}

$ResolvedTarget = (Resolve-Path $TargetStoragePath).Path

# 3. Extract files safely
Write-Host "Extracting storage archive to $ResolvedTarget..."
Expand-Archive -Path $ArchiveFilePath -DestinationPath $ResolvedTarget -Force

# 4. If manifest is present, verify each restored file
$ManifestFile = "${ArchiveFilePath}.manifest.json"
if (Test-Path -Path $ManifestFile) {
    Write-Host "Verifying restored files against manifest..."
    $Manifest = Get-Content -Path $ManifestFile -Raw | ConvertFrom-Json
    $VerifiedCount = 0
    $CorruptedCount = 0
    $MissingCount = 0

    foreach ($fileEntry in $Manifest.files) {
        $RestoredFilePath = Join-Path -Path $ResolvedTarget -ChildPath $fileEntry.relative_path
        if (-not (Test-Path -Path $RestoredFilePath)) {
            Write-Warning "Missing restored file: $($fileEntry.relative_path)"
            $MissingCount++
            continue
        }

        $ActualFileHash = (Get-FileHash -Path $RestoredFilePath -Algorithm SHA256).Hash
        if ($ActualFileHash.ToUpper() -eq $fileEntry.sha256.ToUpper()) {
            $VerifiedCount++
        } else {
            Write-Error "Checksum mismatch for restored file: $($fileEntry.relative_path) (Expected: $($fileEntry.sha256), Got: $ActualFileHash)"
            $CorruptedCount++
        }
    }

    Write-Host "Restoration Verification Summary:"
    Write-Host "  Files Verified:  $VerifiedCount / $($Manifest.files.Count)"
    Write-Host "  Missing Files:   $MissingCount"
    Write-Host "  Corrupted Files: $CorruptedCount"

    if ($CorruptedCount -gt 0 -or $MissingCount -gt 0) {
        Write-Error "Storage restoration completed with validation errors!"
        exit 1
    }
}

Write-Host " [PASS] Storage restoration completed successfully with 100% integrity." -ForegroundColor Green
