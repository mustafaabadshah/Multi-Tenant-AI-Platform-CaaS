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
  Edit2,
  RotateCcw,
} from "lucide-react";
import MarkdownRenderer from "@/components/chat/MarkdownRenderer";

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
  const [convSearchQuery, setConvSearchQuery] = useState("");
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editingConvTitle, setEditingConvTitle] = useState("");

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

  const filteredConversations = useMemo(() => {
    if (!convSearchQuery.trim()) return conversations;
    const q = convSearchQuery.toLowerCase();
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, convSearchQuery]);

  const handleRenameConversation = async (convId: string, newTitle: string) => {
    const trimmed = newTitle.trim();
    if (!trimmed) {
      setEditingConvId(null);
      return;
    }
    try {
      const updated = await api.updateConversation(convId, { title: trimmed });
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, title: updated.title } : c))
      );
      if (activeConversation?.id === convId) {
        setActiveConversation((prev) => (prev ? { ...prev, title: updated.title } : null));
      }
    } catch (err) {
      console.error("Failed to rename conversation", err);
    } finally {
      setEditingConvId(null);
    }
  };

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
  const handleSendMessageWithText = async (textToSend: string) => {
    const content = textToSend.trim();
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

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    await handleSendMessageWithText(inputMessage);
  };

  const handleRegenerateResponse = async () => {
    if (streaming || !activeAssistant || !activeConversation) return;
    const userMessages = messages.filter((m) => m.sender_type === "user");
    if (userMessages.length === 0) return;
    const lastUserMsg = userMessages[userMessages.length - 1];
    // Remove the last assistant response from the display if present
    setMessages((prev) => {
      if (prev.length > 0 && prev[prev.length - 1].sender_type === "assistant") {
        return prev.slice(0, prev.length - 1);
      }
      return prev;
    });
    await handleSendMessageWithText(lastUserMsg.content);
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex h-[calc(100vh-5rem)] border border-gray-200 rounded-2xl overflow-hidden bg-white shadow-sm">
      {/* ================================================================= */}
      {/* 1. LEFT SIDEBAR: Assistant Studio List & Conversation History */}
      {/* ================================================================= */}
      <div className="w-80 bg-gray-50/70 border-r border-gray-200 flex flex-col justify-between shrink-0">
        <div>
          {/* Studio Header */}
          <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-white">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <span className="text-xs font-bold tracking-tight text-gray-900 block">
                  Assistant Studio
                </span>
                <span className="text-[10px] text-gray-500">M06 Creation & Lifecycle</span>
              </div>
            </div>
            <button
              onClick={() => setShowWizard(true)}
              className="p-1.5 px-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium transition cursor-pointer flex items-center gap-1 shadow-sm"
              title="Create Assistant Wizard"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New</span>
            </button>
          </div>

          {/* Search Box */}
          <div className="p-2.5 border-b border-gray-200 bg-white">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter assistants..."
                className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-gray-50 border border-gray-200 text-[11px] text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:bg-white outline-none transition"
              />
            </div>
          </div>
        </div>

        {/* Assistant List */}
        <div className="p-2 space-y-1 overflow-y-auto max-h-64 border-b border-gray-200 flex-1">
          {loading ? (
            <div className="p-4 text-center text-[11px] text-gray-400">Loading assistants...</div>
          ) : filteredAssistants.length === 0 ? (
            <div className="p-4 text-center text-[11px] text-gray-400">
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
                      ? "bg-white text-gray-900 font-semibold border border-blue-500/30 shadow-xs ring-1 ring-blue-500/10"
                      : "text-gray-600 hover:bg-gray-100/70 hover:text-gray-900"
                  }`}
                >
                  <div className="truncate pr-2 flex-1">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="truncate font-semibold">{asst.name}</span>
                      <span className="px-1.5 py-0.2 rounded text-[9px] bg-gray-100 text-blue-600 border border-gray-200 font-mono">
                        v{asst.current_version_num || 1}
                      </span>
                    </div>
                    <div className="text-[10px] text-gray-500 truncate flex items-center gap-1.5 mt-0.5">
                      {asst.template_id ? (
                        <span className="text-blue-600/90 truncate flex items-center gap-1">
                          <Tag className="w-2.5 h-2.5" />
                          {asst.template_id.replace(/-/g, " ")}
                        </span>
                      ) : (
                        <span className="capitalize">{asst.llm_provider || "omniroute"}</span>
                      )}
                    </div>
                  </div>
                  {asst.connected_kb_ids && asst.connected_kb_ids.length > 0 && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono shrink-0">
                      {asst.connected_kb_ids.length} KB
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Conversations History */}
        <div className="h-56 flex flex-col overflow-hidden bg-gray-50/50">
          <div className="p-2.5 px-4 flex items-center justify-between text-[11px] font-semibold text-gray-700 border-b border-gray-200 bg-white/60">
            <span>Conversations</span>
            <button
              onClick={handleNewConversation}
              className="text-[10px] text-blue-600 hover:text-blue-700 transition cursor-pointer flex items-center gap-1 font-medium"
            >
              <Plus className="w-3 h-3" />
              <span>New</span>
            </button>
          </div>

          {/* Quick filter for conversations */}
          {conversations.length > 2 && (
            <div className="px-2.5 py-1.5 border-b border-gray-200">
              <input
                type="text"
                value={convSearchQuery}
                onChange={(e) => setConvSearchQuery(e.target.value)}
                placeholder="Search chats..."
                className="w-full px-2 py-1 rounded bg-white border border-gray-200 text-[10px] text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500 transition"
              />
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {filteredConversations.length === 0 ? (
              <div className="p-3 text-center text-[10px] text-gray-400">
                {convSearchQuery ? "No matching chats." : "No chats recorded."}
              </div>
            ) : (
              filteredConversations.map((c) => {
                const isSelected = activeConversation?.id === c.id;
                const isEditing = editingConvId === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => {
                      if (!isEditing) {
                        setActiveConversation(c);
                        setViewMode("chat");
                      }
                    }}
                    className={`group w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition cursor-pointer flex items-center justify-between gap-1 ${
                      isSelected && viewMode === "chat"
                        ? "bg-blue-50 text-blue-700 font-medium border border-blue-200"
                        : "text-gray-600 hover:bg-gray-100/80 hover:text-gray-900"
                    }`}
                  >
                    {isEditing ? (
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          handleRenameConversation(c.id, editingConvTitle);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="flex-1 min-w-0"
                      >
                        <input
                          type="text"
                          value={editingConvTitle}
                          onChange={(e) => setEditingConvTitle(e.target.value)}
                          autoFocus
                          onBlur={() => handleRenameConversation(c.id, editingConvTitle)}
                          className="w-full px-1.5 py-0.5 rounded bg-white border border-blue-500 text-[11px] text-gray-900 outline-none"
                        />
                      </form>
                    ) : (
                      <div className="flex items-center gap-2 truncate flex-1 min-w-0">
                        <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-60" />
                        <span className="truncate text-[11px]">{c.title}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-0.5 shrink-0">
                      {!isEditing && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingConvId(c.id);
                            setEditingConvTitle(c.title);
                          }}
                          className="opacity-0 group-hover:opacity-100 p-1 hover:text-blue-600 text-gray-400 transition cursor-pointer"
                          title="Rename chat"
                        >
                          <Edit2 className="w-3 h-3" />
                        </button>
                      )}
                      <button
                        onClick={async (e) => {
                          e.stopPropagation();
                          await api.deleteConversation(c.id);
                          setConversations((prev) => prev.filter((item) => item.id !== c.id));
                          if (activeConversation?.id === c.id) {
                            setActiveConversation(null);
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-600 text-gray-400 transition cursor-pointer"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Workspace Footer Info */}
        <div className="p-3 border-t border-gray-200 bg-white text-[10px] text-gray-500 flex items-center justify-between">
          <span className="truncate max-w-[140px]">{activeWorkspace?.tenant_name || "Workspace"}</span>
          <span className="font-mono text-blue-600 font-medium">Studio M06</span>
        </div>
      </div>

      {/* ================================================================= */}
      {/* 2. MAIN WORKSPACE / CHAT CONTAINER */}
      {/* ================================================================= */}
      <div className="flex-1 flex flex-col bg-white overflow-hidden relative">
        {activeAssistant ? (
          <>
            {/* Top Navigation & Mode Switcher Header */}
            <div className="p-3.5 px-6 border-b border-gray-200 bg-white flex items-center justify-between z-10">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold border border-blue-100">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold text-gray-900 tracking-tight">
                      {activeAssistant.name}
                    </h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-200 font-semibold">
                      v{activeAssistant.current_version_num || 1}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-100 text-gray-700 border border-gray-200">
                      {activeAssistant.llm_provider || "omniroute"} • {activeAssistant.default_model || "auto"}
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-500 mt-0.5 truncate max-w-md">
                    {activeAssistant.description || "Configurable Multi-Tenant Assistant"}
                  </p>
                </div>
              </div>

              {/* View Switcher: Studio Workspace vs Chat Sandbox */}
              <div className="flex items-center gap-3">
                <div className="flex items-center bg-gray-100 p-1 rounded-xl border border-gray-200">
                  <button
                    type="button"
                    onClick={() => setViewMode("workspace")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${
                      viewMode === "workspace"
                        ? "bg-white text-blue-600 font-semibold shadow-xs"
                        : "text-gray-600 hover:text-gray-900"
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
                        ? "bg-blue-600 text-white font-semibold shadow-xs"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Chat Sandbox</span>
                  </button>
                </div>

                <button
                  onClick={() => setShowWizard(true)}
                  className="px-3 py-1.5 rounded-xl bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-medium transition cursor-pointer flex items-center gap-1.5 shadow-xs"
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
              <div className="flex-1 flex flex-col overflow-hidden relative bg-gray-50/30">
                {/* Chat Messages Log */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  {messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto py-8">
                      <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-3 border border-blue-100">
                        <Sparkles className="w-6 h-6" />
                      </div>
                      <h3 className="text-sm font-bold text-gray-900">
                        Ready to chat with {activeAssistant.name}
                      </h3>
                      <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
                        Test questions grounded in connected knowledge bases. Responses follow strict
                        source citations and prompt trust guidelines.
                      </p>

                      <div className="w-full space-y-2 mt-6">
                        <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider text-left px-1">
                          Starter Prompts
                        </div>
                        {[
                          `What key knowledge and documents are loaded into ${activeAssistant.name}?`,
                          "Summarize the main topics and instructions you are configured to help with.",
                          "Provide a concrete example of how you extract information with verified citations.",
                        ].map((promptText, pIdx) => (
                          <button
                            key={pIdx}
                            type="button"
                            onClick={() => handleSendMessageWithText(promptText)}
                            className="w-full p-2.5 px-3 text-left rounded-xl bg-white hover:bg-gray-50 border border-gray-200 text-[11px] text-gray-800 hover:border-gray-300 transition cursor-pointer flex items-center justify-between group shadow-xs"
                          >
                            <span className="truncate pr-2">{promptText}</span>
                            <ChevronRight className="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-600 group-hover:translate-x-0.5 transition shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    messages.map((m, mIdx) => {
                      const isUser = m.sender_type === "user";
                      const isLatestAssistant =
                        !isUser &&
                        (mIdx === messages.length - 1 ||
                          (mIdx === messages.length - 2 && messages[messages.length - 1].sender_type === "user"));
                      return (
                        <div
                          key={m.id}
                          className={`flex flex-col ${
                            isUser ? "items-end" : "items-start"
                          } max-w-3xl mx-auto`}
                        >
                          <div className="flex items-center gap-2 mb-1 px-1">
                            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                              {isUser ? "You" : activeAssistant.name}
                            </span>
                            <span className="text-[9px] text-gray-400 font-mono">
                              {new Date(m.created_at).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </div>

                          <div
                            className={`p-4 rounded-2xl text-xs leading-relaxed max-w-2xl transition shadow-xs ${
                              isUser
                                ? "bg-blue-600 text-white rounded-br-sm"
                                : "bg-white border border-gray-200 text-gray-900 rounded-bl-sm"
                            }`}
                          >
                            <div className="font-sans">
                              {isUser || !m.citations || m.citations.length === 0 ? (
                                <p className="whitespace-pre-wrap">{m.content}</p>
                              ) : (
                                <MarkdownRenderer
                                  content={m.content}
                                  citations={m.citations}
                                  onCitationClick={(cit) => {
                                    setActiveCitation(cit);
                                    setCitationTab("visual");
                                  }}
                                  className="text-xs"
                                />
                              )}
                            </div>


                          </div>

                          {!isUser && m.content && (
                            <div className="flex items-center gap-3 mt-1.5 px-1 text-gray-400">
                              <button
                                onClick={() => handleCopy(m.id, m.content)}
                                className="hover:text-gray-600 transition text-[10px] flex items-center gap-1 cursor-pointer"
                              >
                                {copiedId === m.id ? (
                                  <>
                                    <Check className="w-3 h-3 text-blue-600" />
                                    <span className="text-blue-600 font-medium">Copied</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3 h-3" />
                                    <span>Copy</span>
                                  </>
                                )}
                              </button>
                              {isLatestAssistant && (
                                <button
                                  type="button"
                                  onClick={handleRegenerateResponse}
                                  disabled={streaming}
                                  className="hover:text-gray-600 transition text-[10px] flex items-center gap-1 cursor-pointer disabled:opacity-50"
                                  title="Regenerate response"
                                >
                                  <RotateCcw className="w-3 h-3" />
                                  <span>Retry</span>
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Box */}
                <div className="p-4 px-6 border-t border-gray-200 bg-white">
                  <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex gap-2">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder={`Ask ${activeAssistant.name} a test question...`}
                      disabled={streaming}
                      className="flex-1 px-4 py-3 rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 text-xs focus:border-blue-600 focus:bg-white outline-none transition disabled:opacity-50"
                    />

                    {streaming ? (
                      <button
                        type="button"
                        onClick={() => {
                          abortControllerRef.current?.abort();
                          setStreaming(false);
                        }}
                        className="px-4 py-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                      >
                        <Square className="w-3.5 h-3.5 fill-current" />
                        <span>Stop</span>
                      </button>
                    ) : (
                      <button
                        type="submit"
                        disabled={!inputMessage.trim()}
                        className="px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer disabled:opacity-50 shadow-sm"
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
            <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4 border border-blue-100">
              <Bot className="w-7 h-7" />
            </div>
            <h3 className="text-base font-bold text-gray-900">Welcome to Assistant Studio</h3>
            <p className="text-xs text-gray-500 mt-2 max-w-sm leading-relaxed">
              Create purpose-specific AI assistants with guided 5-step creation, safe instructions,
              version history, and optional knowledge integration.
            </p>
            <button
              onClick={() => setShowWizard(true)}
              className="mt-6 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition cursor-pointer flex items-center gap-2 shadow-sm"
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
          <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-3 md:p-6 overflow-y-auto animate-fadeIn">
            <div className="bg-white border border-gray-200 rounded-3xl max-w-4xl w-full shadow-2xl flex flex-col max-h-[92vh] overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 font-mono text-sm font-bold flex items-center justify-center shrink-0 border border-blue-200">
                    [{activeCitation.citation_num}]
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-gray-900 truncate">
                        {activeCitation.document_name}
                      </h3>
                      <span className="px-2 py-0.5 rounded-full bg-gray-100 text-[10px] font-mono text-gray-700 border border-gray-200">
                        Page {activeCitation.page_number || 1}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <div className="flex items-center bg-gray-100 p-1 rounded-xl border border-gray-200">
                    <button
                      type="button"
                      onClick={() => setCitationTab("visual")}
                      className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition cursor-pointer ${
                        citationTab === "visual"
                          ? "bg-white text-blue-600 font-semibold shadow-xs"
                          : "text-gray-600 hover:text-gray-900"
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
                          ? "bg-white text-blue-600 font-semibold shadow-xs"
                          : "text-gray-600 hover:text-gray-900"
                      }`}
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>Context & Text</span>
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => setActiveCitation(null)}
                    className="p-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-500 hover:text-gray-800 transition cursor-pointer"
                    title="Close"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="p-6 overflow-y-auto flex-1 bg-gray-50/50">
                {citationTab === "visual" ? (
                  <div className="flex flex-col items-center">
                    <div className="w-full max-w-2xl mb-3 flex items-center justify-between text-[11px] text-gray-500 px-2">
                      <div className="flex items-center gap-2">
                        <Layers className="w-3.5 h-3.5 text-blue-600" />
                        <span>Interactive PDF Viewport</span>
                      </div>
                      <div className="font-mono text-[10px]">
                        Page {activeCitation.page_number || 1}
                      </div>
                    </div>

                    <div className="relative w-full max-w-2xl bg-white border border-gray-200 rounded-2xl shadow-sm p-8 flex flex-col justify-between">
                      <p className="text-gray-900 text-xs leading-relaxed font-sans font-medium select-text">
                        &ldquo;{activeCitation.citation_text || activeCitation.snippet}&rdquo;
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4 max-w-2xl mx-auto">
                    <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
                      <div className="text-[11px] font-bold text-gray-500 mb-2 flex items-center justify-between">
                        <span>SOURCE EXCERPT</span>
                        <span className="font-mono text-blue-600">Page {activeCitation.page_number || 1}</span>
                      </div>
                      <div className="text-xs text-gray-900 leading-relaxed font-sans whitespace-pre-wrap select-text">
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
