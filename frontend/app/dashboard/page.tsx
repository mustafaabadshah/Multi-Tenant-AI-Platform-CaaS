"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  AssistantItem,
  ConversationItem,
  KnowledgeBaseItem,
  AuditLogItem,
} from "@/lib/api";
import {
  Bot,
  Database,
  History,
  ArrowRight,
  Plus,
  MessageSquare,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Send,
  Layers,
  FileText,
  Clock,
  ShieldCheck,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";
import { setPendingChatDraft } from "@/lib/chat-draft";

export default function DashboardOverviewPage() {
  const { user, activeWorkspace } = useAuth();
  const router = useRouter();

  const [assistants, setAssistants] = useState<AssistantItem[]>([]);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseItem[]>([]);
  const [recentAudit, setRecentAudit] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Quick Start Composer state
  const [selectedAssistantId, setSelectedAssistantId] = useState<string>("");
  const [draftPrompt, setDraftPrompt] = useState<string>("");

  useEffect(() => {
    async function loadWorkspaceData() {
      if (!activeWorkspace) return;
      setLoading(true);
      try {
        const [assistantsRes, knowledgeRes, conversationsRes, auditRes] =
          await Promise.allSettled([
            api.listAssistants(),
            api.listKnowledgeBases(),
            api.listConversations(),
            api.listAuditLogs(),
          ]);

        if (assistantsRes.status === "fulfilled") {
          const list = assistantsRes.value;
          setAssistants(list);
          if (list.length > 0) {
            setSelectedAssistantId(list[0].id);
          }
        }
        if (knowledgeRes.status === "fulfilled") {
          setKnowledgeBases(knowledgeRes.value);
        }
        if (conversationsRes.status === "fulfilled") {
          setConversations(conversationsRes.value);
        }
        if (auditRes.status === "fulfilled") {
          setRecentAudit(auditRes.value.slice(0, 5));
        }
      } catch (err) {
        console.error("Error loading dashboard data", err);
      } finally {
        setLoading(false);
      }
    }

    loadWorkspaceData();
  }, [activeWorkspace]);

  const handleStartChatFromComposer = (e: React.FormEvent) => {
    e.preventDefault();
    if (draftPrompt.trim() && activeWorkspace?.tenant_id) {
      setPendingChatDraft(activeWorkspace.tenant_id, draftPrompt.trim(), selectedAssistantId);
    }
    const query = new URLSearchParams();
    if (selectedAssistantId) {
      query.set("assistantId", selectedAssistantId);
    }
    const qs = query.toString();
    router.push(`/dashboard/conversations${qs ? `?${qs}` : ""}`);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Workspace Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 tracking-tight">
            {activeWorkspace?.tenant_name || "Workspace Overview"}
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Grounded AI workspace · Multi-tenant isolated · Staging
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/dashboard/conversations">
            <Button variant="primary" size="sm" icon={MessageSquare}>
              Open Chat
            </Button>
          </Link>
          <Link href="/dashboard/knowledge">
            <Button variant="secondary" size="sm" icon={Database}>
              Add Knowledge
            </Button>
          </Link>
        </div>
      </div>

      {/* Main Task-Oriented Start Area */}
      {loading ? (
        <div className="p-12 text-center bg-white rounded-xl border border-gray-200">
          <Spinner size="md" />
          <p className="text-xs text-gray-500 mt-2">Loading workspace...</p>
        </div>
      ) : assistants.length === 0 ? (
        /* Empty Assistants: First-time Onboarding */
        <div className="p-8 rounded-2xl bg-gradient-to-br from-blue-50/60 via-white to-gray-50 border border-blue-200/80 shadow-xs text-center sm:text-left flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">
              <Sparkles size={12} />
              <span>Step 1: Create an Assistant</span>
            </div>
            <h2 className="text-base font-semibold text-gray-900">
              Set up your first AI Assistant
            </h2>
            <p className="text-xs text-gray-600 leading-relaxed">
              Build an AI assistant grounded in your documents, connected to knowledge bases, or able to read public web pages in real time.
            </p>
          </div>
          <Link href="/dashboard/assistants?create=true">
            <Button variant="primary" size="md" icon={Plus}>
              Create Assistant
            </Button>
          </Link>
        </div>
      ) : (
        /* Returning / Active User: One-Click Prompt Composer */
        <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-blue-50 text-blue-600 flex items-center justify-center">
                <Bot size={14} />
              </div>
              <span className="text-xs font-semibold text-gray-900">
                Start a Conversation
              </span>
            </div>

            {/* Assistant Selector */}
            <div className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="text-[11px] text-gray-400">Assistant:</span>
              <select
                value={selectedAssistantId}
                onChange={(e) => setSelectedAssistantId(e.target.value)}
                className="text-xs bg-gray-50 border border-gray-200 rounded-lg px-2 py-1 text-gray-800 font-medium outline-none focus:border-blue-500"
              >
                {assistants.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <form onSubmit={handleStartChatFromComposer} className="space-y-3">
            <textarea
              rows={2}
              value={draftPrompt}
              onChange={(e) => setDraftPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleStartChatFromComposer(e);
                }
              }}
              placeholder={`Ask ${assistants.find((a) => a.id === selectedAssistantId)?.name || "Assistant"} a question, paste a webpage link, or outline what you need...`}
              className="w-full resize-none p-3 text-xs bg-gray-50/70 border border-gray-200 rounded-xl text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-500 focus:bg-white focus:ring-1 focus:ring-blue-500"
            />

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              {/* Quick suggestion chips */}
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <button
                  type="button"
                  onClick={() =>
                    setDraftPrompt("Please read this webpage and explain the key points: ")
                  }
                  className="px-2 py-0.5 rounded-md bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors"
                >
                  🌐 Read webpage
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setDraftPrompt("Summarize key findings from our connected knowledge base.")
                  }
                  className="px-2 py-0.5 rounded-md bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors"
                >
                  📚 Search knowledge
                </button>
              </div>

              <div className="flex items-center gap-2 justify-end">
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  icon={Send}
                >
                  Start Chat
                </Button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* Two Column Grid: Continue Working & Active Assistants */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Recent Conversations */}
        <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <MessageSquare size={16} className="text-gray-500" />
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">
                  Recent Conversations
                </h3>
              </div>
              <Link
                href="/dashboard/conversations"
                className="text-[11px] text-blue-600 hover:underline font-medium"
              >
                View all &rarr;
              </Link>
            </div>

            {conversations.length === 0 ? (
              <div className="py-8 text-center text-gray-400 text-xs">
                No conversations yet. Type above to start your first chat.
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {conversations.slice(0, 4).map((c) => {
                  const asst = assistants.find((a) => a.id === c.assistant_id);
                  return (
                    <Link
                      key={c.id}
                      href={`/dashboard/conversations?conversationId=${c.id}`}
                      className="py-2.5 flex items-center justify-between hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors group"
                    >
                      <div className="min-w-0 pr-2">
                        <span className="text-xs font-medium text-gray-800 truncate block group-hover:text-blue-600 transition-colors">
                          {c.title}
                        </span>
                        <span className="text-[10px] text-gray-400 block">
                          {asst ? asst.name : "Assistant"} · {new Date(c.updated_at || c.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <ChevronRight
                        size={14}
                        className="text-gray-400 group-hover:translate-x-0.5 transition-transform shrink-0"
                      />
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Your Assistants */}
        <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Bot size={16} className="text-gray-500" />
                <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">
                  Configured Assistants
                </h3>
              </div>
              <Link
                href="/dashboard/assistants"
                className="text-[11px] text-blue-600 hover:underline font-medium"
              >
                Manage &rarr;
              </Link>
            </div>

            {assistants.length === 0 ? (
              <div className="py-8 text-center text-gray-400 text-xs">
                No assistants configured.
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {assistants.slice(0, 4).map((a) => (
                  <div
                    key={a.id}
                    className="py-2.5 flex items-center justify-between hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors"
                  >
                    <div className="min-w-0 pr-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-medium text-gray-900 truncate">
                          {a.name}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-gray-100 text-gray-600 font-mono">
                          {a.llm_provider || "omniroute"}
                        </span>
                      </div>
                      <span className="text-[10px] text-gray-400 truncate block mt-0.5">
                        {a.description || "Grounded assistant"} · {a.connected_kb_ids?.length || 0} KBs
                      </span>
                    </div>

                    <Link href={`/dashboard/conversations?assistantId=${a.id}`}>
                      <Button variant="secondary" size="xs">
                        Chat
                      </Button>
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Knowledge Bases & Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Knowledge Bases Card */}
        <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Database size={16} className="text-gray-500" />
              <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">
                Connected Knowledge
              </h3>
            </div>
            <Link
              href="/dashboard/knowledge"
              className="text-[11px] text-blue-600 hover:underline font-medium"
            >
              Add Knowledge &rarr;
            </Link>
          </div>

          {knowledgeBases.length === 0 ? (
            <div className="py-6 text-center text-gray-400 text-xs">
              No knowledge bases found. Upload documents to ground your assistants.
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {knowledgeBases.slice(0, 3).map((kb) => (
                <div
                  key={kb.id}
                  className="py-2 flex items-center justify-between text-xs"
                >
                  <div className="min-w-0 pr-2">
                    <span className="font-medium text-gray-800 block truncate">
                      {kb.name}
                    </span>
                    <span className="text-[10px] text-gray-400 font-mono">
                      {kb.document_count ?? 0} documents · {kb.status || "READY"}
                    </span>
                  </div>
                  <Link href="/dashboard/knowledge">
                    <Button variant="ghost" size="xs">
                      View
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity Audit */}
        <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <History size={16} className="text-gray-500" />
              <h3 className="text-xs font-semibold text-gray-900 uppercase tracking-wider">
                Recent Activity
              </h3>
            </div>
            <Link
              href="/dashboard/audit"
              className="text-[11px] text-blue-600 hover:underline font-medium"
            >
              Audit Trail &rarr;
            </Link>
          </div>

          {recentAudit.length === 0 ? (
            <div className="py-6 text-center text-gray-400 text-xs">
              No recent activity recorded.
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {recentAudit.slice(0, 3).map((log) => (
                <div key={log.id} className="py-2 flex items-center justify-between text-xs">
                  <div className="min-w-0 pr-2">
                    <span className="font-mono text-blue-600 font-medium block truncate text-[11px]">
                      {log.action}
                    </span>
                    <span className="text-[10px] text-gray-400 block truncate">
                      {log.resource_type} by {log.actor_name || "System"}
                    </span>
                  </div>
                  <span className="text-[10px] text-gray-400 font-mono shrink-0">
                    {new Date(log.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Platform Status & Non-Sensitive Release Identity */}
      <div className="p-3.5 rounded-xl bg-gray-50 border border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-gray-500">
        <div className="flex items-center gap-2.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span className="font-medium text-gray-800">
            Multi-Tenant AI Platform (CaaS) · Release M28.8
          </span>
          <span className="text-gray-300">|</span>
          <span className="text-gray-500">Unified AI Workspace</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono text-gray-400">
          <span>Staging</span>
          <span>Zero-Trust Scoped</span>
        </div>
      </div>
    </div>
  );
}
