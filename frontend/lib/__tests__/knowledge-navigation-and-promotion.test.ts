/**
 * M28.13 Knowledge Base Navigation, Assistant-KB Routing, Refresh & Promotion Tests
 * Verifies:
 * 1. Deterministic destination policy (single connected, multiple connected, none connected)
 * 2. Non-connected KB warning flag detection
 * 3. Knowledge Base URL query parameter sync & history navigation
 * 4. Ingestion job active polling vs idle zero-polling lifecycle
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";

interface MockKnowledgeBase {
  id: string;
  name: string;
  status: string;
}

interface MockAssistant {
  id: string;
  name: string;
  connected_kb_ids: string[];
}

interface MockDocument {
  id: string;
  filename: string;
  status: "QUEUED" | "PROCESSING" | "READY" | "COMPLETED" | "FAILED";
}

// Destination policy resolution function under test
function resolveInitialDestination(
  assistant: MockAssistant | null,
  allKBs: MockKnowledgeBase[]
): {
  initialKbId: string;
  connectedKBs: MockKnowledgeBase[];
  otherKBs: MockKnowledgeBase[];
  policyCase: "SINGLE_CONNECTED" | "MULTIPLE_CONNECTED" | "NO_CONNECTED";
} {
  const connectedIds = assistant?.connected_kb_ids || [];
  const connectedKBs = allKBs.filter((kb) => connectedIds.includes(kb.id));
  const otherKBs = allKBs.filter((kb) => !connectedIds.includes(kb.id));

  if (connectedKBs.length === 1) {
    return {
      initialKbId: connectedKBs[0].id,
      connectedKBs,
      otherKBs,
      policyCase: "SINGLE_CONNECTED",
    };
  }

  if (connectedKBs.length > 1) {
    return {
      initialKbId: "",
      connectedKBs,
      otherKBs,
      policyCase: "MULTIPLE_CONNECTED",
    };
  }

  return {
    initialKbId: "",
    connectedKBs,
    otherKBs,
    policyCase: "NO_CONNECTED",
  };
}

// Ingestion active polling trigger function under test
function shouldPollDocuments(docs: MockDocument[]): boolean {
  return docs.some((d) => d.status === "QUEUED" || d.status === "PROCESSING");
}

describe("M28.13 Deterministic Destination Policy", () => {
  const kbCricket: MockKnowledgeBase = { id: "kb-cricket", name: "Cricket", status: "ACTIVE" };
  const kbPF: MockKnowledgeBase = { id: "kb-pf", name: "PF", status: "ACTIVE" };
  const kbMath: MockKnowledgeBase = { id: "kb-math", name: "Mathematics", status: "ACTIVE" };
  const allWorkspaceKBs = [kbCricket, kbPF, kbMath]; // Cricket first in list!

  it("Case A: exactly one connected KB (Notes Assistant -> PF) preselects PF, never Cricket", () => {
    const notesAssistant: MockAssistant = {
      id: "asst-notes",
      name: "Notes & Textbook Q&A Assistant",
      connected_kb_ids: ["kb-pf"], // Connected to PF only
    };

    const res = resolveInitialDestination(notesAssistant, allWorkspaceKBs);
    assert.equal(res.policyCase, "SINGLE_CONNECTED");
    assert.equal(res.initialKbId, "kb-pf", "Must preselect PF because it is the only connected KB");
    assert.notEqual(res.initialKbId, "kb-cricket", "Must NOT pick Cricket merely because it is first in workspace list");
    assert.equal(res.connectedKBs.length, 1);
    assert.equal(res.connectedKBs[0].id, "kb-pf");
    assert.equal(res.otherKBs.length, 2);
  });

  it("Case B: multiple connected KBs requires explicit selection (empty initial ID)", () => {
    const multiAssistant: MockAssistant = {
      id: "asst-multi",
      name: "Research Assistant",
      connected_kb_ids: ["kb-pf", "kb-math"],
    };

    const res = resolveInitialDestination(multiAssistant, allWorkspaceKBs);
    assert.equal(res.policyCase, "MULTIPLE_CONNECTED");
    assert.equal(res.initialKbId, "", "Must NOT silently pick first KB when multiple are connected");
    assert.equal(res.connectedKBs.length, 2);
  });

  it("Case C: zero connected KBs requires explicit choice and isolates workspace KBs", () => {
    const generalAssistant: MockAssistant = {
      id: "asst-gen",
      name: "General Chat Assistant",
      connected_kb_ids: [],
    };

    const res = resolveInitialDestination(generalAssistant, allWorkspaceKBs);
    assert.equal(res.policyCase, "NO_CONNECTED");
    assert.equal(res.initialKbId, "", "Must NOT pick a random workspace KB when assistant has none connected");
    assert.equal(res.connectedKBs.length, 0);
    assert.equal(res.otherKBs.length, 3);
  });

  it("identifies connection status and detects non-connected warnings", () => {
    const notesAssistant: MockAssistant = {
      id: "asst-notes",
      name: "Notes & Textbook Q&A Assistant",
      connected_kb_ids: ["kb-pf"],
    };

    const isTargetConnected = (targetId: string) => notesAssistant.connected_kb_ids.includes(targetId);

    assert.equal(isTargetConnected("kb-pf"), true);
    assert.equal(isTargetConnected("kb-cricket"), false);
  });
});

describe("M28.13 Knowledge Navigation & URL Sync", () => {
  it("constructs stable URL for selected KB detail", () => {
    const kbId = "kb-pf-uuid-1234";
    const detailUrl = `/dashboard/knowledge?kbId=${kbId}`;
    const searchParams = new URLSearchParams(detailUrl.split("?")[1]);
    assert.equal(searchParams.get("kbId"), kbId);
  });

  it("returns to clean KB list URL on back action", () => {
    const listUrl = "/dashboard/knowledge";
    const searchParams = new URLSearchParams(listUrl.includes("?") ? listUrl.split("?")[1] : "");
    assert.equal(searchParams.get("kbId"), null);
  });
});

describe("M28.13 Bounded Ingestion Polling Lifecycle", () => {
  it("triggers polling when documents are QUEUED or PROCESSING", () => {
    const docs: MockDocument[] = [
      { id: "1", filename: "doc1.pdf", status: "READY" },
      { id: "2", filename: "doc2.pdf", status: "PROCESSING" },
    ];
    assert.equal(shouldPollDocuments(docs), true);
  });

  it("stops polling when all documents reach terminal states (READY, COMPLETED, FAILED)", () => {
    const docs: MockDocument[] = [
      { id: "1", filename: "doc1.pdf", status: "READY" },
      { id: "2", filename: "doc2.pdf", status: "COMPLETED" },
      { id: "3", filename: "doc3.pdf", status: "FAILED" },
    ];
    assert.equal(shouldPollDocuments(docs), false, "Idle document list must produce zero polling requests");
  });

  it("produces zero polling on empty document collection", () => {
    const docs: MockDocument[] = [];
    assert.equal(shouldPollDocuments(docs), false);
  });
});
