"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  AssistantItem,
  ConversationItem,
  MessageItem,
  MessageCitationItem,
  ToolApprovalItem,
  ConversationAttachmentItem,
  KnowledgeBaseItem,
  VoicePreferenceItem,
} from "@/lib/api";
import { dedupeCitations } from "@/lib/citations";
import {
  BrowserSpeechRecognizer,
  BrowserSpeechSynthesizer,
  VoiceMode,
  cleanTextForSpeech,
} from "@/lib/speech";
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
  ShieldAlert,
  Paperclip,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Bookmark,
  Upload,
  AlertCircle,
  FileUp,
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
  const { user, activeWorkspace } = useAuth();

  // Core State
  const [assistants, setAssistants] = useState<AssistantItem[]>([]);
  const [selectedAssistantFilter, setSelectedAssistantFilter] = useState<string>("ALL");
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConversation, setActiveConversation] = useState<ConversationItem | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ToolApprovalItem[]>([]);
  const [approvingIds, setApprovingIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [inputMessage, setInputMessage] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<MessageCitationItem[]>([]);
  const [loadingConvList, setLoadingConvList] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [creatingChat, setCreatingChat] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // M22: Attachments State
  const [attachments, setAttachments] = useState<ConversationAttachmentItem[]>([]);
  const [loadingAttachments, setLoadingAttachments] = useState(false);
  const [uploadingAttachment, setUploadingAttachment] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseItem[]>([]);
  const [promoteAttachment, setPromoteAttachment] = useState<ConversationAttachmentItem | null>(null);
  const [targetKbId, setTargetKbId] = useState<string>("");
  const [promoteTitle, setPromoteTitle] = useState<string>("");
  const [isPromoting, setIsPromoting] = useState(false);

  // M23 & M24: Speech & Voice State
  const [voiceMode, setVoiceMode] = useState<VoiceMode>("TEXT");
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const [speechError, setSpeechError] = useState<string | null>(null);

  // Rename & Delete state
  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [deleteConfirmConv, setDeleteConfirmConv] = useState<ConversationItem | null>(null);
  const [deletingConv, setDeletingConv] = useState(false);

  // Citation inspection modal
  const [inspectCitation, setInspectCitation] = useState<MessageCitationItem | null>(null);

  // Refs
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const speechRecognizerRef = useRef<BrowserSpeechRecognizer | null>(null);
  const speechSynthesizerRef = useRef<BrowserSpeechSynthesizer | null>(null);
  const voiceModeRef = useRef<VoiceMode>(voiceMode);
  voiceModeRef.current = voiceMode;
  const isSubmittingVoiceRef = useRef<boolean>(false);

  // 1. Initialize Speech Engines
  useEffect(() => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    const synthesizer = new BrowserSpeechSynthesizer();

    recognizer.onStateChange((listening) => {
      setIsListening(listening);
      if (!listening) {
        setSpeechError(null);
      }
    });

    recognizer.onError((err) => {
      setSpeechError(err);
      setIsListening(false);
    });

    synthesizer.onSpeakingChange((speaking) => {
      setIsSpeaking(speaking);
      if (!speaking) {
        setSpeakingMsgId(null);
      }
    });

    speechRecognizerRef.current = recognizer;
    speechSynthesizerRef.current = synthesizer;

    // Load user voice preferences if available
    api.getVoicePreferences()
      .then((pref) => {
        if (pref?.voice_mode) {
          setVoiceMode(pref.voice_mode as VoiceMode);
        }
      })
      .catch(() => {});

    return () => {
      recognizer.abort();
      synthesizer.cancel();
      isSubmittingVoiceRef.current = false;
    };
  }, []);

  // 2. Fetch Assistants, Knowledge Bases, and Conversations on Workspace load
  useEffect(() => {
    async function init() {
      if (!activeWorkspace) return;
      try {
        setLoadingConvList(true);
        const [astList, convList, kbList] = await Promise.all([
          api.listAssistants(),
          api.listConversations(),
          api.listKnowledgeBases().catch(() => []),
        ]);
        setAssistants(astList);
        setConversations(convList);
        setKnowledgeBases(kbList);
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

  // 3. Fetch Messages & Attachments when active conversation changes
  useEffect(() => {
    // Stop ongoing speech on conversation switch
    speechSynthesizerRef.current?.cancel();
    speechRecognizerRef.current?.stop();
    setIsSpeaking(false);
    setIsListening(false);
    setSpeakingMsgId(null);
    isSubmittingVoiceRef.current = false;

    async function loadConvData() {
      if (!activeConversation) {
        setMessages([]);
        setPendingApprovals([]);
        setAttachments([]);
        return;
      }
      try {
        setLoadingMessages(true);
        setLoadingAttachments(true);
        setErrorMessage(null);

        const [msgList, apprs, atts] = await Promise.all([
          api.listMessages(activeConversation.id),
          api.listPendingApprovals(activeConversation.id).catch(() => []),
          api.listConversationAttachments(activeConversation.id).catch(() => []),
        ]);

        setMessages(msgList);
        setPendingApprovals(apprs || []);
        setAttachments(atts || []);
      } catch (err) {
        console.error("Failed to load conversation details", err);
        setErrorMessage("Failed to load details for this conversation.");
      } finally {
        setLoadingMessages(false);
        setLoadingAttachments(false);
      }
    }
    loadConvData();
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

  // Setup recognizer transcript callback
  useEffect(() => {
    if (!speechRecognizerRef.current) return;
    speechRecognizerRef.current.onTranscript((transcript: string, isFinal: boolean) => {
      if (voiceModeRef.current === "DICTATION") {
        setInputMessage(transcript);
      } else if (voiceModeRef.current === "VOICE_CONVERSATION") {
        setInputMessage(transcript);
        if (isFinal && transcript.trim() && !isSubmittingVoiceRef.current && !streaming) {
          isSubmittingVoiceRef.current = true;
          speechRecognizerRef.current?.stop();
          handleSendMessageWithText(transcript.trim()).finally(() => {
            isSubmittingVoiceRef.current = false;
          });
        }
      }
    });
  }, [streaming]);

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
      setConversations((prev) => prev.map((c) => (c.id === convId ? updated : c)));
      if (activeConversation?.id === convId) {
        setActiveConversation(updated);
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

  // M22: File Upload Handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !activeConversation) return;

    const file = files[0];
    try {
      setUploadingAttachment(true);
      setErrorMessage(null);
      const created = await api.uploadConversationAttachment(activeConversation.id, file);
      setAttachments((prev) => [created, ...prev]);
    } catch (err: any) {
      console.error("Failed to upload conversation attachment", err);
      setErrorMessage(err.message || "Failed to upload document.");
    } finally {
      setUploadingAttachment(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  // M22: Delete Attachment Handler
  const handleDeleteAttachment = async (attachmentId: string) => {
    if (!activeConversation) return;
    try {
      await api.deleteConversationAttachment(activeConversation.id, attachmentId);
      setAttachments((prev) => prev.filter((a) => a.id !== attachmentId));
    } catch (err) {
      console.error("Failed to delete attachment", err);
    }
  };

  // M22: Promote Attachment Handler
  const handlePromoteAttachment = async () => {
    if (!activeConversation || !promoteAttachment || !targetKbId) return;
    try {
      setIsPromoting(true);
      const res = await api.promoteConversationAttachment(
        activeConversation.id,
        promoteAttachment.id,
        targetKbId,
        promoteTitle.trim() || undefined
      );
      setAttachments((prev) =>
        prev.map((a) =>
          a.id === promoteAttachment.id
            ? {
                ...a,
                is_promoted: true,
                promoted_knowledge_base_id: res.knowledge_base_id,
                promoted_document_id: res.document_id,
                promoted_at: res.promoted_at,
              }
            : a
        )
      );
      setPromoteAttachment(null);
      setTargetKbId("");
      setPromoteTitle("");
    } catch (err: any) {
      console.error("Failed to promote attachment", err);
      setErrorMessage(err.message || "Failed to promote document to Knowledge Base.");
    } finally {
      setIsPromoting(false);
    }
  };

  // M23 & M24: Toggle Microphone
  const handleToggleMic = () => {
    if (!speechRecognizerRef.current) return;
    if (isListening) {
      speechRecognizerRef.current.stop();
    } else {
      setSpeechError(null);
      speechRecognizerRef.current.start();
    }
  };

  // M23: Speak individual assistant message
  const handleToggleSpeakMessage = (msgId: string, text: string) => {
    const synthesizer = speechSynthesizerRef.current;
    if (!synthesizer) return;

    if (speakingMsgId === msgId && isSpeaking) {
      synthesizer.cancel();
      setSpeakingMsgId(null);
      return;
    }

    setSpeakingMsgId(msgId);
    synthesizer.speak(text, {
      onEnd: () => {
        setSpeakingMsgId(null);
      },
      onError: () => {
        setSpeakingMsgId(null);
      },
    });
  };

  // M23: Stop Speech
  const handleStopSpeaking = () => {
    speechSynthesizerRef.current?.cancel();
    setIsSpeaking(false);
    setSpeakingMsgId(null);
  };

  // Core Send & Stream SSE response with text parameter support
  const handleSendMessageWithText = async (customPrompt?: string) => {
    const textToSend = (customPrompt ?? inputMessage).trim();
    if (!textToSend || streaming) return;

    let conv = activeConversation;
    if (!conv) {
      if (assistants.length === 0) {
        alert("Please create an assistant first.");
        return;
      }
      try {
        conv = await api.createConversation({
          assistant_id: assistants[0].id,
          title: textToSend.slice(0, 30) + (textToSend.length > 30 ? "..." : ""),
        });
        setConversations((prev) => [conv!, ...prev]);
        setActiveConversation(conv);
      } catch (err) {
        console.error("Failed to auto-create conversation", err);
        return;
      }
    }

    setInputMessage("");

    // Optimistically push user message
    const tempUserMsg: MessageItem = {
      id: "temp-user-" + Date.now(),
      conversation_id: conv.id,
      sender_type: "user",
      content: textToSend,
      token_count: Math.ceil(textToSend.length / 4),
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
          body: JSON.stringify({ content: textToSend }),
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
              } else if (eventType === "tool_approval_required") {
                const approvalItem: ToolApprovalItem = {
                  id: data.approval_id,
                  tenant_id: activeWorkspace?.tenant_id || "",
                  conversation_id: conv.id,
                  assistant_id: conv.assistant_id,
                  user_id: user?.id || "",
                  tool_id: data.tool_id || data.tool_name,
                  tool_name: data.tool_name,
                  call_arguments: data.arguments || {},
                  status: "PENDING",
                  approval_token: data.token,
                  expires_at: data.expires_at || new Date(Date.now() + 600000).toISOString(),
                  created_at: new Date().toISOString(),
                };
                setPendingApprovals((prev) => {
                  const exists = prev.some((a) => a.id === approvalItem.id);
                  return exists ? prev : [...prev, approvalItem];
                });
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

        // M24: Automated TTS in LISTEN or VOICE_CONVERSATION modes
        const currentMode = voiceModeRef.current;
        if (currentMode === "LISTEN" || currentMode === "VOICE_CONVERSATION") {
          // Explicitly stop microphone to prevent acoustic feedback loop
          speechRecognizerRef.current?.stop();
          setIsListening(false);
          speechSynthesizerRef.current?.speak(accumulatedText, {
            onEnd: () => {
              setIsSpeaking(false);
              setSpeakingMsgId(null);
              // In Voice Conversation mode: if no pending approvals are blocking, resume listening
              if (voiceModeRef.current === "VOICE_CONVERSATION" && pendingApprovals.length === 0) {
                speechRecognizerRef.current?.start();
              }
            },
            onError: () => {
              setIsSpeaking(false);
              setSpeakingMsgId(null);
            },
          });
        }
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

      if (conv?.id) {
        try {
          const [freshMessages, freshApprs] = await Promise.all([
            api.listMessages(conv.id),
            api.listPendingApprovals(conv.id).catch(() => []),
          ]);
          setMessages(freshMessages);
          setPendingApprovals(freshApprs || []);
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

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    await handleSendMessageWithText();
  };

  const handleApproveTool = async (approval: ToolApprovalItem) => {
    setApprovingIds((prev) => new Set(prev).add(approval.id));
    try {
      await api.approveTool(approval.id, approval.approval_token || "");
      setPendingApprovals((prev) => prev.filter((a) => a.id !== approval.id));
      if (activeConversation) {
        const fresh = await api.listMessages(activeConversation.id);
        setMessages(fresh);
      }
    } catch (err: any) {
      console.error("Failed to approve tool execution", err);
      alert(`Approval execution failed: ${err.message}`);
    } finally {
      setApprovingIds((prev) => {
        const next = new Set(prev);
        next.delete(approval.id);
        return next;
      });
    }
  };

  const handleDenyTool = async (approval: ToolApprovalItem) => {
    try {
      await api.denyTool(approval.id);
      setPendingApprovals((prev) => prev.filter((a) => a.id !== approval.id));
    } catch (err: any) {
      console.error("Failed to deny tool", err);
    }
  };

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    speechSynthesizerRef.current?.cancel();
    setStreaming(false);
    isSubmittingVoiceRef.current = false;
  };

  // Change Voice Mode
  const handleSelectVoiceMode = (mode: VoiceMode) => {
    setVoiceMode(mode);
    isSubmittingVoiceRef.current = false;
    if (mode === "TEXT") {
      speechRecognizerRef.current?.stop();
      speechSynthesizerRef.current?.cancel();
    } else if (mode === "VOICE_CONVERSATION") {
      speechRecognizerRef.current?.start();
    }
    api.updateVoicePreferences({ voice_mode: mode }).catch(() => {});
  };

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-white">
      {/* 1. LEFT SIDEBAR: Conversations List */}
      <div className="w-80 border-r border-gray-200 flex flex-col bg-gray-50/50 shrink-0">
        <div className="p-4 border-b border-gray-200 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <MessageSquare size={16} className="text-blue-600" />
              <span>Chats</span>
            </h2>
            <Button
              variant="primary"
              size="xs"
              icon={Plus}
              onClick={() => handleCreateNewChat()}
              disabled={creatingChat || assistants.length === 0}
            >
              New Chat
            </Button>
          </div>

          {/* Assistant Filter Dropdown */}
          <div className="relative">
            <select
              value={selectedAssistantFilter}
              onChange={(e) => setSelectedAssistantFilter(e.target.value)}
              className="w-full text-xs bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 text-gray-700 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-medium appearance-none cursor-pointer pr-7"
            >
              <option value="ALL">All Assistants ({assistants.length})</option>
              {assistants.map((ast) => (
                <option key={ast.id} value={ast.id}>
                  {ast.name} ({ast.llm_provider})
                </option>
              ))}
            </select>
            <ChevronDown
              size={13}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
            />
          </div>

          {/* Search Box */}
          <div className="relative">
            <Search
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              placeholder="Filter chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg text-gray-900 placeholder:text-gray-400 outline-none focus:border-blue-500"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X size={12} />
              </button>
            )}
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loadingConvList ? (
            <div className="py-8 flex justify-center">
              <Spinner size="sm" />
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="text-center py-8 px-4">
              <p className="text-xs text-gray-400">No conversations found.</p>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => handleCreateNewChat()}
                className="mt-2 text-blue-600"
              >
                Start your first chat
              </Button>
            </div>
          ) : (
            filteredConversations.map((conv) => {
              const isSelected = activeConversation?.id === conv.id;
              const isEditing = editingConvId === conv.id;
              const convAssistant = assistants.find((a) => a.id === conv.assistant_id);

              return (
                <div
                  key={conv.id}
                  onClick={() => setActiveConversation(conv)}
                  className={`group relative flex flex-col p-2.5 rounded-xl text-left transition-all cursor-pointer border ${
                    isSelected
                      ? "bg-white border-blue-500 shadow-xs"
                      : "bg-transparent border-transparent hover:bg-white/80 hover:border-gray-200"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1">
                    {isEditing ? (
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

      {/* 2. RIGHT PANE: Chat Canvas */}
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

              {/* Mode Selector & Action Buttons */}
              <div className="flex items-center gap-2">
                {/* Voice Mode Selector */}
                <div className="flex items-center p-0.5 rounded-lg bg-gray-100 border border-gray-200 text-xs">
                  <button
                    type="button"
                    onClick={() => handleSelectVoiceMode("TEXT")}
                    className={`px-2 py-1 rounded-md font-medium transition-colors flex items-center gap-1 ${
                      voiceMode === "TEXT"
                        ? "bg-white text-gray-900 shadow-xs"
                        : "text-gray-500 hover:text-gray-900"
                    }`}
                    title="Text Mode: keyboard input and text responses"
                  >
                    <MessageSquare size={13} />
                    <span className="hidden sm:inline">Text</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSelectVoiceMode("DICTATION")}
                    className={`px-2 py-1 rounded-md font-medium transition-colors flex items-center gap-1 ${
                      voiceMode === "DICTATION"
                        ? "bg-white text-blue-600 shadow-xs"
                        : "text-gray-500 hover:text-gray-900"
                    }`}
                    title="Dictation Mode: microphone to editable text"
                  >
                    <Mic size={13} />
                    <span className="hidden sm:inline">Dictate</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSelectVoiceMode("LISTEN")}
                    className={`px-2 py-1 rounded-md font-medium transition-colors flex items-center gap-1 ${
                      voiceMode === "LISTEN"
                        ? "bg-white text-emerald-600 shadow-xs"
                        : "text-gray-500 hover:text-gray-900"
                    }`}
                    title="Listen Mode: answers read aloud with TTS"
                  >
                    <Volume2 size={13} />
                    <span className="hidden sm:inline">Listen</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSelectVoiceMode("VOICE_CONVERSATION")}
                    className={`px-2 py-1 rounded-md font-medium transition-colors flex items-center gap-1 ${
                      voiceMode === "VOICE_CONVERSATION"
                        ? "bg-white text-purple-600 shadow-xs font-semibold"
                        : "text-gray-500 hover:text-gray-900"
                    }`}
                    title="Voice Conversation Mode: voice input and spoken answers"
                  >
                    <Sparkles size={13} />
                    <span className="hidden sm:inline">Voice Chat</span>
                  </button>
                </div>

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

            {/* Error Notification Banner */}
            {(errorMessage || speechError) && (
              <div className="px-6 py-2 bg-rose-50 border-b border-rose-100 flex items-center justify-between text-xs text-rose-700">
                <span className="flex items-center gap-1.5">
                  <AlertCircle size={14} className="shrink-0" />
                  <span>{errorMessage || speechError}</span>
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setErrorMessage(null);
                    setSpeechError(null);
                  }}
                  className="text-rose-500 hover:text-rose-700"
                >
                  <X size={13} />
                </button>
              </div>
            )}

            {/* Speaking Status Pill */}
            {isSpeaking && (
              <div className="px-6 py-1.5 bg-blue-50 border-b border-blue-100 flex items-center justify-between text-xs text-blue-700">
                <div className="flex items-center gap-2">
                  <Volume2 size={14} className="animate-pulse text-blue-600" />
                  <span className="font-medium">Speaking response aloud...</span>
                </div>
                <Button
                  variant="outline"
                  size="xs"
                  icon={VolumeX}
                  onClick={handleStopSpeaking}
                  className="text-blue-700 border-blue-200 hover:bg-blue-100"
                >
                  Stop Speaking
                </Button>
              </div>
            )}

            {/* Messages Scroll View */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
              {loadingMessages ? (
                <div className="py-12 flex justify-center">
                  <Spinner size="md" />
                </div>
              ) : messages.length === 0 && !streaming ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-8 text-gray-400 space-y-3">
                  <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-500 flex items-center justify-center">
                    <Sparkles size={24} />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700">
                      Start your conversation with {activeAssistant?.name}
                    </h4>
                    <p className="text-xs text-gray-400 max-w-sm mt-1">
                      Type a message, speak via microphone, or attach documents to ask grounded questions.
                    </p>
                  </div>
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
                        {/* Speaker Button on Assistant Messages */}
                        {!isUser && (
                          <button
                            type="button"
                            onClick={() => handleToggleSpeakMessage(msg.id, msg.content)}
                            title={speakingMsgId === msg.id && isSpeaking ? "Stop" : "Listen aloud"}
                            className="p-1 rounded text-gray-400 hover:text-blue-600 hover:bg-gray-100 transition-colors"
                          >
                            {speakingMsgId === msg.id && isSpeaking ? (
                              <VolumeX size={12} className="text-rose-500 animate-pulse" />
                            ) : (
                              <Volume2 size={12} />
                            )}
                          </button>
                        )}
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

              {/* Pending Human-in-the-Loop Approval Cards */}
              {pendingApprovals.map((appr) => (
                <div
                  key={appr.id}
                  className="p-4 rounded-2xl border border-amber-200 bg-amber-50/70 shadow-xs max-w-2xl animate-fadeIn space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="p-1.5 rounded-lg bg-amber-100 text-amber-800">
                        <ShieldAlert size={16} />
                      </span>
                      <div>
                        <span className="font-semibold text-xs text-gray-900">
                          Human-in-the-Loop Approval Required
                        </span>
                        <p className="text-[11px] text-gray-600">
                          The assistant requested execution of external action:{" "}
                          <span className="font-mono font-bold text-gray-900">{appr.tool_name}</span>
                        </p>
                      </div>
                    </div>
                    <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-amber-200/80 text-amber-900">
                      Pending
                    </span>
                  </div>

                  {appr.call_arguments && Object.keys(appr.call_arguments).length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[11px] font-medium text-gray-600">Action Arguments:</span>
                      <pre className="p-2.5 rounded-xl bg-slate-900 text-slate-100 text-[11px] font-mono overflow-x-auto max-h-36">
                        {JSON.stringify(appr.call_arguments, null, 2)}
                      </pre>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2 border-t border-amber-200/60">
                    <span className="text-[10px] text-gray-500 font-mono">
                      Expires: {new Date(appr.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="xs"
                        disabled={approvingIds.has(appr.id)}
                        onClick={() => handleDenyTool(appr)}
                        className="text-rose-700 hover:bg-rose-50 border-rose-200"
                      >
                        Deny
                      </Button>
                      <Button
                        variant="primary"
                        size="xs"
                        disabled={approvingIds.has(appr.id)}
                        onClick={() => handleApproveTool(appr)}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        {approvingIds.has(appr.id) ? "Approving..." : "Approve & Execute"}
                      </Button>
                    </div>
                  </div>
                </div>
              ))}

              <div ref={messagesEndRef} />
            </div>

            {/* Attachment Chips Drawer (Above Input) */}
            {attachments.length > 0 && (
              <div className="px-6 py-2 border-t border-gray-100 bg-gray-50/70 flex items-center gap-2 overflow-x-auto">
                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider shrink-0 flex items-center gap-1">
                  <Paperclip size={12} />
                  <span>Attachments ({attachments.length}):</span>
                </span>
                <div className="flex items-center gap-2">
                  {attachments.map((att) => (
                    <div
                      key={att.id}
                      className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white border border-gray-200 text-xs shadow-xs shrink-0"
                    >
                      <FileText size={13} className="text-blue-500 shrink-0" />
                      <span className="font-medium text-gray-800 truncate max-w-[140px]" title={att.original_filename}>
                        {att.original_filename}
                      </span>
                      <span className="text-[10px] text-gray-400 font-mono">
                        {(att.file_size / 1024).toFixed(0)} KB
                      </span>

                      {/* Status indicator */}
                      {att.status === "READY" ? (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 font-medium">
                          Ready
                        </span>
                      ) : att.status === "PROCESSING" ? (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-50 text-amber-700 font-medium animate-pulse">
                          Indexing...
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-rose-50 text-rose-700 font-medium">
                          Failed
                        </span>
                      )}

                      {/* Promote to KB action */}
                      {att.is_promoted ? (
                        <span className="text-[10px] flex items-center gap-0.5 text-blue-600 font-medium" title="Promoted to Knowledge Base">
                          <Check size={11} />
                          <span>Saved to KB</span>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setPromoteAttachment(att);
                            setPromoteTitle(att.original_filename);
                            if (knowledgeBases.length > 0) {
                              setTargetKbId(knowledgeBases[0].id);
                            }
                          }}
                          className="text-[11px] text-blue-600 hover:text-blue-800 font-medium hover:underline flex items-center gap-0.5"
                          title="Promote document to Knowledge Base"
                        >
                          <Bookmark size={11} />
                          <span>Save to KB</span>
                        </button>
                      )}

                      {/* Delete attachment */}
                      <button
                        type="button"
                        onClick={() => handleDeleteAttachment(att.id)}
                        className="text-gray-400 hover:text-rose-600 p-0.5 rounded transition-colors"
                        title="Remove attachment from chat"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Bottom Input Area */}
            <div className="p-4 border-t border-gray-200 bg-white">
              <form onSubmit={handleSendMessage} className="space-y-2">
                <div className="relative flex items-center">
                  {/* Hidden File Input for Paperclip */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx,.txt,.csv"
                    onChange={handleFileUpload}
                  />

                  {/* Attachment & Mic Controls (Left of Textarea) */}
                  <div className="absolute left-2 flex items-center gap-1 z-10">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploadingAttachment || streaming}
                      className="p-1.5 rounded-lg text-gray-500 hover:text-blue-600 hover:bg-gray-100 transition-colors"
                      title="Attach document (PDF, DOCX, TXT, CSV)"
                    >
                      {uploadingAttachment ? (
                        <Spinner size="sm" />
                      ) : (
                        <Paperclip size={16} />
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={handleToggleMic}
                      className={`p-1.5 rounded-lg transition-colors ${
                        isListening
                          ? "bg-rose-100 text-rose-600 animate-pulse ring-2 ring-rose-400/50"
                          : "text-gray-500 hover:text-blue-600 hover:bg-gray-100"
                      }`}
                      title={isListening ? "Stop listening" : "Speak message via microphone"}
                    >
                      {isListening ? <MicOff size={16} /> : <Mic size={16} />}
                    </button>
                  </div>

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
                    placeholder={
                      isListening
                        ? "Listening... speak now"
                        : `Message ${activeAssistant?.name || "Assistant"}...`
                    }
                    disabled={streaming}
                    className="w-full resize-none pl-20 pr-24 py-2.5 text-sm bg-gray-50 border border-gray-300 rounded-xl text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-500/20"
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
                        disabled={!inputMessage.trim() && !isListening}
                      >
                        Send
                      </Button>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-gray-400 px-1">
                  <span>Enter to send · Shift+Enter for new line · Mic & Document aware</span>
                  <span className="flex items-center gap-1 text-gray-500">
                    <Sparkles size={12} className="text-blue-500" />
                    <span>Multimodal Agentic Runtime</span>
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

      {/* M22: Knowledge Base Promotion Modal */}
      {promoteAttachment && (
        <Modal
          isOpen={true}
          onClose={() => setPromoteAttachment(null)}
          title="Promote Document to Knowledge Base"
          description="Permanently index this conversation attachment into a shared Knowledge Base."
          maxWidth="md"
        >
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 text-xs space-y-1">
              <div className="font-semibold text-gray-800">{promoteAttachment.original_filename}</div>
              <div className="text-gray-500 font-mono">
                {(promoteAttachment.file_size / 1024).toFixed(0)} KB · {promoteAttachment.chunk_count} chunks extracted
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700">
                Destination Knowledge Base
              </label>
              {knowledgeBases.length === 0 ? (
                <p className="text-xs text-rose-600">
                  No Knowledge Bases found in this workspace. Please create a Knowledge Base first.
                </p>
              ) : (
                <select
                  value={targetKbId}
                  onChange={(e) => setTargetKbId(e.target.value)}
                  className="w-full text-xs bg-white border border-gray-300 rounded-lg p-2 text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                >
                  {knowledgeBases.map((kb) => (
                    <option key={kb.id} value={kb.id}>
                      {kb.name} ({kb.status || "ACTIVE"})
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700">
                Document Title (Optional)
              </label>
              <input
                type="text"
                value={promoteTitle}
                onChange={(e) => setPromoteTitle(e.target.value)}
                placeholder={promoteAttachment.original_filename}
                className="w-full text-xs bg-white border border-gray-300 rounded-lg p-2 text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-gray-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPromoteAttachment(null)}
                disabled={isPromoting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={Bookmark}
                onClick={handlePromoteAttachment}
                disabled={isPromoting || !targetKbId}
              >
                {isPromoting ? "Promoting..." : "Promote to KB"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
