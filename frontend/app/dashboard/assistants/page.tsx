"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  AssistantItem,
  ConversationItem,
  KnowledgeBaseItem,
  MessageCitationItem,
  MessageItem,
} from "@/lib/api";
import AssistantCreationWizard from "./AssistantCreationWizard";
import AssistantWorkspaceView from "./AssistantWorkspaceView";
import {
  Bot,
  Plus,
  Send,
  Square,
  Sparkles,
  Settings2,
  Trash2,
  FileText,
  BookOpen,
  MessageSquare,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  X,
  Eye,
  Layers,
  Hash,
  Search,
  Sliders,
  ShieldCheck,
  Tag,
} from "lucide-react";

export default function AssistantsChatPage() {
  const { activeWorkspace } = useAuth();

  // State: Assistants
  const [assistants, setAssistants] = useState<AssistantItem[]>([]);
  const [activeAssistant, setActiveAssistant] = useState<AssistantItem | null>(null);
  const [tenantKBs, setTenantKBs] = useState<KnowledgeBaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // Mode: "workspace" = Studio settings & version history; "chat" = live conversation drawer
  const [viewMode, setViewMode] = useState<"workspace" | "chat">("workspace");

  // Wizard State
  const [showWizard, setShowWizard] = useState(false);

  // State: Conversations & Chat
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConversation, setActiveConversation] = useState<ConversationItem | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<MessageCitationItem | null>(null);
  const [citationTab, setCitationTab] = useState<"visual" | "text">("visual");
  const [copiedCitationText, setCopiedCitationText] = useState(false);
  const [copiedCitationTag, setCopiedCitationTag] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Filtered Assistants List
  const filteredAssistants = useMemo(() => {
    if (!searchQuery.trim()) return assistants;
    const q = searchQuery.toLowerCase();
    return assistants.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        (a.description && a.description.toLowerCase().includes(q)) ||
        (a.template_id && a.template_id.toLowerCase().includes(q))
    );
  }, [assistants, searchQuery]);

  const activeMessageCitations = useMemo(() => {
    if (!activeCitation) return [];
    const containingMsg = messages.find((m) =>
      m.citations?.some(
        (c) => c.citation_num === activeCitation.citation_num || (c.id && c.id === activeCitation.id)
      )
    );
    return containingMsg?.citations || [activeCitation];
  }, [activeCitation, messages]);

  const currentCitationIdx = activeMessageCitations.findIndex(
    (c) => c.citation_num === activeCitation?.citation_num
  );

  const handleNextCitation = () => {
    if (activeMessageCitations.length <= 1 || currentCitationIdx === -1) return;
    const nextIdx = (currentCitationIdx + 1) % activeMessageCitations.length;
    setActiveCitation(activeMessageCitations[nextIdx]);
    setCopiedCitationText(false);
    setCopiedCitationTag(false);
  };

  const handlePrevCitation = () => {
    if (activeMessageCitations.length <= 1 || currentCitationIdx === -1) return;
    const prevIdx =
      (currentCitationIdx - 1 + activeMessageCitations.length) % activeMessageCitations.length;
    setActiveCitation(activeMessageCitations[prevIdx]);
    setCopiedCitationText(false);
    setCopiedCitationTag(false);
  };

  // 1. Initial Load: Assistants & Tenant KBs
  const loadInitialData = async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    try {
      const [asstList, kbList] = await Promise.all([
        api.listAssistants(),
        api.listKnowledgeBases(),
      ]);
      setAssistants(asstList);
      setTenantKBs(kbList);

      if (asstList.length > 0 && !activeAssistant) {
        setActiveAssistant(asstList[0]);
      }
    } catch (err) {
      console.error("Failed to load initial data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, [activeWorkspace]);

  // 2. Load Conversations when activeAssistant changes
  useEffect(() => {
    if (!activeAssistant) {
      setConversations([]);
      setActiveConversation(null);
      setMessages([]);
      return;
    }
    const fetchConversations = async () => {
      try {
        const convList = await api.listConversations(activeAssistant.id);
        setConversations(convList);
        if (convList.length > 0) {
          setActiveConversation(convList[0]);
        } else {
          setActiveConversation(null);
          setMessages([]);
        }
      } catch (err) {
        console.error("Failed to fetch conversations", err);
      }
    };
    fetchConversations();
  }, [activeAssistant]);

  // 3. Load Messages when activeConversation changes
  useEffect(() => {
    if (!activeConversation) {
      setMessages([]);
      return;
    }
    const fetchMessages = async () => {
      try {
        const msgList = await api.listMessages(activeConversation.id);
        setMessages(msgList);
      } catch (err) {
        console.error("Failed to load messages", err);
      }
    };
    fetchMessages();
  }, [activeConversation]);

  // Auto scroll to bottom
  useEffect(() => {
    if (viewMode === "chat") {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streaming, viewMode]);

  // 4. Create New Conversation
  const handleNewConversation = async () => {
    if (!activeAssistant) return;
    try {
      const newConv = await api.createConversation({
        assistant_id: activeAssistant.id,
        title: "New Conversation",
      });
      setConversations((prev) => [newConv, ...prev]);
      setActiveConversation(newConv);
      setMessages([]);
      setViewMode("chat");
    } catch (err) {
      console.error("Failed to create conversation", err);
    }
  };

  // 5. Send Message & Stream Response
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const content = inputMessage.trim();
    if (!content || !activeAssistant || streaming) return;

    let conv = activeConversation;
    if (!conv) {
      try {
        conv = await api.createConversation({
          assistant_id: activeAssistant.id,
          title: content.slice(0, 30) + (content.length > 30 ? "..." : ""),
        });
        setConversations((prev) => [conv!, ...prev]);
        setActiveConversation(conv);
      } catch (err) {
        console.error("Failed to start conversation", err);
        return;
      }
    }

    const userMsg: MessageItem = {
      id: "temp-user-" + Date.now(),
      conversation_id: conv.id,
      sender_type: "user",
      content,
      token_count: content.split(" ").length,
      citations: [],
      created_at: new Date().toISOString(),
    };

    const assistantMsgId = "temp-asst-" + Date.now();
    const placeholderAssistantMsg: MessageItem = {
      id: assistantMsgId,
      conversation_id: conv.id,
      sender_type: "assistant",
      content: "",
      token_count: 0,
      citations: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg, placeholderAssistantMsg]);
    setInputMessage("");
    setStreaming(true);

    try {
      await api.streamChatMessage(conv.id, content, {
        onToken: (delta) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: m.content + delta }
                : m
            )
          );
        },
        onCitations: (citations) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, citations } : m
            )
          );
        },
        onComplete: (meta) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId ? { ...m, id: meta.messageId } : m
            )
          );
          setStreaming(false);
        },
        onError: (err) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: m.content + `\n\n[Generation Error: ${err}]` }
                : m
            )
          );
          setStreaming(false);
        },
      });
    } catch (err) {
      console.error("Stream failed", err);
      setStreaming(false);
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex h-[calc(100vh-5rem)] border border-slate-800/80 rounded-2xl overflow-hidden bg-slate-950 shadow-2xl backdrop-blur-xl">
      {/* ================================================================= */}
      {/* 1. LEFT SIDEBAR: Assistant Studio List & Conversation History */}
      {/* ================================================================= */}
      <div className="w-80 bg-slate-900/60 border-r border-slate-800/80 flex flex-col justify-between shrink-0">
        <div>
          {/* Studio Header */}
          <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-sky-500/10 text-sky-400 flex items-center justify-center border border-sky-500/20">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <span className="text-xs font-bold tracking-tight text-slate-100 block">
                  Assistant Studio
                </span>
                <span className="text-[10px] text-slate-500">M06 Creation & Lifecycle</span>
              </div>
            </div>
            <button
              onClick={() => setShowWizard(true)}
              className="p-1.5 px-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium transition cursor-pointer flex items-center gap-1 shadow-sm"
              title="Create Assistant Wizard"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New</span>
            </button>
          </div>

          {/* Search Box */}
          <div className="p-2.5 border-b border-slate-800/60">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter assistants..."
                className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] text-slate-200 placeholder:text-slate-600 focus:border-sky-500 outline-none transition"
              />
            </div>
          </div>
        </div>

        {/* Assistant List */}
        <div className="p-2 space-y-1 overflow-y-auto max-h-64 border-b border-slate-800/80 flex-1">
          {loading ? (
            <div className="p-4 text-center text-[11px] text-slate-500">Loading assistants...</div>
          ) : filteredAssistants.length === 0 ? (
            <div className="p-4 text-center text-[11px] text-slate-500">
              {searchQuery ? "No matching assistants." : "No assistants created yet."}
            </div>
          ) : (
            filteredAssistants.map((asst) => {
              const isSelected = activeAssistant?.id === asst.id;
              return (
                <button
                  key={asst.id}
                  onClick={() => {
                    setActiveAssistant(asst);
                  }}
                  className={`w-full text-left p-2.5 rounded-xl text-xs transition cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? "bg-slate-800/90 text-white font-medium border border-sky-500/30 shadow-sm"
                      : "text-slate-400 hover:bg-slate-900/80 hover:text-slate-200"
                  }`}
                >
                  <div className="truncate pr-2 flex-1">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="truncate font-semibold">{asst.name}</span>
                      <span className="px-1.5 py-0.2 rounded text-[9px] bg-slate-800 text-sky-400 border border-slate-700/60 font-mono">
                        v{asst.current_version_num || 1}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-500 truncate flex items-center gap-1.5 mt-0.5">
                      {asst.template_id ? (
                        <span className="text-sky-400/90 truncate flex items-center gap-1">
                          <Tag className="w-2.5 h-2.5" />
                          {asst.template_id.replace(/-/g, " ")}
                        </span>
                      ) : (
                        <span className="capitalize">{asst.llm_provider || "omniroute"}</span>
                      )}
                    </div>
                  </div>
                  {asst.connected_kb_ids && asst.connected_kb_ids.length > 0 && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] bg-emerald-950 text-emerald-400 border border-emerald-800/60 font-mono shrink-0">
                      {asst.connected_kb_ids.length} KB
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Conversations History */}
        <div className="h-48 flex flex-col overflow-hidden bg-slate-950/40">
          <div className="p-2.5 px-4 flex items-center justify-between text-[11px] font-semibold text-slate-400 border-b border-slate-800/60">
            <span>Conversations</span>
            <button
              onClick={handleNewConversation}
              className="text-[10px] text-sky-400 hover:text-sky-300 transition cursor-pointer flex items-center gap-1"
            >
              <Plus className="w-3 h-3" />
              <span>New</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {conversations.length === 0 ? (
              <div className="p-3 text-center text-[10px] text-slate-600">No chats recorded.</div>
            ) : (
              conversations.map((c) => {
                const isSelected = activeConversation?.id === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => {
                      setActiveConversation(c);
                      setViewMode("chat");
                    }}
                    className={`group w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition cursor-pointer flex items-center justify-between ${
                      isSelected && viewMode === "chat"
                        ? "bg-sky-600/10 text-sky-300 font-medium border border-sky-500/20"
                        : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-60" />
                      <span className="truncate text-[11px]">{c.title}</span>
                    </div>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        await api.deleteConversation(c.id);
                        setConversations((prev) => prev.filter((item) => item.id !== c.id));
                        if (activeConversation?.id === c.id) {
                          setActiveConversation(null);
                        }
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition"
                      title="Delete chat"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Workspace Footer Info */}
        <div className="p-3 border-t border-slate-800/80 bg-slate-900/40 text-[10px] text-slate-500 flex items-center justify-between">
          <span className="truncate max-w-[140px]">{activeWorkspace?.tenant_name || "Workspace"}</span>
          <span className="font-mono text-sky-400">Studio M06</span>
        </div>
      </div>

      {/* ================================================================= */}
      {/* 2. MAIN WORKSPACE / CHAT CONTAINER */}
      {/* ================================================================= */}
      <div className="flex-1 flex flex-col bg-slate-950 overflow-hidden relative">
        {activeAssistant ? (
          <>
            {/* Top Navigation & Mode Switcher Header */}
            <div className="p-3.5 px-6 border-b border-slate-800/80 bg-slate-900/40 backdrop-blur-md flex items-center justify-between z-10">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-sky-500/10 text-sky-400 flex items-center justify-center font-bold border border-sky-500/20">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold text-white tracking-tight">
                      {activeAssistant.name}
                    </h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950/80 text-sky-400 border border-sky-800/60 font-semibold">
                      v{activeAssistant.current_version_num || 1}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60">
                      {activeAssistant.llm_provider || "omniroute"} • {activeAssistant.default_model || "auto"}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5 truncate max-w-md">
                    {activeAssistant.description || "Configurable Multi-Tenant Assistant"}
                  </p>
                </div>
              </div>

              {/* View Switcher: Studio Workspace vs Chat Sandbox */}
              <div className="flex items-center gap-3">
                <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
                  <button
                    type="button"
                    onClick={() => setViewMode("workspace")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${
                      viewMode === "workspace"
                        ? "bg-slate-800 text-sky-400 font-semibold shadow-sm"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <Sliders className="w-3.5 h-3.5" />
                    <span>Workspace & Versions</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("chat")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${
                      viewMode === "chat"
                        ? "bg-sky-600 text-white font-semibold shadow-sm"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Chat Sandbox</span>
                  </button>
                </div>

                <button
                  onClick={() => setShowWizard(true)}
                  className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium transition cursor-pointer flex items-center gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>New Assistant</span>
                </button>
              </div>
            </div>

            {/* Content Switcher */}
            {viewMode === "workspace" ? (
              <div className="flex-1 overflow-y-auto">
                <AssistantWorkspaceView
                  assistant={activeAssistant}
                  tenantKBs={tenantKBs}
                  onUpdate={(updated) => {
                    setAssistants((prev) =>
                      prev.map((a) => (a.id === updated.id ? updated : a))
                    );
                    setActiveAssistant(updated);
                  }}
                  onDelete={(id) => {
                    const remaining = assistants.filter((a) => a.id !== id);
                    setAssistants(remaining);
                    setActiveAssistant(remaining.length > 0 ? remaining[0] : null);
                  }}
                  onStartChat={(asst) => {
                    setActiveAssistant(asst);
                    setViewMode("chat");
                  }}
                />
              </div>
            ) : (
              /* Conversational Chat View */
              <div className="flex-1 flex flex-col overflow-hidden relative">
                {/* Chat Messages Log */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center max-w-sm mx-auto">
                      <div className="w-12 h-12 rounded-2xl bg-sky-500/10 text-sky-400 flex items-center justify-center mb-3 border border-sky-500/20">
                        <Sparkles className="w-6 h-6" />
                      </div>
                      <h3 className="text-sm font-bold text-slate-200">
                        Ready to chat with {activeAssistant.name}
                      </h3>
                      <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                        Test questions grounded in connected knowledge bases. Responses follow the
                        configured prompt trust hierarchy.
                      </p>
                    </div>
                  ) : (
                    messages.map((m) => {
                      const isUser = m.sender_type === "user";
                      return (
                        <div
                          key={m.id}
                          className={`flex flex-col ${
                            isUser ? "items-end" : "items-start"
                          } max-w-3xl mx-auto`}
                        >
                          <div className="flex items-center gap-2 mb-1 px-1">
                            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                              {isUser ? "You" : activeAssistant.name}
                            </span>
                            <span className="text-[9px] text-slate-600 font-mono">
                              {new Date(m.created_at).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </div>

                          <div
                            className={`p-4 rounded-2xl text-xs leading-relaxed max-w-2xl transition shadow-sm ${
                              isUser
                                ? "bg-sky-600 text-white rounded-br-sm"
                                : "bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-sm"
                            }`}
                          >
                            <div className="whitespace-pre-wrap font-sans">
                              {isUser || !m.citations || m.citations.length === 0
                                ? m.content
                                : m.content.split(/(\[\d+\])/g).map((part, pIdx) => {
                                    const match = part.match(/^\[(\d+)\]$/);
                                    if (match) {
                                      const cNum = parseInt(match[1], 10);
                                      const matchedCitation = m.citations.find(
                                        (c) => c.citation_num === cNum
                                      );
                                      if (matchedCitation) {
                                        return (
                                          <button
                                            key={pIdx}
                                            type="button"
                                            onClick={() => {
                                              setActiveCitation(matchedCitation);
                                              setCitationTab("visual");
                                            }}
                                            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-sky-500/20 hover:bg-sky-500/35 text-sky-300 font-mono text-[10px] font-bold border border-sky-500/40 transition cursor-pointer shadow-sm hover:scale-105 active:scale-95"
                                            title={`View Citation [${cNum}] — ${matchedCitation.document_name}`}
                                          >
                                            [{cNum}]
                                          </button>
                                        );
                                      }
                                    }
                                    return <span key={pIdx}>{part}</span>;
                                  })}
                            </div>

                            {!isUser && m.citations && m.citations.length > 0 && (
                              <div className="mt-3 pt-3 border-t border-slate-800/80">
                                <div className="text-[10px] font-semibold text-slate-400 mb-1.5 flex items-center justify-between">
                                  <div className="flex items-center gap-1">
                                    <FileText className="w-3 h-3 text-sky-400" />
                                    <span>Verified Document Citations:</span>
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                  {m.citations.map((c) => (
                                    <button
                                      key={c.id || c.citation_num}
                                      onClick={() => {
                                        setActiveCitation(c);
                                        setCitationTab("visual");
                                      }}
                                      className="px-2.5 py-1 rounded-lg bg-slate-950/90 hover:bg-sky-950/40 text-[10px] text-slate-300 border border-slate-800 hover:border-sky-500/40 transition cursor-pointer flex items-center gap-1.5 shadow-sm group"
                                    >
                                      <span className="font-mono text-sky-400 font-bold group-hover:scale-110 transition">
                                        [{c.citation_num}]
                                      </span>
                                      <span className="truncate max-w-[130px] font-medium text-slate-200">
                                        {c.document_name}
                                      </span>
                                      <span className="px-1 py-0.2 rounded bg-slate-800/80 text-[9px] text-slate-400 font-mono">
                                        p.{c.page_number || 1}
                                      </span>
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>

                          {!isUser && m.content && (
                            <div className="flex items-center gap-2 mt-1 px-1 text-slate-500">
                              <button
                                onClick={() => handleCopy(m.id, m.content)}
                                className="hover:text-slate-300 transition text-[10px] flex items-center gap-1"
                              >
                                {copiedId === m.id ? (
                                  <>
                                    <Check className="w-3 h-3 text-sky-400" />
                                    <span className="text-sky-400">Copied</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3 h-3" />
                                    <span>Copy</span>
                                  </>
                                )}
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Box */}
                <div className="p-4 px-6 border-t border-slate-800/80 bg-slate-900/60 backdrop-blur-md">
                  <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex gap-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder={`Ask ${activeAssistant.name} a test question...`}
                      disabled={streaming}
                      className="flex-1 px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs focus:border-sky-500 outline-none transition disabled:opacity-50"
                    />

                    {streaming ? (
                      <button
                        type="button"
                        onClick={() => {
                          abortControllerRef.current?.abort();
                          setStreaming(false);
                        }}
                        className="px-4 py-3 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                      >
                        <Square className="w-3.5 h-3.5 fill-current" />
                        <span>Stop</span>
                      </button>
                    ) : (
                      <button
                        type="submit"
                        disabled={!inputMessage.trim()}
                        className="px-5 py-3 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50 shadow-lg shadow-sky-600/20"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>Send</span>
                      </button>
                    )}
                  </form>
                </div>
              </div>
            )}
          </>
        ) : (
          /* Empty State */
          <div className="h-full flex flex-col items-center justify-center text-center p-6">
            <div className="w-14 h-14 rounded-2xl bg-sky-500/10 text-sky-400 flex items-center justify-center mb-4 border border-sky-500/20">
              <Bot className="w-7 h-7" />
            </div>
            <h3 className="text-base font-bold text-slate-200">Welcome to Assistant Studio</h3>
            <p className="text-xs text-slate-400 mt-2 max-w-sm leading-relaxed">
              Create purpose-specific AI assistants with guided 5-step creation, safe instructions,
              version history, and optional knowledge integration.
            </p>
            <button
              onClick={() => setShowWizard(true)}
              className="mt-6 px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold transition cursor-pointer flex items-center gap-2 shadow-lg shadow-sky-600/20"
            >
              <Plus className="w-4 h-4" />
              <span>Create Your First Assistant</span>
            </button>
          </div>
        )}

        {/* ================================================================= */}
        {/* 3. CITATION PREVIEW / INSPECTOR MODAL */}
        {/* ================================================================= */}
        {activeCitation && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-3 md:p-6 overflow-y-auto">
            <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-4xl w-full shadow-2xl flex flex-col max-h-[92vh] overflow-hidden animate-fadeIn">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/70">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="w-8 h-8 rounded-xl bg-sky-500/20 text-sky-400 font-mono text-sm font-bold flex items-center justify-center shrink-0 border border-sky-500/30">
                    [{activeCitation.citation_num}]
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-100 truncate">
                        {activeCitation.document_name}
                      </h3>
                      <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] font-mono text-slate-300 border border-slate-700">
                        Page {activeCitation.page_number || 1}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
                    <button
                      type="button"
                      onClick={() => setCitationTab("visual")}
                      className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                        citationTab === "visual"
                          ? "bg-sky-600 text-white shadow-sm"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Visual Page</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setCitationTab("text")}
                      className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                        citationTab === "text"
                          ? "bg-sky-600 text-white shadow-sm"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>Context & Text</span>
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => setActiveCitation(null)}
                    className="p-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition cursor-pointer"
                    title="Close"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="p-6 overflow-y-auto flex-1 bg-slate-950/40">
                {citationTab === "visual" ? (
                  <div className="flex flex-col items-center">
                    <div className="w-full max-w-2xl mb-3 flex items-center justify-between text-[11px] text-slate-400 px-2">
                      <div className="flex items-center gap-2">
                        <Layers className="w-3.5 h-3.5 text-sky-400" />
                        <span>Interactive PDF Viewport</span>
                      </div>
                      <div className="font-mono text-[10px]">
                        Page {activeCitation.page_number || 1}
                      </div>
                    </div>

                    <div className="relative w-full max-w-2xl bg-slate-950 border-2 border-slate-800 rounded-2xl shadow-2xl p-8 flex flex-col justify-between">
                      <p className="text-slate-100 text-xs leading-relaxed font-sans font-medium select-text">
                        &ldquo;{activeCitation.citation_text || activeCitation.snippet}&rdquo;
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4 max-w-2xl mx-auto">
                    <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800">
                      <div className="text-[11px] font-bold text-slate-400 mb-2 flex items-center justify-between">
                        <span>SOURCE EXCERPT</span>
                        <span className="font-mono text-sky-400">Page {activeCitation.page_number || 1}</span>
                      </div>
                      <div className="text-xs text-slate-200 leading-relaxed font-sans whitespace-pre-wrap select-text">
                        {activeCitation.citation_text || activeCitation.snippet}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* 4. GUIDED 5-STEP ASSISTANT CREATION WIZARD MODAL */}
        {/* ================================================================= */}
        <AssistantCreationWizard
          isOpen={showWizard}
          onClose={() => setShowWizard(false)}
          onSuccess={(newAsst) => {
            setAssistants((prev) => [newAsst, ...prev]);
            setActiveAssistant(newAsst);
            setViewMode("workspace");
            setShowWizard(false);
          }}
          tenantKBs={tenantKBs}
        />
      </div>
    </div>
  );
}
