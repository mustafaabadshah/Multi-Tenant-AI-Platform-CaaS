# M25 — Controlled Staging Release Plan

## 1. Prerequisites & Release Baseline
- Local Git Branch: `main`
- Last verified deployed commit: `a0cd98c039c43a5f7e191bdf279c01874a820ce9`
- Current verified Neon database revision: `0016_m20_2_assistant_tools_config`
- Target additive revision: `0017_m22_conversation_attachments`
- Target staging databases:
  - Neon Project: `aged-heart-01771250`
  - Neon Branch: `br-tiny-wind-arvfyx75`
  - Neon DB: `mmaip_staging`
  - Render Services: `mmaip-backend` (`srv-dbrk57gn74is73fqo4k0`), `mmaip-frontend` (`srv-dbrkthcipgvc739d6oh0`)

## 2. Release Steps (Requiring Explicit Operator Authorization)
1. **Pre-Flight Snapshot**:
   Create a point-in-time branch or snapshot of Neon database `mmaip_staging`.
2. **Apply Additive Migration**:
   Run Alembic migration `0017_m22_conversation_attachments` using migration-capable role `mmaip_user`.
3. **Apply Runtime Table Grants**:
   Grant `SELECT, INSERT, UPDATE, DELETE` on `conversation_attachments`, `conversation_attachment_chunks`, and `user_voice_preferences` to restricted runtime role `mmaip_app`.
4. **Git Commit & Push**:
   Commit local changes with clean allowlist and push to `origin main`.
5. **Render Backend Deploy**:
   Trigger deployment for `mmaip-backend` and verify healthy status.
6. **Render Frontend Deploy**:
   Trigger deployment for `mmaip-frontend` and verify production build.
7. **Post-Deploy Smoke Test**:
   Execute synthetic attachment upload and voice interaction acceptance.

## 3. Rollback Plan
- The database migration `0017` is strictly additive (creates new tables only). The deployed legacy application (`a0cd98c`) remains 100% functional even if migration `0017` is applied before code deployment.
- If backend deployment fails, rollback Render deployment to `a0cd98c039c43a5f7e191bdf279c01874a820ce9` with zero data loss.
