# M25.3 — Live Document Workflow Acceptance

## 1. Test Execution Evidence
Executed against live Render backend (`https://mmaip-backend.onrender.com`) and Neon staging database:
- **Test File**: `policy_sla.txt` (synthetic policy text, 230 bytes)
- **Upload Status**: HTTP 201 Created (`id=b707bae2-0e19-4350-b09d-49a7f6814241`)
- **Extraction & Processing State**: `READY` (chunk count = 1)
- **Listing Verification**: Verified attachment listed in `GET /api/v1/conversations/{conv_id}/attachments`
- **Promotion to Knowledge Base**:
  - Target KB: `53f8a3d8-e1c1-4211-a30e-578df8fac7dc` (`M14 Synthetic KB`)
  - Status: HTTP 200 OK
  - Created Document ID: `493cc3bc-6b7b-4e28-bc09-b9970883411b`
- **Cleanup**: Cleaned up synthetic conversation via `DELETE /api/v1/conversations/{conv_id}` (HTTP 204).
