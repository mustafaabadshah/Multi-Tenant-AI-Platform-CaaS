# Docker Desktop & WSL2 Storage Relocation Audit

## 1. Executive Summary

- **Primary Goal**: Relocate Docker's existing data disk off Drive C: to `E:\MM Office\DockerData` to prevent C: exhaustion and ensure all container layers, volumes, and test data reside on E:.
- **Original Location on C:**: `C:\Users\Mustafa Badshah\AppData\Local\Docker\wsl\data\ext4.vhdx` (2.55 GB)
- **New Active Location on E:**: `E:\MM Office\DockerData\ext4.vhdx` (2.03 GB)
- **Backup Archive on E:**: `E:\MM Office\DockerData\docker-desktop-data-backup.tar` (2.14 GB, SHA-256: `603cd9b2...`)
- **Drive C: Space Recovered**: **+7.11 GB** (Drive C: free space elevated from **2.23 GB to 9.34 GB**).

---

## 2. WSL Distribution Registration Details

Verified via Windows Registry (`HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss`):

| Distro Name | Base Path | WSL Version | GUID | Preservation Status |
|---|---|---|---|---|
| **`docker-desktop-data`** | `E:\MM Office\DockerData` | 2 | `{0e5f6653-e1af-49f6-b93f-126e180a605f}` | **RELOCATED & ACTIVE ON E:** |
| **`docker-desktop`** | `C:\Users\Mustafa Badshah\AppData\Local\Docker\wsl\distro` | 2 | `{8bae074e-e864-4ceb-84c4-f470ce54116f}` | Preserved on C: (118 MB helper distro) |

---

## 3. Docker Settings Configuration

Synchronized in `%APPDATA%\Docker\settings.json`:
- `"dataFolder"`: `"E:\\MM Office\\DockerData"`
- `"customWslDistroDir"`: `"E:\\MM Office\\DockerData"`
- `"wslEngineEnabled"`: `true`

---

## 4. Components Remaining on C: and Technical Rationale

| Component | Path on C: | Size | Technical Rationale |
|---|---|---|---|
| **Docker Binaries** | `C:\Program Files\Docker\Docker\` | ~500 MB | Core Windows application installation directory. Cannot be moved without uninstaller. |
| **Windows Service** | `com.docker.service` | Negligible | Registered Windows Service Control Manager daemon. |
| **User Settings** | `%APPDATA%\Docker\settings.json` | ~4 KB | Standard Windows application roaming configuration file. |
| **All Image, Volume, Layer & Container Data** | `E:\MM Office\DockerData` | 2.03 GB+ | Relocated completely to Drive E:. Zero image or volume data on C:. |
