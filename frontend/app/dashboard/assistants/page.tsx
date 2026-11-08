"use client";

import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  AssistantItem,
  ConversationItem,
  KnowledgeBaseItem,
  MessageCitationItem,
  MessageItem,
} from "@/lib/api";
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
} from "lucide-react";


export default function AssistantsChatPage() {
  const { activeWorkspace } = useAuth();

  // State: Assistants
  const [assistants, setAssistants] = useState<AssistantItem[]>([]);
  const [activeAssistant, setActiveAssistant] = useState<AssistantItem | null>(null);
  const [tenantKBs, setTenantKBs] = useState<KnowledgeBaseItem[]>([]);
  const [loading, setLoading] = useState(true);

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

  const activeMessageCitations = React.useMemo(() => {
    if (!activeCitation) return [];
    const containingMsg = messages.find((m) =>
      m.citations?.some((c) => c.citation_num === activeCitation.citation_num || (c.id && c.id === activeCitation.id))
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
    const prevIdx = (currentCitationIdx - 1 + activeMessageCitations.length) % activeMessageCitations.length;
    setActiveCitation(activeMessageCitations[prevIdx]);
    setCopiedCitationText(false);
    setCopiedCitationTag(false);
  };

  // State: Assistant Editor Drawer
  const [showEditor, setShowEditor] = useState(false);
  const [isNewAssistant, setIsNewAssistant] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editProvider, setEditProvider] = useState("omniroute");
  const [editModel, setEditModel] = useState("auto");
  const [editTemperature, setEditTemperature] = useState(0.7);
  const [editMaxTokens, setEditMaxTokens] = useState(1024);
  const [editRetrievalMode, setEditRetrievalMode] = useState<"hybrid" | "semantic" | "lexical">("hybrid");
  const [editTopK, setEditTopK] = useState(5);
  const [editSystemPrompt, setEditSystemPrompt] = useState("");
  const [selectedKBIds, setSelectedKBIds] = useState<string[]>([]);
  const [editorSubmitting, setEditorSubmitting] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

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
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

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
      // Auto-create conversation
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

    // Append user message immediately
    const userMsg: MessageItem = {
      id: "temp-user-" + Date.now(),
      conversation_id: conv.id,
      sender_type: "user",
      content,
      token_count: content.split(" ").length,
      citations: [],
      created_at: new Date().toISOString(),
    };

    // Temporary placeholder for assistant streaming
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

  // 6. Editor Drawer Actions
  const openEditorForCreate = () => {
    setIsNewAssistant(true);
    setEditName("");
    setEditDescription("");
    setEditProvider("omniroute");
    setEditModel("auto");
    setEditTemperature(0.7);
    setEditMaxTokens(1024);
    setEditRetrievalMode("hybrid");
    setEditTopK(5);
    setEditSystemPrompt("You are an expert enterprise AI assistant. Ground your answers strictly in connected documentation.");
    setSelectedKBIds([]);
    setEditorError(null);
    setShowEditor(true);
  };

  const openEditorForEdit = (asst: AssistantItem) => {
    setIsNewAssistant(false);
    setEditName(asst.name);
    setEditDescription(asst.description || "");
    setEditProvider(asst.llm_provider || "omniroute");
    setEditModel(asst.default_model || "auto");
    setEditTemperature(asst.temperature ?? 0.7);
    setEditMaxTokens(asst.max_tokens ?? 1024);
    setEditRetrievalMode((asst.retrieval_mode as "hybrid" | "semantic" | "lexical") || "hybrid");
    setEditTopK(asst.top_k ?? 5);
    setEditSystemPrompt(asst.system_prompt || "");
    setSelectedKBIds(asst.connected_kb_ids || []);
    setEditorError(null);
    setShowEditor(true);
  };

  const handleSaveAssistant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editName.trim()) return;
    setEditorSubmitting(true);
    setEditorError(null);

    const payload = {
      name: editName.trim(),
      description: editDescription.trim() || undefined,
      llm_provider: editProvider,
      default_model: editModel,
      temperature: editTemperature,
      max_tokens: editMaxTokens,
      retrieval_mode: editRetrievalMode,
      top_k: editTopK,
      system_prompt: editSystemPrompt.trim() || undefined,
      knowledge_base_ids: selectedKBIds,
    };

    try {
      if (isNewAssistant) {
        const created = await api.createAssistant(payload);
        setAssistants((prev) => [created, ...prev]);
        setActiveAssistant(created);
      } else if (activeAssistant) {
        const updated = await api.updateAssistant(activeAssistant.id, payload);
        setAssistants((prev) =>
          prev.map((a) => (a.id === updated.id ? updated : a))
        );
        setActiveAssistant(updated);
      }
      setShowEditor(false);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setEditorError(err.message);
      } else {
        setEditorError("Failed to save assistant configuration");
      }
    } finally {
      setEditorSubmitting(false);
    }
  };

  const handleDeleteAssistant = async () => {
    if (!activeAssistant) return;
    if (!confirm(`Are you sure you want to delete assistant "${activeAssistant.name}"?`)) return;
    try {
      await api.deleteAssistant(activeAssistant.id);
      const remaining = assistants.filter((a) => a.id !== activeAssistant.id);
      setAssistants(remaining);
      setActiveAssistant(remaining.length > 0 ? remaining[0] : null);
      setShowEditor(false);
    } catch (err) {
      console.error("Failed to delete assistant", err);
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
      {/* 1. LEFT SIDEBAR: Assistants & Conversations Navigation */}
      {/* ================================================================= */}
      <div className="w-72 bg-slate-900/60 border-r border-slate-800/80 flex flex-col justify-between shrink-0">
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
              <Bot className="w-4 h-4" />
            </div>
            <span className="text-xs font-bold tracking-tight text-slate-100">Assistants</span>
          </div>
          <button
            onClick={openEditorForCreate}
            className="p-1.5 rounded-lg bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600 hover:text-white transition cursor-pointer"
            title="Create Assistant"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Assistant List */}
        <div className="p-2 space-y-1 overflow-y-auto max-h-56 border-b border-slate-800/80">
          {loading ? (
            <div className="p-4 text-center text-[11px] text-slate-500">Loading agents...</div>
          ) : assistants.length === 0 ? (
            <div className="p-4 text-center text-[11px] text-slate-500">No assistants yet.</div>
          ) : (
            assistants.map((asst) => {
              const isSelected = activeAssistant?.id === asst.id;
              return (
                <button
                  key={asst.id}
                  onClick={() => setActiveAssistant(asst)}
                  className={`w-full text-left p-2.5 rounded-xl text-xs transition cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? "bg-slate-800/90 text-white font-medium border border-slate-700/80"
                      : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                  }`}
                >
                  <div className="truncate pr-2">
                    <div className="truncate font-semibold">{asst.name}</div>
                    <div className="text-[10px] text-slate-500 truncate flex items-center gap-1.5 mt-0.5">
                      <span className="capitalize">{asst.llm_provider}</span> • <span>{asst.default_model}</span>
                    </div>
                  </div>
                  {asst.connected_kb_ids && asst.connected_kb_ids.length > 0 && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] bg-emerald-950 text-emerald-400 border border-emerald-800/60 font-mono">
                      {asst.connected_kb_ids.length} KB
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Conversations History */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="p-3 px-4 flex items-center justify-between text-[11px] font-semibold text-slate-400">
            <span>Conversations</span>
            <button
              onClick={handleNewConversation}
              className="text-[10px] text-blue-400 hover:text-blue-300 transition cursor-pointer flex items-center gap-1"
            >
              <Plus className="w-3 h-3" />
              <span>New</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {conversations.length === 0 ? (
              <div className="p-4 text-center text-[11px] text-slate-600">No chats recorded.</div>
            ) : (
              conversations.map((c) => {
                const isSelected = activeConversation?.id === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => setActiveConversation(c)}
                    className={`group w-full text-left px-3 py-2 rounded-xl text-xs transition cursor-pointer flex items-center justify-between ${
                      isSelected
                        ? "bg-blue-600/10 text-blue-300 font-medium border border-blue-500/20"
                        : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-60" />
                      <span className="truncate">{c.title}</span>
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
          <span>{activeWorkspace?.tenant_name || "Workspace"}</span>
          <span className="font-mono text-emerald-400">RAG Engine v0.4</span>
        </div>
      </div>

      {/* ================================================================= */}
      {/* 2. MAIN CENTER: Chat Stream & Citations Area */}
      {/* ================================================================= */}
      <div className="flex-1 flex flex-col bg-slate-950 overflow-hidden relative">
        {activeAssistant ? (
          <>
            {/* Header */}
            <div className="p-4 px-6 border-b border-slate-800/80 bg-slate-900/40 backdrop-blur-md flex items-center justify-between z-10">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold text-white tracking-tight">{activeAssistant.name}</h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60">
                      {activeAssistant.llm_provider} • {activeAssistant.default_model}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5 truncate max-w-lg">
                    {activeAssistant.description || activeAssistant.system_prompt || "Enterprise AI Assistant"}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-400 flex items-center gap-1.5 bg-slate-900 px-3 py-1.5 rounded-xl border border-slate-800">
                  <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{activeAssistant.connected_kb_ids?.length || 0} Knowledge Bases</span>
                </span>
                <button
                  onClick={() => openEditorForEdit(activeAssistant)}
                  className="p-2 rounded-xl bg-slate-800/80 text-slate-300 hover:text-white hover:bg-slate-700 transition cursor-pointer"
                  title="Assistant Settings"
                >
                  <Settings2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Chat Messages Log */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center max-w-sm mx-auto">
                  <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-3">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-200">Ready to chat with {activeAssistant.name}</h3>
                  <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                    Ask questions grounded in connected knowledge bases. Responses include verified citations.
                  </p>
                </div>
              ) : (
                messages.map((m) => {
                  const isUser = m.sender_type === "user";
                  return (
                    <div
                      key={m.id}
                      className={`flex flex-col ${isUser ? "items-end" : "items-start"} max-w-3xl mx-auto`}
                    >
                      <div className="flex items-center gap-2 mb-1 px-1">
                        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                          {isUser ? "You" : activeAssistant.name}
                        </span>
                        <span className="text-[9px] text-slate-600 font-mono">
                          {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>

                      <div
                        className={`p-4 rounded-2xl text-xs leading-relaxed max-w-2xl transition shadow-sm ${
                          isUser
                            ? "bg-emerald-600 text-white rounded-br-sm"
                            : "bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-sm"
                        }`}
                      >
                        {/* Message Content with interactive inline citation chips */}
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
                                        className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/35 text-emerald-300 font-mono text-[10px] font-bold border border-emerald-500/40 transition cursor-pointer shadow-sm hover:scale-105 active:scale-95"
                                        title={`View Citation [${cNum}] — ${matchedCitation.document_name} (Page ${matchedCitation.page_number || 1})`}
                                      >
                                        [{cNum}]
                                      </button>
                                    );
                                  }
                                }
                                return <span key={pIdx}>{part}</span>;
                              })}
                        </div>

                        {/* Citations Chips */}
                        {!isUser && m.citations && m.citations.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-slate-800/80">
                            <div className="text-[10px] font-semibold text-slate-400 mb-1.5 flex items-center justify-between">
                              <div className="flex items-center gap-1">
                                <FileText className="w-3 h-3 text-emerald-400" />
                                <span>Verified Document Citations:</span>
                              </div>
                              <span className="text-[9px] font-mono text-slate-500">
                                Click chip to inspect PDF bounding box
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {m.citations.map((c) => (
                                <button
                                  key={c.id || c.citation_num}
                                  onClick={() => {
                                    setActiveCitation(c);
                                    setCitationTab("visual");
                                  }}
                                  className="px-2.5 py-1 rounded-lg bg-slate-950/90 hover:bg-emerald-950/40 text-[10px] text-slate-300 border border-slate-800 hover:border-emerald-500/40 transition cursor-pointer flex items-center gap-1.5 shadow-sm group"
                                >
                                  <span className="font-mono text-emerald-400 font-bold group-hover:scale-110 transition">
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

                      {/* Action row (Copy) */}
                      {!isUser && m.content && (
                        <div className="flex items-center gap-2 mt-1 px-1 text-slate-500">
                          <button
                            onClick={() => handleCopy(m.id, m.content)}
                            className="hover:text-slate-300 transition text-[10px] flex items-center gap-1"
                          >
                            {copiedId === m.id ? (
                              <>
                                <Check className="w-3 h-3 text-emerald-400" />
                                <span className="text-emerald-400">Copied</span>
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
                  placeholder={`Ask ${activeAssistant.name} a question...`}
                  disabled={streaming}
                  className="flex-1 px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs focus:border-emerald-500 outline-none transition disabled:opacity-50"
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
                    className="px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50 shadow-lg shadow-emerald-600/20"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Send</span>
                  </button>
                )}
              </form>
            </div>
          </>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center p-6">
            <Bot className="w-12 h-12 text-slate-700 mb-3" />
            <h3 className="text-sm font-bold text-slate-300">No Assistant Selected</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              Choose an assistant from the left sidebar or create a new one to begin.
            </p>
            <button
              onClick={openEditorForCreate}
              className="mt-4 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition cursor-pointer flex items-center gap-2"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Assistant</span>
            </button>
          </div>
        )}

        {/* ================================================================= */}
        {/* 3. CITATION PREVIEW MODAL */}
        {/* ================================================================= */}
        {/* ================================================================= */}
        {/* 3. CITATION VISUAL PDF DRAWER / INSPECTOR MODAL */}
        {/* ================================================================= */}
        {activeCitation && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-3 md:p-6 overflow-y-auto">
            <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-4xl w-full shadow-2xl flex flex-col max-h-[92vh] overflow-hidden animate-fadeIn">
              {/* Header Bar */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/70">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-400 font-mono text-sm font-bold flex items-center justify-center shrink-0 border border-emerald-500/30 shadow-inner">
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
                      {activeCitation.score !== undefined && activeCitation.score !== null && (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-950/80 text-[10px] font-mono text-emerald-400 border border-emerald-800/80">
                          {Math.round(activeCitation.score * 100)}% match
                        </span>
                      )}
                    </div>
                    {activeCitation.heading_path && (
                      <p className="text-[11px] text-slate-400 truncate mt-0.5">
                        {activeCitation.heading_path}
                      </p>
                    )}
                  </div>
                </div>

                {/* Header Controls: Tab Switcher, Carousel Navigation, Close */}
                <div className="flex items-center gap-3 shrink-0">
                  {/* View Mode Tabs */}
                  <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
                    <button
                      type="button"
                      onClick={() => setCitationTab("visual")}
                      className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                        citationTab === "visual"
                          ? "bg-emerald-600 text-white shadow-sm"
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
                          ? "bg-emerald-600 text-white shadow-sm"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>Context & Text</span>
                    </button>
                  </div>

                  {/* Carousel Prev/Next */}
                  {activeMessageCitations.length > 1 && (
                    <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
                      <button
                        type="button"
                        onClick={handlePrevCitation}
                        className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition cursor-pointer"
                        title="Previous Citation"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <span className="px-1 text-[11px] font-mono text-slate-400">
                        {currentCitationIdx + 1}/{activeMessageCitations.length}
                      </span>
                      <button
                        type="button"
                        onClick={handleNextCitation}
                        className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition cursor-pointer"
                        title="Next Citation"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  )}

                  {/* Close button */}
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

              {/* Body Content Area */}
              <div className="p-6 overflow-y-auto flex-1 bg-slate-950/40">
                {citationTab === "visual" ? (
                  <div className="flex flex-col items-center">
                    {/* Visual Canvas Toolbar Banner */}
                    <div className="w-full max-w-2xl mb-3 flex items-center justify-between text-[11px] text-slate-400 px-2">
                      <div className="flex items-center gap-2">
                        <Layers className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Interactive PDF Viewport (US Letter 612 × 792 pt)</span>
                      </div>
                      <div className="flex items-center gap-2 font-mono text-[10px]">
                        <span>BBox:</span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                          x: {Math.round(activeCitation.bounding_box?.x ?? 72)}pt, y: {Math.round(activeCitation.bounding_box?.y ?? 90)}pt
                        </span>
                      </div>
                    </div>

                    {/* PDF Sheet Canvas */}
                    <div className="relative w-full max-w-2xl bg-slate-950 border-2 border-slate-800 rounded-2xl shadow-2xl overflow-hidden aspect-[612/792] p-8 flex flex-col justify-between select-none">
                      {/* Document Sheet Header */}
                      <div>
                        <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-[10px] text-slate-500 font-mono">
                          <span className="truncate max-w-xs">{activeCitation.document_name}</span>
                          <span className="text-emerald-500/80 font-bold">PAGE {activeCitation.page_number || 1}</span>
                        </div>

                        {/* Simulated Document Text Skeleton Lines */}
                        <div className="space-y-3 mt-6">
                          <div className="h-2.5 bg-slate-800/70 rounded-full w-3/4"></div>
                          <div className="h-2 bg-slate-800/50 rounded-full w-full"></div>
                          <div className="h-2 bg-slate-800/50 rounded-full w-5/6"></div>
                          <div className="h-2 bg-slate-800/40 rounded-full w-11/12"></div>
                          <div className="h-2.5 bg-slate-800/70 rounded-full w-2/3 mt-4"></div>
                          <div className="h-2 bg-slate-800/50 rounded-full w-full"></div>
                        </div>
                      </div>

                      {/* DYNAMIC BOUNDING BOX HIGHLIGHT OVERLAY */}
                      {(() => {
                        const bbox = activeCitation.bounding_box || {
                          page: activeCitation.page_number || 1,
                          x: 72,
                          y: 175,
                          width: 468,
                          height: 75,
                        };
                        const leftPct = (bbox.x / 612) * 100;
                        const topPct = (bbox.y / 792) * 100;
                        const widthPct = (bbox.width / 612) * 100;
                        const heightPct = Math.max((bbox.height / 792) * 100, 16);

                        return (
                          <div
                            style={{
                              position: "absolute",
                              left: `${leftPct}%`,
                              top: `${topPct}%`,
                              width: `${widthPct}%`,
                              minHeight: `${heightPct}%`,
                            }}
                            className="border-2 border-emerald-400 bg-emerald-500/20 backdrop-blur-[2px] rounded-xl shadow-[0_0_35px_rgba(16,185,129,0.35)] ring-4 ring-emerald-500/20 z-10 transition-all flex flex-col justify-between p-3"
                          >
                            {/* Floating Highlight Pin Badge */}
                            <div className="absolute -top-3 left-3 px-2 py-0.5 rounded-full bg-emerald-600 text-[10px] font-bold text-white shadow-md flex items-center gap-1.5 z-20">
                              <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                              <span>Citation [{activeCitation.citation_num}] Excerpt</span>
                            </div>

                            {/* Highlighted Verified Text */}
                            <p className="text-slate-100 text-xs leading-relaxed font-sans font-medium line-clamp-4 select-text">
                              &ldquo;{activeCitation.citation_text || activeCitation.snippet}&rdquo;
                            </p>

                            {/* Coordinate Footer Inside Bounding Box */}
                            <div className="flex items-center justify-between text-[9px] font-mono text-emerald-300/80 pt-1 border-t border-emerald-500/30">
                              <span>Page {bbox.page} • Conf: {activeCitation.score ? `${Math.round(activeCitation.score * 100)}%` : "Verified"}</span>
                              <span>{Math.round(bbox.width)}×{Math.round(bbox.height)} pt</span>
                            </div>
                          </div>
                        );
                      })()}

                      {/* Lower Skeleton Lines */}
                      <div className="space-y-3">
                        <div className="h-2 bg-slate-800/40 rounded-full w-full"></div>
                        <div className="h-2 bg-slate-800/50 rounded-full w-4/5"></div>
                        <div className="h-2 bg-slate-800/40 rounded-full w-full"></div>
                        <div className="h-2 bg-slate-800/60 rounded-full w-2/4"></div>

                        {/* Document Footer */}
                        <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-600">
                          <span>Multi-Tenant Enterprise Document Engine</span>
                          <span>SHA-256 Validated</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Text & Metadata Tab */
                  <div className="space-y-4 max-w-2xl mx-auto">
                    {/* Full Snippet Card */}
                    <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800">
                      <div className="text-[11px] font-bold text-slate-400 mb-2 flex items-center justify-between">
                        <span>FULL SOURCE EXCERPT</span>
                        <span className="font-mono text-emerald-400">Page {activeCitation.page_number || 1}</span>
                      </div>
                      <div className="text-xs text-slate-200 leading-relaxed font-sans whitespace-pre-wrap select-text">
                        {activeCitation.citation_text || activeCitation.snippet}
                      </div>
                    </div>

                    {/* Metadata Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Document</span>
                        <span className="text-xs font-semibold text-slate-200 truncate block mt-0.5" title={activeCitation.document_name}>
                          {activeCitation.document_name}
                        </span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Page & Citation</span>
                        <span className="text-xs font-semibold text-slate-200 block mt-0.5">
                          Page {activeCitation.page_number || 1} (Chip [{activeCitation.citation_num}])
                        </span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Relevance Score</span>
                        <span className="text-xs font-semibold text-emerald-400 block mt-0.5">
                          {activeCitation.score !== undefined && activeCitation.score !== null
                            ? `${(activeCitation.score * 100).toFixed(1)}%`
                            : "Direct Match"}
                        </span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 col-span-2 md:col-span-3">
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Heading Hierarchy</span>
                        <span className="text-xs font-semibold text-slate-300 block mt-0.5">
                          {activeCitation.heading_path || "Root Document Section"}
                        </span>
                      </div>
                      {activeCitation.chunk_id && (
                        <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 col-span-2 md:col-span-3">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Chunk UUID</span>
                          <span className="text-xs font-mono text-slate-400 block mt-0.5 break-all">
                            {activeCitation.chunk_id}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Action Bar Footer */}
              <div className="px-6 py-3.5 border-t border-slate-800 bg-slate-950/70 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(activeCitation.citation_text || activeCitation.snippet || "");
                      setCopiedCitationText(true);
                      setTimeout(() => setCopiedCitationText(false), 2000);
                    }}
                    className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition cursor-pointer flex items-center gap-1.5"
                  >
                    {copiedCitationText ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedCitationText ? "Excerpt Copied" : "Copy Excerpt"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(`[${activeCitation.citation_num}]`);
                      setCopiedCitationTag(true);
                      setTimeout(() => setCopiedCitationTag(false), 2000);
                    }}
                    className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition cursor-pointer flex items-center gap-1.5"
                  >
                    {copiedCitationTag ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Hash className="w-3.5 h-3.5 text-emerald-400" />}
                    <span>{copiedCitationTag ? "Tag Copied" : `Copy [${activeCitation.citation_num}]`}</span>
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setActiveCitation(null)}
                    className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition cursor-pointer shadow-md"
                  >
                    Done
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* 4. ASSISTANT CONFIGURATION DRAWER / MODAL */}
        {/* ================================================================= */}
        {showEditor && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-xl w-full shadow-2xl my-8 animate-fadeIn">
              <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center">
                    <Bot className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-100">
                      {isNewAssistant ? "Create AI Assistant" : `Configure ${editName}`}
                    </h3>
                    <p className="text-[11px] text-slate-400">Settings, model, system prompt, and connected knowledge bases</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowEditor(false)}
                  className="text-slate-400 hover:text-slate-200 text-xs cursor-pointer"
                >
                  ✕
                </button>
              </div>

              {editorError && (
                <div className="mb-4 p-3 rounded-xl bg-red-950/60 border border-red-800 text-red-300 text-xs">
                  {editorError}
                </div>
              )}

              <form onSubmit={handleSaveAssistant} className="space-y-4 text-xs">
                {/* General Info */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Assistant Name</label>
                    <input
                      type="text"
                      required
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      placeholder="e.g. HR Policy Tutor, Financial Analyst"
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-emerald-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">LLM Provider</label>
                    <select
                      value={editProvider}
                      onChange={(e) => setEditProvider(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-emerald-500 outline-none font-mono"
                    >
                      <option value="omniroute">OmniRoute (Local Gateway)</option>
                      <option value="openai">OpenAI (BYOK Direct)</option>
                      <option value="mock">Mock Provider (Offline Deterministic)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Description</label>
                  <input
                    type="text"
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="Brief scope of this assistant"
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-emerald-500 outline-none"
                  />
                </div>

                {/* Generation Settings */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Model</label>
                    <input
                      type="text"
                      value={editModel}
                      onChange={(e) => setEditModel(e.target.value)}
                      placeholder="auto, gpt-4o, etc."
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-emerald-500 outline-none font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Temperature ({editTemperature})</label>
                    <input
                      type="range"
                      min="0.0"
                      max="1.0"
                      step="0.1"
                      value={editTemperature}
                      onChange={(e) => setEditTemperature(parseFloat(e.target.value))}
                      className="w-full accent-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Max Output Tokens</label>
                    <input
                      type="number"
                      min="64"
                      max="4096"
                      value={editMaxTokens}
                      onChange={(e) => setEditMaxTokens(parseInt(e.target.value) || 1024)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-emerald-500 outline-none font-mono"
                    />
                  </div>
                </div>

                {/* Connected Knowledge Bases */}
                <div>
                  <label className="block text-slate-300 font-medium mb-1.5 flex items-center justify-between">
                    <span>Connected Knowledge Bases</span>
                    <span className="text-[10px] text-slate-500">{selectedKBIds.length} selected</span>
                  </label>
                  <div className="max-h-32 overflow-y-auto p-2 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                    {tenantKBs.length === 0 ? (
                      <div className="text-[11px] text-slate-500 p-2">No Knowledge Bases created yet.</div>
                    ) : (
                      tenantKBs.map((kb) => {
                        const checked = selectedKBIds.includes(kb.id);
                        return (
                          <label
                            key={kb.id}
                            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-900 text-slate-300 cursor-pointer text-xs"
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedKBIds((prev) => [...prev, kb.id]);
                                } else {
                                  setSelectedKBIds((prev) => prev.filter((id) => id !== kb.id));
                                }
                              }}
                              className="accent-emerald-500 rounded"
                            />
                            <span className="truncate">{kb.name}</span>
                            <span className="text-[10px] text-slate-500 font-mono ml-auto">
                              {kb.document_count} docs
                            </span>
                          </label>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* Retrieval Settings */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Retrieval Mode</label>
                    <select
                      value={editRetrievalMode}
                      onChange={(e) => setEditRetrievalMode(e.target.value as "hybrid" | "semantic" | "lexical")}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-emerald-500 outline-none font-mono"
                    >
                      <option value="hybrid">Hybrid (BM25 + Semantic RRF)</option>
                      <option value="semantic">Semantic Only (Vector Similarity)</option>
                      <option value="lexical">Lexical Only (Full-Text Search)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-300 font-medium mb-1">Top-K Chunks ({editTopK})</label>
                    <input
                      type="number"
                      min="1"
                      max="15"
                      value={editTopK}
                      onChange={(e) => setEditTopK(parseInt(e.target.value) || 5)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-emerald-500 outline-none font-mono"
                    />
                  </div>
                </div>

                {/* System Prompt */}
                <div>
                  <label className="block text-slate-300 font-medium mb-1">System Instructions</label>
                  <textarea
                    rows={4}
                    value={editSystemPrompt}
                    onChange={(e) => setEditSystemPrompt(e.target.value)}
                    placeholder="Instructions regarding persona, scope, tone, and citation behavior..."
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-emerald-500 outline-none resize-none font-mono text-[11px]"
                  />
                </div>

                {/* Footer Buttons */}
                <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                  {!isNewAssistant && (
                    <button
                      type="button"
                      onClick={handleDeleteAssistant}
                      className="px-3 py-2 rounded-xl bg-red-950/60 text-red-400 hover:bg-red-900 border border-red-800/80 transition cursor-pointer flex items-center gap-1.5"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Delete</span>
                    </button>
                  )}
                  <div className="flex gap-2 ml-auto">
                    <button
                      type="button"
                      onClick={() => setShowEditor(false)}
                      className="px-4 py-2 rounded-xl text-slate-400 hover:text-slate-200 transition cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={editorSubmitting}
                      className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition cursor-pointer disabled:opacity-50"
                    >
                      {editorSubmitting ? "Saving..." : isNewAssistant ? "Create Assistant" : "Save Changes"}
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
