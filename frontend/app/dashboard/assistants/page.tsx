"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  AssistantItem,
  KnowledgeBaseItem,
} from "@/lib/api";
import AssistantCreationWizard from "./AssistantCreationWizard";
import AssistantWorkspaceView from "./AssistantWorkspaceView";
import {
  Bot,
  Plus,
  Search,
  Sliders,
  MessageSquare,
  ArrowRight,
  ChevronRight,
  Database,
  Layers,
  Sparkles,
  ChevronLeft,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";

function AssistantsContent() {
  const { activeWorkspace } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [assistants, setAssistants] = useState<AssistantItem[]>([]);
  const [activeAssistant, setActiveAssistant] = useState<AssistantItem | null>(null);
  const [tenantKBs, setTenantKBs] = useState<KnowledgeBaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [showWizard, setShowWizard] = useState(false);

  // Check URL query parameters
  const queryCreate = searchParams?.get("create");
  const queryAssistantId = searchParams?.get("assistantId");

  useEffect(() => {
    if (queryCreate === "true") {
      setShowWizard(true);
    }
  }, [queryCreate]);

  // Initial Data Load
  useEffect(() => {
    async function loadData() {
      if (!activeWorkspace) return;
      setLoading(true);
      try {
        const [assts, kbs] = await Promise.all([
          api.listAssistants(),
          api.listKnowledgeBases().catch(() => []),
        ]);
        setAssistants(assts);
        setTenantKBs(kbs);

        if (queryAssistantId) {
          const match = assts.find((a) => a.id === queryAssistantId);
          if (match) {
            setActiveAssistant(match);
          } else if (assts.length > 0) {
            setActiveAssistant(assts[0]);
          }
        } else if (assts.length > 0) {
          // Default to first assistant on desktop
          setActiveAssistant(assts[0]);
        }
      } catch (err) {
        console.error("Failed to load assistants", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [activeWorkspace, queryAssistantId]);

  // Filtered Assistants
  const filteredAssistants = useMemo(() => {
    if (!searchQuery.trim()) return assistants;
    const q = searchQuery.toLowerCase();
    return assistants.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        (a.description && a.description.toLowerCase().includes(q))
    );
  }, [assistants, searchQuery]);

  const handleStartChat = (assistant: AssistantItem) => {
    router.push(`/dashboard/conversations?assistantId=${assistant.id}`);
  };

  const handleAssistantUpdated = (updated: AssistantItem) => {
    setAssistants((prev) =>
      prev.map((a) => (a.id === updated.id ? updated : a))
    );
    setActiveAssistant(updated);
  };

  const handleAssistantDeleted = (deletedId: string) => {
    setAssistants((prev) => prev.filter((a) => a.id !== deletedId));
    if (activeAssistant?.id === deletedId) {
      const remaining = assistants.filter((a) => a.id !== deletedId);
      setActiveAssistant(remaining.length > 0 ? remaining[0] : null);
    }
  };

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-200 pb-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 tracking-tight">
            AI Assistants
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Configure specialized AI personas, tool policies, instructions, and connected knowledge.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            icon={Plus}
            onClick={() => setShowWizard(true)}
          >
            Create Assistant
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="p-12 text-center bg-white rounded-xl border border-gray-200">
          <Spinner size="md" />
          <p className="text-xs text-gray-500 mt-2">Loading assistants...</p>
        </div>
      ) : assistants.length === 0 ? (
        /* Empty State */
        <div className="p-12 rounded-2xl bg-white border border-dashed border-gray-300 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto border border-blue-100">
            <Bot size={24} />
          </div>
          <h3 className="text-sm font-semibold text-gray-900">No Assistants Yet</h3>
          <p className="text-xs text-gray-500 max-w-sm mx-auto">
            Create your first assistant to begin chatting, searching internal documents, or querying web pages.
          </p>
          <Button
            variant="primary"
            size="sm"
            icon={Plus}
            onClick={() => setShowWizard(true)}
          >
            Create Your First Assistant
          </Button>
        </div>
      ) : (
        /* Responsive Hybrid Layout: List & Detail Pane */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 min-h-[calc(100vh-180px)]">
          {/* Assistant List Pane (Desktop col-4, Mobile full if no active assistant selected) */}
          <div
            className={`lg:col-span-4 space-y-3 ${
              activeAssistant ? "hidden lg:block" : "block"
            }`}
          >
            {/* Search Input */}
            <div className="relative">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search assistants..."
                className="w-full pl-9 pr-3 py-2 text-xs bg-white border border-gray-200 rounded-xl text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* List of Assistants */}
            <div className="space-y-2 overflow-y-auto max-h-[calc(100vh-250px)] pr-1">
              {filteredAssistants.map((a) => {
                const isSelected = activeAssistant?.id === a.id;
                return (
                  <div
                    key={a.id}
                    onClick={() => setActiveAssistant(a)}
                    className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer group ${
                      isSelected
                        ? "bg-blue-50/60 border-blue-400 shadow-xs ring-1 ring-blue-400/20"
                        : "bg-white border-gray-200 hover:border-gray-300 hover:shadow-xs"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 pr-1">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`font-semibold text-xs truncate ${
                              isSelected ? "text-blue-900" : "text-gray-900"
                            }`}
                          >
                            {a.name}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-gray-100 text-gray-600 font-mono">
                            {a.llm_provider || "omniroute"}
                          </span>
                        </div>
                        <p className="text-[11px] text-gray-500 line-clamp-2 mt-1">
                          {a.description || "Grounded assistant for your workspace."}
                        </p>
                      </div>
                      <ChevronRight
                        size={14}
                        className={`text-gray-400 shrink-0 transition-transform ${
                          isSelected ? "text-blue-600 translate-x-0.5" : "group-hover:translate-x-0.5"
                        }`}
                      />
                    </div>

                    <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100 text-[10px] text-gray-500">
                      <div className="flex items-center gap-1">
                        <Database size={11} className="text-gray-400" />
                        <span>{a.connected_kb_ids?.length || 0} KBs</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartChat(a);
                          }}
                          className="px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white font-medium text-[10px] flex items-center gap-1 transition-colors"
                        >
                          <MessageSquare size={10} />
                          <span>Chat</span>
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Assistant Detail Viewport (Desktop col-8) */}
          <div
            className={`lg:col-span-8 bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-xs flex flex-col ${
              !activeAssistant ? "hidden lg:flex items-center justify-center p-8 text-gray-400" : "block"
            }`}
          >
            {activeAssistant ? (
              <div className="h-full flex flex-col">
                {/* Mobile Back button */}
                <div className="lg:hidden p-3 border-b border-gray-100 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setActiveAssistant(null)}
                    className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 flex items-center gap-1 text-xs font-medium"
                  >
                    <ChevronLeft size={16} />
                    <span>Back to all assistants</span>
                  </button>
                </div>

                <AssistantWorkspaceView
                  assistant={activeAssistant}
                  tenantKBs={tenantKBs}
                  onUpdate={handleAssistantUpdated}
                  onDelete={handleAssistantDeleted}
                  onStartChat={handleStartChat}
                />
              </div>
            ) : (
              <div className="text-center p-8">
                <Bot size={28} className="mx-auto mb-2 text-gray-300" />
                <p className="text-xs text-gray-500">Select an assistant to view or configure its details.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Creation Wizard Modal */}
      <AssistantCreationWizard
        isOpen={showWizard}
        onClose={() => setShowWizard(false)}
        onSuccess={(newAsst) => {
          setAssistants((prev) => [newAsst, ...prev]);
          setActiveAssistant(newAsst);
          setShowWizard(false);
        }}
        onStartChat={handleStartChat}
        tenantKBs={tenantKBs}
      />
    </div>
  );
}

export default function AssistantsChatPage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-gray-50">
          <Spinner size="lg" />
        </div>
      }
    >
      <AssistantsContent />
    </React.Suspense>
  );
}
