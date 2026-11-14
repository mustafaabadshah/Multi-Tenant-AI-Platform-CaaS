"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  AssistantItem,
  ConversationItem,
  MessageItem,
  MessageCitationItem,
} from "@/lib/api";
import { dedupeCitations } from "@/lib/citations";
import {
  Bot,
  Plus,
  Send,
  Square,
  Trash2,
  FileText,
  MessageSquare,
  Copy,
  Check,
  Search,
  Edit2,
  X,
  ExternalLink,
  ChevronDown,
  Layers,
  Sparkles,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Spinner from "@/components/ui/Spinner";
import ConfirmModal from "@/components/ui/ConfirmModal";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import Badge from "@/components/ui/Badge";
import MarkdownRenderer from "@/components/chat/MarkdownRenderer";



export default function ConversationsWorkspacePage() {
  const { activeWorkspace } = useAuth();

  // State
  const [assistants, setAssistants] = useState<AssistantItem[]>([]);
  const [selectedAssistantFilter, setSelectedAssistantFilter] = useState<string>("ALL");
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConversation, setActiveConversation] = useState<ConversationItem | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [inputMessage, setInputMessage] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<MessageCitationItem[]>([]);
  const [loadingConvList, setLoadingConvList] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [creatingChat, setCreatingChat] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Rename & Delete state
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [deleteConfirmConv, setDeleteConfirmConv] = useState<ConversationItem | null>(null);
  const [deletingConv, setDeletingConv] = useState(false);

  // Citation inspection modal
  const [inspectCitation, setInspectCitation] = useState<MessageCitationItem | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 1. Fetch Assistants and Conversations on Workspace load
  useEffect(() => {
    async function init() {
      if (!activeWorkspace) return;
      try {
        setLoadingConvList(true);
        const [astList, convList] = await Promise.all([
          api.listAssistants(),
          api.listConversations(),
        ]);
        setAssistants(astList);
        setConversations(convList);
        if (convList.length > 0) {
          setActiveConversation(convList[0]);
        } else {
          setActiveConversation(null);
        }
      } catch (err) {
        console.error("Failed to load conversations or assistants", err);
      } finally {
        setLoadingConvList(false);
      }
    }
    init();
  }, [activeWorkspace]);

  // 2. Fetch Messages when active conversation changes
  useEffect(() => {
    async function loadConvMessages() {
      if (!activeConversation) {
        setMessages([]);
        return;
      }
      try {
        setLoadingMessages(true);
        setErrorMessage(null);
        const msgList = await api.listMessages(activeConversation.id);
        setMessages(msgList);
      } catch (err) {
        console.error("Failed to load messages", err);
        setErrorMessage("Failed to load message history for this conversation.");
      } finally {
        setLoadingMessages(false);
      }
    }
    loadConvMessages();
  }, [activeConversation]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Active assistant mapping
  const activeAssistant = useMemo(() => {
    if (!activeConversation) return null;
    return assistants.find((a) => a.id === activeConversation.assistant_id) || null;
  }, [activeConversation, assistants]);

  // Filtered conversations
  const filteredConversations = useMemo(() => {
    return conversations.filter((c) => {
      const matchesSearch = c.title.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesAssistant =
        selectedAssistantFilter === "ALL" || c.assistant_id === selectedAssistantFilter;
      return matchesSearch && matchesAssistant;
    });
  }, [conversations, searchQuery, selectedAssistantFilter]);

  // Create new conversation
  const handleCreateNewChat = async (targetAssistantId?: string) => {
    const astId =
      targetAssistantId ||
      (selectedAssistantFilter !== "ALL" ? selectedAssistantFilter : assistants[0]?.id);

    if (!astId) {
      alert("Please create at least one assistant first.");
      return;
    }

    try {
      setCreatingChat(true);
      const newConv = await api.createConversation({
        assistant_id: astId,
        title: "New Conversation",
      });
      setConversations((prev) => [newConv, ...prev]);
      setActiveConversation(newConv);
    } catch (err) {
      console.error("Failed to create conversation", err);
    } finally {
      setCreatingChat(false);
    }
  };

  // Rename conversation
  const handleRenameSave = async (convId: string) => {
    if (!renameTitle.trim()) {
      setEditingConvId(null);
      return;
    }
    try {
      const updated = await api.updateConversation(convId, { title: renameTitle.trim() });
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

  // Delete conversation
  const handleDeleteConversation = async () => {
    if (!deleteConfirmConv) return;
    try {
      setDeletingConv(true);
      await api.deleteConversation(deleteConfirmConv.id);
      const remaining = conversations.filter((c) => c.id !== deleteConfirmConv.id);
      setConversations(remaining);
      if (activeConversation?.id === deleteConfirmConv.id) {
        setActiveConversation(remaining[0] || null);
      }
      setDeleteConfirmConv(null);
    } catch (err) {
      console.error("Failed to delete conversation", err);
    } finally {
      setDeletingConv(false);
    }
  };

  // Send Message & Stream SSE response
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputMessage.trim() || streaming) return;

    let conv = activeConversation;
    if (!conv) {
      // Auto-create conversation with first assistant
      if (assistants.length === 0) {
        alert("Please create an assistant first.");
        return;
      }
      try {
        conv = await api.createConversation({
          assistant_id: assistants[0].id,
          title: inputMessage.slice(0, 30) + (inputMessage.length > 30 ? "..." : ""),
        });
        setConversations((prev) => [conv!, ...prev]);
        setActiveConversation(conv);
      } catch (err) {
        console.error("Failed to auto-create conversation", err);
        return;
      }
    }

    const userPrompt = inputMessage.trim();
    setInputMessage("");

    // Optimistically push user message
    const tempUserMsg: MessageItem = {
      id: "temp-user-" + Date.now(),
      conversation_id: conv.id,
      sender_type: "user",
      content: userPrompt,
      token_count: Math.ceil(userPrompt.length / 4),
      created_at: new Date().toISOString(),
      citations: [],
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    // Initialize streaming
    setStreaming(true);
    setStreamingContent("");
    setStreamingCitations([]);
    setErrorMessage(null);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    let accumulatedText = "";
    let accumulatedCitations: MessageCitationItem[] = [];

    try {
      const token = api.getToken() || "";
      const tenantId = activeWorkspace?.tenant_id || api.getActiveTenantId() || "";
      const response = await fetch(
        `${api.getApiV1()}/conversations/${conv.id}/messages/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
            "X-Tenant-ID": tenantId,
          },
          body: JSON.stringify({ content: userPrompt }),
          signal: abortController.signal,
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body available for streaming");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          const eventMatch = line.match(/^event:\s*(\w+)/m);
          const dataMatch = line.match(/^data:\s*(.*)$/m);

          if (eventMatch && dataMatch) {
            const eventType = eventMatch[1];
            try {
              const data = JSON.parse(dataMatch[1]);
              if (eventType === "token") {
                accumulatedText += data.delta ?? data.token ?? "";
                setStreamingContent(accumulatedText);
              } else if (eventType === "citation" || eventType === "retrieval_complete") {
                if (data.citations && Array.isArray(data.citations)) {
                  accumulatedCitations = dedupeCitations(accumulatedCitations, data.citations);
                } else if (data.document_name) {
                  accumulatedCitations = dedupeCitations(accumulatedCitations, [data]);
                }
                setStreamingCitations([...accumulatedCitations]);
              } else if (eventType === "message_end") {
                // Completed
              } else if (eventType === "message_error") {
                setErrorMessage(data.error || "Generation error");
              }
            } catch {
              // Non-JSON SSE payload
            }
          }
        }
      }

      // Finalize assistant message into list
      if (accumulatedText.trim()) {
        const finalAssistantMsg: MessageItem = {
          id: "asst-" + Date.now(),
          conversation_id: conv.id,
          sender_type: "assistant",
          content: accumulatedText,
          token_count: Math.ceil(accumulatedText.length / 4),
          created_at: new Date().toISOString(),
          citations: accumulatedCitations,
        };
        setMessages((prev) => [...prev, finalAssistantMsg]);
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        console.error("Stream failed", err);
        let msg = err.message || "Failed to stream assistant response.";
        if (msg.includes("Authentication token required") || msg.includes("401")) {
          msg = "Your authentication session has expired. Please refresh the page or sign in again.";
        }
        setErrorMessage(msg);
      }
    } finally {
      setStreaming(false);
      setStreamingContent("");
      setStreamingCitations([]);
      abortControllerRef.current = null;
      // Reload actual persisted messages from backend database to ensure consistency
      if (conv?.id) {
        try {
          const freshMessages = await api.listMessages(conv.id);
          setMessages(freshMessages);
        } catch (e) {
          console.warn("Failed to refresh messages after stream:", e);
        }
      }
      try {
        const freshConvs = await api.listConversations();
        setConversations(freshConvs);
      } catch (e) {
        console.warn("Failed to refresh conversations:", e);
      }
    }
  };

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setStreaming(false);
      if (streamingContent.trim() && activeConversation) {
        const stoppedMsg: MessageItem = {
          id: "asst-stopped-" + Date.now(),
          conversation_id: activeConversation.id,
          sender_type: "assistant",
          content: streamingContent + " [Stopped by user]",
          token_count: Math.ceil(streamingContent.length / 4),
          created_at: new Date().toISOString(),
          citations: streamingCitations,
        };
        setMessages((prev) => [...prev, stoppedMsg]);
      }
      setStreamingContent("");
      setStreamingCitations([]);
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex rounded-xl border border-gray-200 bg-white overflow-hidden shadow-xs">
      {/* 1. LEFT PANE: Conversation History & Assistant Selector */}
      <div className="w-80 border-r border-gray-200 flex flex-col bg-gray-50/60 shrink-0">
        {/* Top Action Bar */}
        <div className="p-3 border-b border-gray-200 bg-white space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <MessageSquare size={16} className="text-blue-600" />
              <span>Conversations</span>
            </h2>
            <Button
              variant="primary"
              size="xs"
              icon={Plus}
              onClick={() => handleCreateNewChat()}
              isLoading={creatingChat}
            >
              New Chat
            </Button>
          </div>

          {/* Assistant Filter Dropdown */}
          <div className="relative">
            <select
              value={selectedAssistantFilter}
              onChange={(e) => setSelectedAssistantFilter(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs bg-white border border-gray-300 rounded-lg text-gray-800 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600"
            >
              <option value="ALL">All Assistants ({assistants.length})</option>
              {assistants.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.llm_provider || "auto"})
                </option>
              ))}
            </select>
          </div>

          {/* Search Box */}
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600"
            />
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loadingConvList ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <Spinner size="md" />
              <p className="text-xs mt-2">Loading chats...</p>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="text-center py-10 px-3">
              <MessageSquare size={28} className="mx-auto mb-2 text-gray-300" />
              <p className="text-xs text-gray-500 font-medium">No conversations found</p>
              <p className="text-[11px] text-gray-400 mt-1">Start a new chat to begin prompting.</p>
            </div>
          ) : (
            filteredConversations.map((conv) => {
              const isSelected = activeConversation?.id === conv.id;
              const convAssistant = assistants.find((a) => a.id === conv.assistant_id);

              return (
                <div
                  key={conv.id}
                  onClick={() => setActiveConversation(conv)}
                  className={`group relative p-2.5 rounded-lg border text-left transition-colors cursor-pointer ${
                    isSelected
                      ? "bg-white border-blue-500 shadow-xs ring-1 ring-blue-500/20"
                      : "bg-white/70 border-gray-200 hover:bg-white hover:border-gray-300"
                  }`}
                >
                  <div className="flex items-start justify-between gap-1">
                    {editingConvId === conv.id ? (
                      <input
                        type="text"
                        autoFocus
                        value={renameTitle}
                        onChange={(e) => setRenameTitle(e.target.value)}
                        onBlur={() => handleRenameSave(conv.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleRenameSave(conv.id);
                          if (e.key === "Escape") setEditingConvId(null);
                        }}
                        className="w-full text-xs font-medium text-gray-900 border border-blue-500 rounded px-1 py-0.5 outline-none"
                      />
                    ) : (
                      <h4
                        className={`text-xs font-medium truncate ${
                          isSelected ? "text-blue-700" : "text-gray-900"
                        }`}
                      >
                        {conv.title}
                      </h4>
                    )}

                    {/* Quick hover actions */}
                    <div className="hidden group-hover:flex items-center gap-0.5 shrink-0 bg-white/90 pl-1">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingConvId(conv.id);
                          setRenameTitle(conv.title);
                        }}
                        title="Rename"
                        className="p-1 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100"
                      >
                        <Edit2 size={12} />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteConfirmConv(conv);
                        }}
                        title="Delete"
                        className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-gray-400 mt-1">
                    <span className="truncate max-w-[120px]">
                      {convAssistant?.name || "Assistant"}
                    </span>
                    <span>
                      {new Date(conv.updated_at || conv.created_at).toLocaleDateString([], {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 2. RIGHT PANE: First-Class Active Chat Canvas */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        {activeConversation ? (
          <>
            {/* Chat Top Header */}
            <div className="h-14 px-6 border-b border-gray-200 flex items-center justify-between bg-white shrink-0">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center shrink-0">
                  <Bot size={18} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900 truncate">
                      {activeAssistant?.name || "AI Assistant"}
                    </h3>
                    <Badge variant="blue" size="xs">
                      {activeAssistant?.llm_provider || "omniroute"}
                    </Badge>
                  </div>
                  <p className="text-xs text-gray-400 truncate max-w-md">
                    {activeConversation.title}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="xs"
                  icon={Trash2}
                  onClick={() => setDeleteConfirmConv(activeConversation)}
                  title="Clear or delete conversation"
                >
                  Delete
                </Button>
              </div>
            </div>

            {/* Error Banner */}
            {errorMessage && (
              <div className="px-6 py-2.5 bg-red-50 border-b border-red-200 text-xs text-red-700 flex items-center justify-between">
                <span>{errorMessage}</span>
                <button
                  type="button"
                  onClick={() => setErrorMessage(null)}
                  className="text-red-500 hover:text-red-700"
                >
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Message Thread History */}
            <div className="flex-1 p-6 overflow-y-auto space-y-5">
              {loadingMessages ? (
                <div className="flex items-center justify-center py-20 text-gray-400">
                  <Spinner size="md" />
                </div>
              ) : messages.length === 0 && !streaming ? (
                <div className="text-center py-24 max-w-md mx-auto">
                  <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-3">
                    <Bot size={24} />
                  </div>
                  <h4 className="text-base font-semibold text-gray-900 mb-1">
                    Ready to assist
                  </h4>
                  <p className="text-xs text-gray-500 mb-4">
                    Send a question to begin. Responses will ground automatically in connected tenant knowledge bases with provenance citations.
                  </p>
                </div>
              ) : (
                messages.map((msg) => {
                  const isUser = msg.sender_type === "user";
                  return (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                    >
                      <div className="flex items-center gap-2 mb-1 px-1">
                        <span className="text-[11px] font-medium text-gray-400">
                          {isUser ? "You" : activeAssistant?.name || "Assistant"}
                        </span>
                        <span className="text-[10px] text-gray-300">
                          {new Date(msg.created_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>

                      <div
                        className={`rounded-2xl px-4 py-3 text-sm leading-relaxed max-w-2xl ${
                          isUser
                            ? "bg-blue-600 text-white rounded-tr-none shadow-xs"
                            : "bg-gray-50 border border-gray-200 text-gray-900 rounded-tl-none shadow-xs"
                        }`}
                      >
                        {isUser ? (
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        ) : (
                          <MarkdownRenderer
                            content={msg.content}
                            citations={msg.citations}
                            onCitationClick={(cit) => setInspectCitation(cit)}
                            className="text-sm"
                          />
                        )}
                      </div>

                      {/* References Tray for Assistant */}
                      {!isUser && msg.citations && msg.citations.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-center gap-1.5 px-1 max-w-2xl">
                          <span className="text-[10px] uppercase font-semibold text-gray-400 mr-1">
                            Sources:
                          </span>
                          {msg.citations.map((c) => (
                            <button
                              key={c.id || c.citation_num}
                              type="button"
                              onClick={() => setInspectCitation(c)}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-medium transition-colors cursor-pointer"
                            >
                              <FileText size={11} className="text-gray-500" />
                              <span className="truncate max-w-[120px]">
                                {c.document_name || "Document"}
                              </span>
                              <span className="text-[10px] text-gray-400">
                                p.{c.page_number || 1}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })
              )}

              {/* Live Streaming Message Bubble */}
              {streaming && (
                <div className="flex flex-col items-start animate-fadeIn">
                  <div className="flex items-center gap-2 mb-1 px-1">
                    <span className="text-[11px] font-medium text-gray-400">
                      {activeAssistant?.name || "Assistant"}
                    </span>
                    <span className="text-[10px] text-blue-600 font-medium animate-pulse">
                      Generating...
                    </span>
                  </div>

                  <div className="rounded-2xl rounded-tl-none px-4 py-3 text-sm bg-gray-50 border border-blue-200 text-gray-900 shadow-xs max-w-2xl">
                    <MarkdownRenderer
                      content={streamingContent || ""}
                      citations={streamingCitations}
                      onCitationClick={(cit) => setInspectCitation(cit)}
                      className="text-sm"
                    />
                    {!streamingContent && (
                      <span className="text-gray-400 italic text-xs">Thinking...</span>
                    )}
                    <span className="inline-block w-1.5 h-4 ml-1 bg-blue-600 animate-pulse align-middle" />
                  </div>

                  {streamingCitations.length > 0 && (
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 px-1">
                      <span className="text-[10px] uppercase font-semibold text-gray-400 mr-1">
                        Discovered Sources:
                      </span>
                      {streamingCitations.map((c, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs"
                        >
                          <FileText size={11} />
                          <span>{c.document_name}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Bottom Input Area */}
            <div className="p-4 border-t border-gray-200 bg-white">
              <form onSubmit={handleSendMessage} className="space-y-2">
                <div className="relative flex items-center">
                  <textarea
                    rows={1}
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    placeholder={`Message ${activeAssistant?.name || "Assistant"}...`}
                    disabled={streaming}
                    className="w-full resize-none pl-4 pr-24 py-2.5 text-sm bg-gray-50 border border-gray-300 rounded-xl text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-500/20"
                  />

                  <div className="absolute right-2 flex items-center gap-1">
                    {streaming ? (
                      <Button
                        type="button"
                        variant="danger"
                        size="xs"
                        icon={Square}
                        onClick={handleStopStreaming}
                      >
                        Stop
                      </Button>
                    ) : (
                      <Button
                        type="submit"
                        variant="primary"
                        size="xs"
                        icon={Send}
                        disabled={!inputMessage.trim()}
                      >
                        Send
                      </Button>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-gray-400 px-1">
                  <span>Enter to send · Shift+Enter for new line</span>
                  <span className="flex items-center gap-1 text-gray-500">
                    <Sparkles size={12} className="text-blue-500" />
                    <span>Multi-Tenant RAG Grounded</span>
                  </span>
                </div>
              </form>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center p-8">
            <EmptyState
              icon={MessageSquare}
              title="No Conversation Selected"
              description="Choose a conversation from the sidebar or start a new chat with one of your assistants."
              action={{
                label: "Start New Chat",
                onClick: () => handleCreateNewChat(),
                icon: Plus,
              }}
            />
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirmConv && (
        <ConfirmModal
          isOpen={true}
          onClose={() => setDeleteConfirmConv(null)}
          onConfirm={handleDeleteConversation}
          title="Delete Conversation"
          message={`Are you sure you want to delete "${deleteConfirmConv.title}"? All message history will be removed.`}
          confirmText="Delete Chat"
          cancelText="Cancel"
          variant="danger"
          isLoading={deletingConv}
        />
      )}

      {/* Citation Inspection Modal */}
      {inspectCitation && (
        <Modal
          isOpen={true}
          onClose={() => setInspectCitation(null)}
          title={`Citation [${inspectCitation.citation_num}]: ${inspectCitation.document_name || "Document"}`}
          description={`Page ${inspectCitation.page_number || 1} · Verified Chunk Reference`}
          maxWidth="lg"
        >
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <h5 className="text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">
                Referenced Excerpt
              </h5>
              <p className="text-xs text-gray-800 leading-relaxed font-mono whitespace-pre-wrap">
                {inspectCitation.citation_text || inspectCitation.snippet || "No text available"}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
              <div>
                <span className="font-semibold block text-gray-700">Source Document:</span>
                <span>{inspectCitation.document_name}</span>
              </div>
              <div>
                <span className="font-semibold block text-gray-700">Page Reference:</span>
                <span>Page {inspectCitation.page_number || 1}</span>
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-gray-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setInspectCitation(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
