/**
 * Tab-scoped, tenant-isolated, one-time chat draft handoff.
 *
 * Prevents sensitive user prompts from leaking into browser URLs,
 * server access logs, browser history, and referrers.
 */

export interface StoredDraft {
  tenantId: string;
  assistantId?: string;
  text: string;
  createdAt: number;
}

export const CHAT_DRAFT_STORAGE_KEY = "mmaip_chat_draft_handoff";
export const CHAT_DRAFT_EXPIRATION_MS = 5 * 60 * 1000; // 5 minutes TTL

export function setPendingChatDraft(
  tenantId: string,
  text: string,
  assistantId?: string
): void {
  if (typeof window === "undefined" || !window.sessionStorage || !text.trim() || !tenantId) return;
  try {
    const payload: StoredDraft = {
      tenantId,
      assistantId,
      text: text.trim(),
      createdAt: Date.now(),
    };
    window.sessionStorage.setItem(CHAT_DRAFT_STORAGE_KEY, JSON.stringify(payload));
  } catch (err) {
    console.warn("Failed to set chat draft in sessionStorage", err);
  }
}

export function consumePendingChatDraft(
  tenantId: string,
  assistantId?: string | null
): string | null {
  if (typeof window === "undefined" || !window.sessionStorage || !tenantId) return null;
  try {
    const raw = window.sessionStorage.getItem(CHAT_DRAFT_STORAGE_KEY);
    if (!raw) return null;

    const parsed: StoredDraft = JSON.parse(raw);

    // Expired draft must be cleaned up
    if (Date.now() - parsed.createdAt > CHAT_DRAFT_EXPIRATION_MS) {
      window.sessionStorage.removeItem(CHAT_DRAFT_STORAGE_KEY);
      return null;
    }

    // Validate tenant isolation (do not clear if user is simply in a different workspace tab)
    if (parsed.tenantId !== tenantId) {
      return null;
    }

    // If an assistantId is specified on the draft, ensure it matches requested assistant
    if (assistantId && parsed.assistantId && parsed.assistantId !== assistantId) {
      return null;
    }

    // Successfully validated: remove immediately for one-time consumption
    window.sessionStorage.removeItem(CHAT_DRAFT_STORAGE_KEY);
    return parsed.text;
  } catch (err) {
    console.warn("Failed to consume chat draft from sessionStorage", err);
    return null;
  }
}

export function clearPendingChatDraft(): void {
  if (typeof window === "undefined" || !window.sessionStorage) return;
  try {
    window.sessionStorage.removeItem(CHAT_DRAFT_STORAGE_KEY);
  } catch {}
}
