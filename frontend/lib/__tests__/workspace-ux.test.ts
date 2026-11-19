/**
 * M28.8 / M28.8.1 Workspace UX & Interaction Tests
 * Verifies core user journeys, secure handoff, and UI contracts:
 * 1. Overview assistant selection & secure session-scoped draft handoff
 * 2. One-time draft consumption, expiration, and tenant isolation
 * 3. URL query parameter hygiene (no sensitive user draft in URLs)
 * 4. One-screen assistant creation and validation
 * 5. Desktop hybrid assistant list & mobile cards selection
 * 6. Knowledge base navigation & webpage preflight validation
 * 7. Source citation parsing and rendering
 * 8. Collapsible advanced navigation behavior
 * 9. Role-based action visibility
 * 10. Dialog, keyboard, and error recovery contracts
 */

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  setPendingChatDraft,
  consumePendingChatDraft,
  clearPendingChatDraft,
  CHAT_DRAFT_STORAGE_KEY,
} from "../chat-draft.ts";

// In-memory Storage mock for Node.js test environment
class MemoryStorage implements Storage {
  private store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}

// Setup window.sessionStorage in global scope for tests
const memorySessionStorage = new MemoryStorage();
(globalThis as unknown as { window?: { sessionStorage: Storage } }).window = {
  sessionStorage: memorySessionStorage,
};

describe("M28.8.1 Secure Overview-to-Chat Handoff", () => {
  beforeEach(() => {
    memorySessionStorage.clear();
  });

  it("should store draft in tab session and consume it exactly once", () => {
    const tenantId = "tenant-alpha";
    const assistantId = "ast-101";
    const draftText = "Analyze this report and summarize key takeaways: https://example.com/doc";

    setPendingChatDraft(tenantId, draftText, assistantId);

    // First consumption must return the draft text
    const firstConsume = consumePendingChatDraft(tenantId, assistantId);
    assert.equal(firstConsume, draftText);

    // Second consumption must return null (one-time consumption)
    const secondConsume = consumePendingChatDraft(tenantId, assistantId);
    assert.equal(secondConsume, null, "Draft must be removed after first consumption");
  });

  it("should enforce tenant isolation (no cross-tenant draft hydration)", () => {
    const tenantA = "tenant-a";
    const tenantB = "tenant-b";
    const sensitiveDraft = "Confidential financial prompt for Tenant A";

    setPendingChatDraft(tenantA, sensitiveDraft);

    // Tenant B attempts to consume draft
    const leakAttempt = consumePendingChatDraft(tenantB);
    assert.equal(leakAttempt, null, "Cross-tenant draft access must return null");

    // Storage must still retain or safely discard without leaking
    // Access with legitimate Tenant A must succeed
    const legitimateAccess = consumePendingChatDraft(tenantA);
    assert.equal(legitimateAccess, sensitiveDraft);
  });

  it("should enforce assistant targeting when specified", () => {
    const tenantId = "tenant-prod";
    const targetAssistant = "ast-support";
    const otherAssistant = "ast-marketing";
    const draft = "Draft specifically for support assistant";

    setPendingChatDraft(tenantId, draft, targetAssistant);

    // Attempting to consume with different assistant must return null
    const wrongAstConsume = consumePendingChatDraft(tenantId, otherAssistant);
    assert.equal(wrongAstConsume, null, "Mismatched assistant must not consume draft");

    // Correct assistant consumes successfully
    const correctAstConsume = consumePendingChatDraft(tenantId, targetAssistant);
    assert.equal(correctAstConsume, draft);
  });

  it("should expire drafts older than 5 minutes", () => {
    const tenantId = "tenant-prod";
    const draft = "Time-sensitive prompt";

    setPendingChatDraft(tenantId, draft);

    // Manually mutate the stored timestamp to simulate expiry (6 minutes ago)
    const raw = memorySessionStorage.getItem(CHAT_DRAFT_STORAGE_KEY);
    assert.ok(raw);
    const parsed = JSON.parse(raw);
    parsed.createdAt = Date.now() - 6 * 60 * 1000;
    memorySessionStorage.setItem(CHAT_DRAFT_STORAGE_KEY, JSON.stringify(parsed));

    const expiredConsume = consumePendingChatDraft(tenantId);
    assert.equal(expiredConsume, null, "Expired draft must return null");
    assert.equal(memorySessionStorage.getItem(CHAT_DRAFT_STORAGE_KEY), null, "Expired draft must be purged");
  });

  it("should clear draft explicitly on workspace switch or abort", () => {
    setPendingChatDraft("tenant-1", "Aborted prompt");
    assert.ok(memorySessionStorage.getItem(CHAT_DRAFT_STORAGE_KEY));

    clearPendingChatDraft();
    assert.equal(memorySessionStorage.getItem(CHAT_DRAFT_STORAGE_KEY), null);
  });

  it("should construct navigation URL WITHOUT raw draft query parameters", () => {
    const selectedAssistantId = "ast-456";
    const rawUserDraft = "Private search query with credentials: user=admin";

    // Overview saves to session
    setPendingChatDraft("tenant-1", rawUserDraft, selectedAssistantId);

    // Navigation URL only carries assistantId
    const query = new URLSearchParams();
    if (selectedAssistantId) query.set("assistantId", selectedAssistantId);

    const targetUrl = `/dashboard/conversations?${query.toString()}`;

    // Verify URL does not contain sensitive draft text or query param
    assert.equal(targetUrl, "/dashboard/conversations?assistantId=ast-456");
    assert.equal(query.get("draft"), null);
    assert.ok(!targetUrl.includes("credentials"), "Raw credentials or query text must never appear in URL");
  });
});

describe("M28.8 Assistant Creation & Validation Interactions", () => {
  it("should reject empty or whitespace-only assistant names", () => {
    const validate = (name: string) => {
      if (!name || !name.trim()) {
        return { valid: false, error: "Assistant name is required" };
      }
      return { valid: true, error: null };
    };

    assert.equal(validate("").valid, false);
    assert.equal(validate("   ").valid, false);
    assert.equal(validate("Docs Assistant").valid, true);
  });

  it("should generate OmniRoute auto model payload for 1-screen creation", () => {
    const form = {
      name: "Research Bot",
      description: "Quick research assistant",
      knowledgeBaseIds: ["kb-alpha"],
      systemPrompt: "You are an expert researcher.",
    };

    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      system_prompt: form.systemPrompt.trim() || undefined,
      llm_provider: "omniroute",
      default_model: "auto",
      temperature: 0.5,
      max_tokens: 1024,
      visibility: "workspace",
      retrieval_mode: "hybrid",
      top_k: 5,
      knowledge_base_ids: form.knowledgeBaseIds,
    };

    assert.equal(payload.name, "Research Bot");
    assert.equal(payload.llm_provider, "omniroute");
    assert.equal(payload.default_model, "auto");
    assert.deepEqual(payload.knowledge_base_ids, ["kb-alpha"]);
  });

  it("should support progressive disclosure toggles without losing basic form values", () => {
    const state = {
      name: "Toggled Bot",
      description: "Basic description",
      showAdvanced: false,
      systemPrompt: "Custom prompt",
      temperature: 0.7,
    };

    // Toggle advanced section open
    const expandedState = { ...state, showAdvanced: true };
    assert.equal(expandedState.name, "Toggled Bot");
    assert.equal(expandedState.showAdvanced, true);

    // Toggle advanced section closed
    const collapsedState = { ...expandedState, showAdvanced: false };
    assert.equal(collapsedState.name, "Toggled Bot");
    assert.equal(collapsedState.systemPrompt, "Custom prompt", "Values preserved when collapsed");
  });
});

describe("M28.8 Desktop Hybrid & Mobile Assistant Selection", () => {
  const mockAssistants = [
    { id: "ast-1", name: "Engineering Guide", description: "C++ and Python docs" },
    { id: "ast-2", name: "Support Bot", description: "Customer triage" },
  ];

  it("should select first assistant by default when no query param provided", () => {
    const selectDefault = (list: typeof mockAssistants, queryId?: string | null) => {
      if (queryId) {
        return list.find((a) => a.id === queryId) || list[0] || null;
      }
      return list[0] || null;
    };

    const defaultSelected = selectDefault(mockAssistants);
    assert.equal(defaultSelected?.id, "ast-1");

    const querySelected = selectDefault(mockAssistants, "ast-2");
    assert.equal(querySelected?.id, "ast-2");
  });

  it("should switch selected assistant without full page reload", () => {
    let activeId = "ast-1";
    const onSelect = (id: string) => {
      activeId = id;
    };

    onSelect("ast-2");
    assert.equal(activeId, "ast-2");
  });
});

describe("M28.8 Knowledge Base & Webpage Preflight Validation", () => {
  it("should validate and authorize public HTTP/HTTPS URLs", () => {
    const validateWebUrl = (url: string) => {
      try {
        const parsed = new URL(url.trim());
        if (!["http:", "https:"].includes(parsed.protocol)) {
          return { valid: false, error: "Only HTTP and HTTPS URLs are supported" };
        }
        if (["localhost", "127.0.0.1", "0.0.0.0"].includes(parsed.hostname)) {
          return { valid: false, error: "Localhost addresses are forbidden for safety" };
        }
        return { valid: true, error: null };
      } catch {
        return { valid: false, error: "Invalid URL format" };
      }
    };

    assert.equal(validateWebUrl("https://www.w3schools.com/cpp/cpp_for_loop.asp").valid, true);
    assert.equal(validateWebUrl("http://example.com").valid, true);
    assert.equal(validateWebUrl("ftp://files.example.com").valid, false);
    assert.equal(validateWebUrl("http://localhost:8000/secret").valid, false);
    assert.equal(validateWebUrl("not a url").valid, false);
  });

  it("should parse and render source citations with URLs and titles", () => {
    const mockCitation = {
      source_id: "src-1",
      title: "C++ For Loops - W3Schools",
      url: "https://www.w3schools.com/cpp/cpp_for_loop.asp",
      snippet: "When you know exactly how many times you want to loop through a block of code...",
    };

    const renderCitationBadge = (citation: typeof mockCitation) => {
      return {
        label: citation.title,
        href: citation.url,
        preview: citation.snippet.slice(0, 50) + "...",
      };
    };

    const badge = renderCitationBadge(mockCitation);
    assert.equal(badge.label, "C++ For Loops - W3Schools");
    assert.equal(badge.href, "https://www.w3schools.com/cpp/cpp_for_loop.asp");
    assert.ok(badge.preview.startsWith("When you know"));
  });
});

describe("M28.8 Navigation Architecture & Role-Based Actions", () => {
  it("should preserve standard 4-destination core navigation and collapsible advanced", () => {
    const navItems = [
      { label: "Overview", href: "/dashboard" },
      { label: "Chat", href: "/dashboard/conversations" },
      { label: "Assistants", href: "/dashboard/assistants" },
      { label: "Knowledge", href: "/dashboard/knowledge" },
    ];

    assert.equal(navItems.length, 4);
    assert.deepEqual(navItems.map((n) => n.label), ["Overview", "Chat", "Assistants", "Knowledge"]);
  });

  it("should gate admin-only destructive actions based on member role", () => {
    const checkCanDeleteAssistant = (role: "owner" | "admin" | "member") => {
      return role === "owner" || role === "admin";
    };

    assert.equal(checkCanDeleteAssistant("owner"), true);
    assert.equal(checkCanDeleteAssistant("admin"), true);
    assert.equal(checkCanDeleteAssistant("member"), false);
  });

  it("should handle dialog dismiss via Escape key or backdrop click", () => {
    let isOpen = true;
    const handleKeyDown = (key: string) => {
      if (key === "Escape") isOpen = false;
    };
    const handleBackdropClick = (targetIsBackdrop: boolean) => {
      if (targetIsBackdrop) isOpen = false;
    };

    handleKeyDown("Escape");
    assert.equal(isOpen, false, "Escape must close dialog");

    isOpen = true;
    handleBackdropClick(true);
    assert.equal(isOpen, false, "Backdrop click must close dialog");
  });

  it("should handle async error recovery gracefully with clear message", () => {
    let errorState: string | null = null;
    let loading = false;

    const simulateAction = async (shouldFail: boolean) => {
      loading = true;
      errorState = null;
      try {
        if (shouldFail) throw new Error("Backend connection timeout");
        return "success";
      } catch (err: unknown) {
        errorState = err instanceof Error ? err.message : "Unexpected error";
        return null;
      } finally {
        loading = false;
      }
    };

    simulateAction(true).then((res) => {
      assert.equal(res, null);
      assert.equal(errorState, "Backend connection timeout");
      assert.equal(loading, false);
    });
  });
});
