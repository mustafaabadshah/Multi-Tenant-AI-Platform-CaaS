# M28.4 Release & Deployment Plan

## 1. Release Architecture & Safety Contract

- **Release Tag:** `v28.4.0`
- **Release Target:** Multi-Tenant AI Platform (CaaS)
- **Safety Directive:** All modifications are verified locally and staged in the local working tree. No remote Git push, Neon database alteration, or Render deployment may occur without fresh explicit operator authorization.

## 2. Infrastructure Inventory & Checkpoint

| Component | Identifier / URL | Status / Checkpoint |
| :--- | :--- | :--- |
| **Git Local Workspace** | `E:\MM Office\Multi-Tanant-CaaS` | Clean working tree; tests green |
| **Git Remote Origin** | `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS` | HEAD: `822f238263c8029fd3b1e349a48b0a7c97fbf83d` |
| **Neon PostgreSQL Database** | `aged-heart-01771250` / `mmaip_staging` | Branch: `br-tiny-wind-arvfyx75` (Revision `0018_m28_message_feedback`) |
| **Neon Safety Checkpoint** | `pre-m28-quality-release-20261118` | Branch: `br-snowy-pine-ar3d40qx` |
| **Render Backend Service** | `srv-dbrk57gn74is73fqo4k0` | `https://mmaip-backend.onrender.com` |
| **Render Frontend Service** | `srv-dbrkthcipgvc739d6oh0` | `https://mmaip-frontend.onrender.com` |

## 3. Deployment Procedure (Awaiting Operator Approval)

When explicit operator authorization is granted:
1. **Commit & Push:**
   - Commit working tree changes with message `feat(m28.4): universal web reader, selective OCR, and KB import`.
   - Push commit to GitHub `origin/main`.
2. **Database Verification:**
   - Confirm current Neon revision matches `0018_m28_message_feedback`. (No new database migrations required for M28.4 as existing `Document` and `DocumentChunk` schemas already support all required JSON metadata).
3. **Render Automatic Build & Deployment:**
   - Monitor Render Backend deployment `srv-dbrk57gn74is73fqo4k0`.
   - Monitor Render Frontend deployment `srv-dbrkthcipgvc739d6oh0`.
4. **Post-Deployment Smoke Verification:**
   - Execute live health probe `GET /health` and `GET /api/v1/auth/me`.
   - Perform live web fetch and multi-mode save verification in staging.
