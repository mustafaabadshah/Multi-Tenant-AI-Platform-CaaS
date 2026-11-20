"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
import { dedupeCitations, groupCitationsBySource } from "@/lib/citations";
import {
  BrowserSpeechRecognizer,
  BrowserSpeechSynthesizer,
  VoiceSessionController,
  VoiceMode,
  RecognitionState,
  VoiceSessionState,
  TranscriptResult,
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
  CheckCircle2,
  FileUp,
  Globe,
  Activity,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Spinner from "@/components/ui/Spinner";
import ConfirmModal from "@/components/ui/ConfirmModal";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import Badge from "@/components/ui/Badge";
import MarkdownRenderer from "@/components/chat/MarkdownRenderer";
import { consumePendingChatDraft } from "@/lib/chat-draft";

function ConversationsContent() {
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

  // M27: Web Source Save to Knowledge Base State
  const [saveWebCitation, setSaveWebCitation] = useState<MessageCitationItem | null>(null);
  const [saveWebKbId, setSaveWebKbId] = useState<string>("");
  const [saveWebTitle, setSaveWebTitle] = useState<string>("");
  const [saveWebMode, setSaveWebMode] = useState<"REFERENCE" | "NOTES" | "FULL_CONTENT" | "SEARCHABLE_CONTENT">("REFERENCE");
  const [saveWebNotes, setSaveWebNotes] = useState<string>("");
  const [isSavingWebSource, setIsSavingWebSource] = useState<boolean>(false);

  // M28.1: Live Web Reading SSE Status
  const [webReadingStatus, setWebReadingStatus] = useState<{
    url: string;
    status: "reading" | "completed" | "failed";
    title?: string;
    error?: string;
  } | null>(null);

  // M28: In-App Message Feedback State
  const [feedbackMap, setFeedbackMap] = useState<Record<string, { rating: "THUMBS_UP" | "THUMBS_DOWN"; category?: string; comment?: string }>>({});
  const [feedbackPopoverMsgId, setFeedbackPopoverMsgId] = useState<string | null>(null);
  const [feedbackSubmittingMsgId, setFeedbackSubmittingMsgId] = useState<string | null>(null);
  const [feedbackSuccessMsgId, setFeedbackSuccessMsgId] = useState<string | null>(null);
  const [negativeCategory, setNegativeCategory] = useState<string>("ACCURACY");
  const [negativeComment, setNegativeComment] = useState<string>("");

  // M28.16.1 & M28.16.2: In-Chat Model Override & Truthful Token Usage State
  const [activeChatModel, setActiveChatModel] = useState<string>("auto");
  const [lastUsage, setLastUsage] = useState<{
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    duration_ms: number;
    model?: string;
    provider?: string;
    is_estimated?: boolean;
  } | null>(null);

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

  // M28.7: Add Webpage Modal State
  const [showAddWebModal, setShowAddWebModal] = useState<boolean>(false);
  const [webpageUrlInput, setWebpageUrlInput] = useState<string>("");
  const [webpagePromptInput, setWebpagePromptInput] = useState<string>("");
  const [webpageUrlError, setWebpageUrlError] = useState<string | null>(null);

  // M27.1 Speech and Voice Session States
  const [recognitionState, setRecognitionState] = useState<RecognitionState>("IDLE");
  const [voiceSessionState, setVoiceSessionState] = useState<VoiceSessionState>("INACTIVE");
  const [voiceTranscript, setVoiceTranscript] = useState<string>("");
  const [showAudioDiagnostics, setShowAudioDiagnostics] = useState<boolean>(false);
  const [diagCapabilities, setDiagCapabilities] = useState<{
    recognitionSupported: boolean;
    synthesisSupported: boolean;
    isSecure: boolean;
    micPermission: string;
    voicesCount: number;
  }>({
    recognitionSupported: false,
    synthesisSupported: false,
    isSecure: false,
    micPermission: "prompt",
    voicesCount: 0,
  });
  const [diagTesting, setDiagTesting] = useState<string | null>(null);

  // Refs
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const speechRecognizerRef = useRef<BrowserSpeechRecognizer | null>(null);
  const speechSynthesizerRef = useRef<BrowserSpeechSynthesizer | null>(null);
  const voiceSessionRef = useRef<VoiceSessionController | null>(null);
  const voiceModeRef = useRef<VoiceMode>(voiceMode);
  voiceModeRef.current = voiceMode;
  const isSubmittingVoiceRef = useRef<boolean>(false);
  const pendingApprovalsRef = useRef<ToolApprovalItem[]>([]);
  pendingApprovalsRef.current = pendingApprovals;
  const handleSendMessageWithTextRef = useRef<(text?: string) => Promise<void>>(async () => {});

  // 1. Initialize Speech Engines & Voice Session Controller
  useEffect(() => {
    const recognizer = new BrowserSpeechRecognizer("en-US");
    const synthesizer = new BrowserSpeechSynthesizer();
    const voiceSession = new VoiceSessionController(recognizer, synthesizer);

    speechRecognizerRef.current = recognizer;
    speechSynthesizerRef.current = synthesizer;
    voiceSessionRef.current = voiceSession;

    recognizer.onState((st) => {
      setRecognitionState(st);
      setIsListening(st === "LISTENING");
      if (st === "LISTENING" || st === "IDLE") {
        setSpeechError(null);
      }
    });

    recognizer.onError((err: any) => {
      setSpeechError(typeof err === "string" ? err : err.message);
      setIsListening(false);
    });

    recognizer.onTranscript((result: any) => {
      const text = typeof result === "string" ? result : result.fullTranscript;
      if (voiceModeRef.current === "DICTATION") {
        setInputMessage(text);
      }
    });

    synthesizer.onSpeakingChange((speaking) => {
      setIsSpeaking(speaking);
      if (!speaking) {
        setSpeakingMsgId(null);
      }
    });

    voiceSession.onStateChange((st) => {
      setVoiceSessionState(st);
    });

    voiceSession.onTranscript((text) => {
      setVoiceTranscript(text);
    });

    voiceSession.setTurnSubmitHandler(async (spokenText) => {
      await handleSendMessageWithTextRef.current(spokenText);
    });

    // Check capabilities for diagnostics
    if (typeof window !== "undefined") {
      const isSecure = window.isSecureContext ?? false;
      const recSupported = recognizer.isSupported();
      const synthSupported = synthesizer.isSupported();
      const voicesCount = synthesizer.getVoices().length;

      let micPerm = "unknown";
      if (navigator?.permissions?.query) {
        navigator.permissions
          .query({ name: "microphone" as PermissionName })
          .then((p) => {
            micPerm = p.state;
            setDiagCapabilities({
              recognitionSupported: recSupported,
              synthesisSupported: synthSupported,
              isSecure,
              micPermission: micPerm,
              voicesCount,
            });
          })
          .catch(() => {
            setDiagCapabilities({
              recognitionSupported: recSupported,
              synthesisSupported: synthSupported,
              isSecure,
              micPermission: "prompt",
              voicesCount,
            });
          });
      } else {
        setDiagCapabilities({
          recognitionSupported: recSupported,
          synthesisSupported: synthSupported,
          isSecure,
          micPermission: micPerm,
          voicesCount,
        });
      }
    }

    // Load user voice preferences if available
    api.getVoicePreferences()
      .then((pref) => {
        if (pref?.voice_mode) {
          setVoiceMode(pref.voice_mode as VoiceMode);
          voiceModeRef.current = pref.voice_mode as VoiceMode;
        }
      })
      .catch(() => {});

    return () => {
      voiceSession.endSession();
      recognizer.abort();
      synthesizer.cancel();
      isSubmittingVoiceRef.current = false;
    };
  }, []);

  const searchParams = useSearchParams();
  const queryAssistantId = searchParams?.get("assistantId");
  const queryConversationId = searchParams?.get("conversationId");

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

        // Secure tab-scoped draft handoff (one-time consumption, tenant-scoped, no URL leakage)
        const pendingDraft = consumePendingChatDraft(activeWorkspace.tenant_id, queryAssistantId || undefined);
        if (pendingDraft) {
          setInputMessage(pendingDraft);
        }

        if (queryConversationId) {
          const match = convList.find((c) => c.id === queryConversationId);
          if (match) {
            setActiveConversation(match);
          } else if (convList.length > 0) {
            setActiveConversation(convList[0]);
          }
        } else if (queryAssistantId) {
          setSelectedAssistantFilter(queryAssistantId);
          const match = convList.find((c) => c.assistant_id === queryAssistantId);
          if (match) {
            setActiveConversation(match);
          } else if (astList.some((a) => a.id === queryAssistantId)) {
            // Start a new conversation for this assistant
            try {
              const targetAst = astList.find((a) => a.id === queryAssistantId);
              const newConv = await api.createConversation({
                assistant_id: queryAssistantId,
                title: `Chat with ${targetAst?.name || "Assistant"}`,
              });
              setConversations((prev) => [newConv, ...prev]);
              setActiveConversation(newConv);
            } catch {
              if (convList.length > 0) setActiveConversation(convList[0]);
            }
          } else if (convList.length > 0) {
            setActiveConversation(convList[0]);
          }
        } else if (convList.length > 0) {
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
  }, [activeWorkspace, queryAssistantId, queryConversationId]);

  // 3. Fetch Messages & Attachments when active conversation changes
  useEffect(() => {
    // Stop ongoing speech on conversation switch
    voiceSessionRef.current?.endSession();
    speechSynthesizerRef.current?.cancel();
    speechRecognizerRef.current?.stop();
    setIsSpeaking(false);
    setIsListening(false);
    setSpeakingMsgId(null);
    setVoiceTranscript("");
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

  // Assistant connected Knowledge Bases vs other workspace KBs
  const connectedKbIds = useMemo(() => {
    return activeAssistant?.connected_kb_ids || [];
  }, [activeAssistant]);

  const connectedKBs = useMemo(() => {
    return knowledgeBases.filter((kb) => connectedKbIds.includes(kb.id));
  }, [knowledgeBases, connectedKbIds]);

  const otherKBs = useMemo(() => {
    return knowledgeBases.filter((kb) => !connectedKbIds.includes(kb.id));
  }, [knowledgeBases, connectedKbIds]);

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

  // M22 / M28.13: Save to Knowledge Handlers with Deterministic Destination Policy
  const handleOpenSaveAttachment = (att: ConversationAttachmentItem) => {
    setPromoteAttachment(att);
    setPromoteTitle(att.filename || (att as any).original_filename || "");
    if (connectedKBs.length === 1) {
      // Case A: Exactly one connected KB -> preselect it
      setTargetKbId(connectedKBs[0].id);
    } else {
      // Case B (multiple) or Case C (no connected KBs) -> require explicit destination selection
      setTargetKbId("");
    }
  };

  const handleOpenSaveWebSource = (cit: MessageCitationItem) => {
    setSaveWebCitation(cit);
    setSaveWebTitle(cit.document_name || "");
    setSaveWebMode("REFERENCE");
    setSaveWebNotes("");
    if (connectedKBs.length === 1) {
      // Case A: Exactly one connected KB -> preselect it
      setSaveWebKbId(connectedKBs[0].id);
    } else {
      // Case B (multiple) or Case C (no connected KBs) -> require explicit destination selection
      setSaveWebKbId("");
    }
  };

  const handleSaveWebSource = async () => {
    if (!saveWebCitation || !saveWebKbId) return;
    setIsSavingWebSource(true);
    try {
      const url = saveWebCitation.source_url || (saveWebCitation.document_name.startsWith("http") ? saveWebCitation.document_name : "");
      if (!url) {
        setErrorMessage("No valid URL found for this web source.");
        return;
      }
      await api.saveWebSourceToKB(
        url,
        saveWebKbId,
        saveWebTitle.trim() || undefined,
        saveWebMode,
        saveWebNotes.trim() || undefined
      );
      setSaveWebCitation(null);
      setSaveWebKbId("");
      setSaveWebTitle("");
      setSaveWebNotes("");
      setErrorMessage(null);
    } catch (err: any) {
      console.error("Failed to save web source to KB", err);
      setErrorMessage(err.message || "Failed to save web source to Knowledge Base.");
    } finally {
      setIsSavingWebSource(false);
    }
  };

  const handlePromoteAttachment = async () => {
    if (!activeConversation || !promoteAttachment || !targetKbId) return;
    try {
      setIsPromoting(true);
      const res = await api.promoteConversationAttachment(
        activeConversation.id,
        promoteAttachment.id,
        targetKbId,
        (promoteTitle || "").trim() || undefined
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
      setErrorMessage(null);
    } catch (err: any) {
      console.error("Failed to promote attachment", err);
      setErrorMessage(err.message || "Failed to promote document to Knowledge Base.");
    } finally {
      setIsPromoting(false);
    }
  };

  // M28: Message Feedback Handlers
  const handleThumbsUp = async (msgId: string) => {
    if (!activeConversation || feedbackSubmittingMsgId) return;
    setFeedbackSubmittingMsgId(msgId);
    setFeedbackPopoverMsgId(null);
    try {
      await api.submitMessageFeedback(activeConversation.id, msgId, {
        rating: "THUMBS_UP",
      });
      setFeedbackMap((prev) => ({
        ...prev,
        [msgId]: { rating: "THUMBS_UP" },
      }));
      setFeedbackSuccessMsgId(msgId);
      setTimeout(() => setFeedbackSuccessMsgId((cur) => (cur === msgId ? null : cur)), 2500);
    } catch (err: any) {
      console.error("Failed to submit feedback", err);
    } finally {
      setFeedbackSubmittingMsgId(null);
    }
  };

  const handleOpenThumbsDownPopover = (msgId: string) => {
    setFeedbackPopoverMsgId((prev) => (prev === msgId ? null : msgId));
    const existing = feedbackMap[msgId];
    if (existing && existing.category) {
      setNegativeCategory(existing.category);
      setNegativeComment(existing.comment || "");
    } else {
      setNegativeCategory("ACCURACY");
      setNegativeComment("");
    }
  };

  const handleSubmitNegativeFeedback = async (msgId: string) => {
    if (!activeConversation || feedbackSubmittingMsgId) return;
    setFeedbackSubmittingMsgId(msgId);
    try {
      await api.submitMessageFeedback(activeConversation.id, msgId, {
        rating: "THUMBS_DOWN",
        category: negativeCategory,
        comment: negativeComment.trim() || undefined,
      });
      setFeedbackMap((prev) => ({
        ...prev,
        [msgId]: {
          rating: "THUMBS_DOWN",
          category: negativeCategory,
          comment: negativeComment.trim() || undefined,
        },
      }));
      setFeedbackPopoverMsgId(null);
      setFeedbackSuccessMsgId(msgId);
      setTimeout(() => setFeedbackSuccessMsgId((cur) => (cur === msgId ? null : cur)), 2500);
    } catch (err: any) {
      console.error("Failed to submit negative feedback", err);
    } finally {
      setFeedbackSubmittingMsgId(null);
    }
  };

  // M23, M24 & M27.1: Change Voice Mode
  const handleVoiceModeChange = async (newMode: VoiceMode) => {
    setVoiceMode(newMode);
    voiceModeRef.current = newMode;
    setSpeechError(null);

    // Cancel existing sessions cleanly on mode change
    voiceSessionRef.current?.endSession();
    speechRecognizerRef.current?.stop();
    speechSynthesizerRef.current?.cancel();
    setIsListening(false);
    setIsSpeaking(false);
    setVoiceTranscript("");

    try {
      await api.updateVoicePreferences({ voice_mode: newMode });
    } catch (_) {}
  };

  // M23, M24 & M27.1: Toggle Microphone
  const handleToggleMic = () => {
    setSpeechError(null);

    if (voiceMode === "VOICE_CONVERSATION") {
      const session = voiceSessionRef.current;
      if (!session) return;
      if (voiceSessionState !== "INACTIVE") {
        session.endSession();
      } else {
        session.startSession();
      }
      return;
    }

    // If currently in TEXT mode, clicking mic enters DICTATION mode
    if (voiceMode === "TEXT") {
      setVoiceMode("DICTATION");
      voiceModeRef.current = "DICTATION";
    }

    const recognizer = speechRecognizerRef.current;
    if (!recognizer) return;

    if (!recognizer.isSupported()) {
      setSpeechError(
        "Speech recognition is not supported in this browser. Please use Google Chrome, Microsoft Edge, or Safari."
      );
      return;
    }

    if (recognitionState === "LISTENING" || recognitionState === "STARTING") {
      recognizer.stop();
    } else {
      const ok = recognizer.start();
      if (!ok) {
        setSpeechError("Could not start microphone. Please check browser microphone permissions.");
      }
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
    handleSendMessageWithTextRef.current = handleSendMessageWithText;
    const textToSend = (customPrompt ?? inputMessage).trim();
    if (!textToSend || streaming) return;

    let conv = activeConversation;
    if (!conv) {
      if (assistants.length === 0) {
        setErrorMessage("Please create an assistant first before starting a conversation.");
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
    setWebReadingStatus(null);
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
          body: JSON.stringify({
            content: textToSend,
            model: activeChatModel !== "auto" ? activeChatModel : undefined,
          }),
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
              } else if (eventType === "web_reading_started") {
                setWebReadingStatus({ url: data.url, status: "reading" });
              } else if (eventType === "web_reading_completed") {
                setWebReadingStatus({ url: data.url, status: "completed", title: data.title });
              } else if (eventType === "web_reading_failed") {
                setWebReadingStatus({ url: data.url, status: "failed", error: data.error });
              } else if (eventType === "web_source_discovered") {
                if (data.url) {
                  const webCit: MessageCitationItem = {
                    id: "web-" + Math.random().toString(36).substring(2, 9),
                    citation_num: accumulatedCitations.length + 1,
                    chunk_id: null,
                    document_name: data.title || data.domain || data.url,
                    citation_text: data.title || data.url,
                    source_type: "web",
                    source_url: data.url,
                    domain: data.domain,
                    page_number: null,
                  };
                  accumulatedCitations = dedupeCitations(accumulatedCitations, [webCit]);
                  setStreamingCitations([...accumulatedCitations]);
                }
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
                voiceSessionRef.current?.notifyWaitingForApproval();
              } else if (eventType === "usage") {
                setLastUsage({
                  input_tokens: data.input_tokens || 0,
                  output_tokens: data.output_tokens || 0,
                  total_tokens: data.total_tokens || ((data.input_tokens || 0) + (data.output_tokens || 0)),
                  duration_ms: data.duration_ms || 0,
                  model: data.model || activeChatModel,
                  provider: data.provider,
                  is_estimated: Boolean(data.is_estimated),
                });
              } else if (eventType === "message_end") {
                // Completed
              } else if (eventType === "message_error") {
                setErrorMessage(data.error || "Generation error");
                accumulatedCitations = [];
                setStreamingCitations([]);
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

        // M24 & M27.1: Automated TTS in LISTEN or VOICE_CONVERSATION modes
        const currentMode = voiceModeRef.current;
        if (currentMode === "VOICE_CONVERSATION") {
          if (pendingApprovalsRef.current.length > 0) {
            voiceSessionRef.current?.notifyWaitingForApproval();
          } else {
            voiceSessionRef.current?.speakResponse(accumulatedText);
          }
        } else if (currentMode === "LISTEN") {
          speechRecognizerRef.current?.stop();
          setIsListening(false);
          speechSynthesizerRef.current?.speak(accumulatedText);
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
      const remaining = pendingApprovals.filter((a) => a.id !== approval.id);
      setPendingApprovals(remaining);
      if (activeConversation) {
        const fresh = await api.listMessages(activeConversation.id);
        setMessages(fresh);
      }
      if (voiceModeRef.current === "VOICE_CONVERSATION" && remaining.length === 0) {
        voiceSessionRef.current?.notifyApprovalResolved();
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
      const remaining = pendingApprovals.filter((a) => a.id !== approval.id);
      setPendingApprovals(remaining);
      if (voiceModeRef.current === "VOICE_CONVERSATION" && remaining.length === 0) {
        voiceSessionRef.current?.notifyApprovalResolved();
      }
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

  // M27.1: Operator Audio Diagnostics Handlers
  const handleTestMicrophone = async () => {
    setDiagTesting("microphone");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setTimeout(() => {
        stream.getTracks().forEach((t) => t.stop());
        setDiagTesting(null);
        alert("Microphone test PASSED: Real audio stream opened successfully.");
      }, 1000);
    } catch (err: any) {
      setDiagTesting(null);
      alert(`Microphone test FAILED: ${err.message}`);
    }
  };

  const handleTestSpeechRecognition = () => {
    const rec = speechRecognizerRef.current;
    if (!rec || !rec.isSupported()) {
      alert("Speech recognition is UNSUPPORTED in this browser.");
      return;
    }
    setDiagTesting("recognition");
    rec.start();
    setTimeout(() => {
      rec.stop();
      setDiagTesting(null);
      alert("Speech recognition test triggered. Observe recognition status banner.");
    }, 2500);
  };

  const handleTestSpeaker = () => {
    const synth = speechSynthesizerRef.current;
    if (!synth || !synth.isSupported()) {
      alert("Speech synthesis is UNSUPPORTED in this browser.");
      return;
    }
    setDiagTesting("speaker");
    synth.testVoice(undefined, () => {
      setDiagTesting(null);
    });
  };

  const handleStopAllAudio = () => {
    voiceSessionRef.current?.endSession();
    speechSynthesizerRef.current?.cancel();
    speechRecognizerRef.current?.stop();
    setIsSpeaking(false);
    setIsListening(false);
    setSpeakingMsgId(null);
    setVoiceTranscript("");
    setDiagTesting(null);
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
                    onClick={() => handleVoiceModeChange("TEXT")}
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
                    onClick={() => handleVoiceModeChange("DICTATION")}
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
                    onClick={() => handleVoiceModeChange("LISTEN")}
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
                    onClick={() => handleVoiceModeChange("VOICE_CONVERSATION")}
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
                <div className="h-full flex flex-col items-center justify-center text-center p-8 text-gray-400 space-y-4">
                  <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-500 flex items-center justify-center">
                    <Sparkles size={24} />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-gray-700">
                      {activeAssistant ? `Chat with ${activeAssistant.name}` : "Start a Conversation"}
                    </h4>
                    <p className="text-xs text-gray-400 max-w-sm mt-1">
                      {activeAssistant
                        ? "Type a question, paste a webpage link, or attach documents for grounded answers."
                        : "Select or create an assistant to start exploring grounded AI capabilities."}
                    </p>
                  </div>
                  {activeAssistant && (
                    <div className="flex flex-wrap gap-2 justify-center max-w-md pt-1">
                      <button
                        type="button"
                        onClick={() => handleSendMessageWithText("What can you help me with?")}
                        className="px-3 py-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 border border-gray-200 text-xs text-gray-700 transition-colors cursor-pointer"
                      >
                        "What can you help me with?"
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSendMessageWithText("Summarize the key information from my documents.")}
                        className="px-3 py-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 border border-gray-200 text-xs text-gray-700 transition-colors cursor-pointer"
                      >
                        "Summarize key document info"
                      </button>
                    </div>
                  )}
                  {assistants.length === 0 && (
                    <Link href="/dashboard/assistants" className="pt-2">
                      <Button variant="primary" size="sm" icon={Plus}>
                        Create your first assistant
                      </Button>
                    </Link>
                  )}
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
                          {groupCitationsBySource(msg.citations).map((g) => {
                            const isWeb = g.source_type === "web" || !!g.source_url;
                            const citNumbers = g.citation_nums.length > 0 ? `[${g.citation_nums.join(", ")}] ` : "";
                            const pageLabel = !isWeb && g.pages.length > 0 ? ` p.${g.pages.join(", ")}` : "";
                            return (
                              <button
                                key={g.key}
                                type="button"
                                onClick={() => setInspectCitation(g.primary_citation)}
                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                                  isWeb
                                    ? "bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/60"
                                    : "bg-gray-100 hover:bg-gray-200 text-gray-700"
                                }`}
                                title={isWeb ? (g.source_url || g.document_name) : `${g.document_name}${pageLabel}`}
                              >
                                {isWeb ? (
                                  <Globe size={11} className="text-emerald-600" />
                                ) : (
                                  <FileText size={11} className="text-gray-500" />
                                )}
                                <span className="truncate max-w-[150px]">
                                  {citNumbers}{g.document_name}
                                </span>
                                {pageLabel && (
                                  <span className="text-[10px] text-gray-400">
                                    {pageLabel}
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      )}

                      {/* M28: In-App Message Feedback Controls */}
                      {!isUser && !msg.id.startsWith("asst-") && (
                        <div className="mt-1.5 flex flex-col items-start px-1">
                          <div className="flex items-center gap-1.5 text-xs text-gray-400">
                            {/* Thumbs Up Button */}
                            <button
                              type="button"
                              onClick={() => handleThumbsUp(msg.id)}
                              disabled={feedbackSubmittingMsgId === msg.id}
                              aria-label="Thumbs up"
                              title="Helpful response"
                              className={`p-1 rounded-md transition-colors ${
                                feedbackMap[msg.id]?.rating === "THUMBS_UP"
                                  ? "text-emerald-600 bg-emerald-50 border border-emerald-200"
                                  : "hover:text-gray-700 hover:bg-gray-100"
                              }`}
                            >
                              <ThumbsUp size={12} className={feedbackMap[msg.id]?.rating === "THUMBS_UP" ? "fill-current" : ""} />
                            </button>

                            {/* Thumbs Down Button */}
                            <button
                              type="button"
                              onClick={() => handleOpenThumbsDownPopover(msg.id)}
                              disabled={feedbackSubmittingMsgId === msg.id}
                              aria-label="Thumbs down"
                              title="Unhelpful or inaccurate response"
                              className={`p-1 rounded-md transition-colors ${
                                feedbackMap[msg.id]?.rating === "THUMBS_DOWN"
                                  ? "text-rose-600 bg-rose-50 border border-rose-200"
                                  : "hover:text-gray-700 hover:bg-gray-100"
                              }`}
                            >
                              <ThumbsDown size={12} className={feedbackMap[msg.id]?.rating === "THUMBS_DOWN" ? "fill-current" : ""} />
                            </button>

                            {/* Feedback Confirmation Pill */}
                            {feedbackSuccessMsgId === msg.id && (
                              <span className="text-[11px] text-emerald-600 flex items-center gap-1 font-medium ml-1 animate-fadeIn">
                                <Check size={11} /> Feedback recorded
                              </span>
                            )}
                          </div>

                          {/* Inline Negative Feedback Popover */}
                          {feedbackPopoverMsgId === msg.id && (
                            <div className="mt-2 p-3 bg-white border border-gray-200 rounded-xl shadow-md w-full max-w-sm text-xs space-y-2 animate-fadeIn z-10">
                              <div className="flex items-center justify-between font-medium text-gray-700">
                                <span>What went wrong?</span>
                                <button
                                  type="button"
                                  onClick={() => setFeedbackPopoverMsgId(null)}
                                  className="text-gray-400 hover:text-gray-600"
                                >
                                  <X size={12} />
                                </button>
                              </div>

                              {/* Category selection chips */}
                              <div className="flex flex-wrap gap-1">
                                {[
                                  { id: "ACCURACY", label: "Inaccurate" },
                                  { id: "HALLUCINATION", label: "Hallucination" },
                                  { id: "HELPFULNESS", label: "Unhelpful" },
                                  { id: "INCOMPLETE", label: "Incomplete" },
                                  { id: "TONE", label: "Tone" },
                                  { id: "OTHER", label: "Other" },
                                ].map((cat) => (
                                  <button
                                    key={cat.id}
                                    type="button"
                                    onClick={() => setNegativeCategory(cat.id)}
                                    className={`px-2 py-0.5 rounded-full text-[11px] border transition-colors ${
                                      negativeCategory === cat.id
                                        ? "bg-rose-50 border-rose-300 text-rose-700 font-medium"
                                        : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100"
                                    }`}
                                  >
                                    {cat.label}
                                  </button>
                                ))}
                              </div>

                              {/* Optional comment */}
                              <input
                                type="text"
                                value={negativeComment}
                                onChange={(e) => setNegativeComment(e.target.value)}
                                placeholder="Additional details (optional)..."
                                maxLength={500}
                                className="w-full px-2.5 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 text-gray-800"
                              />

                              <div className="flex justify-end gap-1.5 pt-1">
                                <button
                                  type="button"
                                  onClick={() => setFeedbackPopoverMsgId(null)}
                                  className="px-2.5 py-1 rounded-md text-gray-500 hover:bg-gray-100 text-[11px]"
                                >
                                  Cancel
                                </button>
                                <button
                                  type="button"
                                  disabled={feedbackSubmittingMsgId === msg.id}
                                  onClick={() => handleSubmitNegativeFeedback(msg.id)}
                                  className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-md text-[11px] font-medium transition-colors disabled:opacity-50"
                                >
                                  {feedbackSubmittingMsgId === msg.id ? "Saving..." : "Submit Feedback"}
                                </button>
                              </div>
                            </div>
                          )}
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
                    {webReadingStatus && (
                      <div className={`mb-2.5 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border ${
                        webReadingStatus.status === "reading"
                          ? "bg-blue-50 border-blue-200 text-blue-700 animate-pulse"
                          : webReadingStatus.status === "completed"
                          ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                          : "bg-amber-50 border-amber-200 text-amber-800"
                      }`}>
                        <Globe size={13} className={webReadingStatus.status === "reading" ? "animate-spin text-blue-600" : ""} />
                        <span>
                          {webReadingStatus.status === "reading" && `Reading webpage: ${webReadingStatus.url}...`}
                          {webReadingStatus.status === "completed" && `Webpage read: ${webReadingStatus.title || webReadingStatus.url}`}
                          {webReadingStatus.status === "failed" && `Couldn't read webpage: ${webReadingStatus.error || "Blocked or unreachable"}`}
                        </span>
                      </div>
                    )}
                    <MarkdownRenderer
                      content={streamingContent || ""}
                      citations={streamingCitations}
                      onCitationClick={(cit) => setInspectCitation(cit)}
                      className="text-sm"
                    />
                    {!streamingContent && !webReadingStatus && (
                      <span className="text-gray-400 italic text-xs">Thinking...</span>
                    )}
                    <span className="inline-block w-1.5 h-4 ml-1 bg-blue-600 animate-pulse align-middle" />
                  </div>

                  {streamingCitations.length > 0 && (
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 px-1">
                      <span className="text-[10px] uppercase font-semibold text-gray-400 mr-1">
                        Discovered Sources:
                      </span>
                      {groupCitationsBySource(streamingCitations).map((g) => (
                        <span
                          key={g.key}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs"
                        >
                          <FileText size={11} />
                          <span className="truncate max-w-[150px]">{g.document_name}</span>
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
                      <span className="font-medium text-gray-800 truncate max-w-[140px]" title={att.filename || (att as any).original_filename}>
                        {att.filename || (att as any).original_filename}
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

                      {/* Save to Knowledge action */}
                      {att.is_promoted ? (
                        <span
                          className="text-[10px] flex items-center gap-1 text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium border border-emerald-200/60"
                          title={`Saved to ${knowledgeBases.find((k) => k.id === att.promoted_knowledge_base_id)?.name || "Knowledge Base"}`}
                        >
                          <Check size={11} className="text-emerald-600" />
                          <span>Saved to {knowledgeBases.find((k) => k.id === att.promoted_knowledge_base_id)?.name || "Knowledge Base"}</span>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleOpenSaveAttachment(att)}
                          className="text-[11px] text-blue-600 hover:text-blue-800 font-medium hover:underline flex items-center gap-0.5 cursor-pointer"
                          title="Save document to Knowledge Base"
                        >
                          <Bookmark size={11} />
                          <span>Save to Knowledge</span>
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
            <div className="p-4 border-t border-gray-200 bg-white space-y-2.5">
              {/* Voice Mode Selector & Speech Status */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-1 bg-gray-100 p-0.5 rounded-lg border border-gray-200/80">
                  <button
                    type="button"
                    onClick={() => handleVoiceModeChange("TEXT")}
                    className={`px-2 py-1 rounded-md font-medium flex items-center gap-1 transition-colors ${
                      voiceMode === "TEXT"
                        ? "bg-white text-gray-900 shadow-2xs font-semibold"
                        : "text-gray-500 hover:text-gray-900"
                    }`}
                    title="Standard text chat"
                  >
                    <MessageSquare size={12} />
                    <span>Text</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleVoiceModeChange("DICTATION")}
                    className={`px-2 py-1 rounded-md font-medium flex items-center gap-1 transition-colors ${
                      voiceMode === "DICTATION"
                        ? "bg-white text-blue-600 shadow-2xs font-semibold"
                        : "text-gray-500 hover:text-gray-900"
                    }`}
                    title="Dictation: Click mic or speak to write text"
                  >
                    <Mic size={12} />
                    <span>Dictate</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleVoiceModeChange("LISTEN")}
                    className={`px-2 py-1 rounded-md font-medium flex items-center gap-1 transition-colors ${
                      voiceMode === "LISTEN"
                        ? "bg-white text-indigo-600 shadow-2xs font-semibold"
                        : "text-gray-500 hover:text-gray-900"
                    }`}
                    title="Auto-Read: Assistant reads aloud all generated responses"
                  >
                    <Volume2 size={12} />
                    <span>Auto-Read</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleVoiceModeChange("VOICE_CONVERSATION")}
                    className={`px-2 py-1 rounded-md font-medium flex items-center gap-1 transition-colors ${
                      voiceMode === "VOICE_CONVERSATION"
                        ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-xs font-semibold"
                        : "text-gray-500 hover:text-gray-900"
                    }`}
                    title="GPT Voice: Hands-free conversational loop (speak -> auto-answer -> listen)"
                  >
                    <Sparkles size={12} />
                    <span>Voice Chat</span>
                  </button>
                </div>

                {/* Speaking indicator / Stop speaking */}
                <div className="flex items-center gap-2">
                  {isSpeaking && (
                    <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-700 animate-fadeIn text-[11px]">
                      <Volume2 size={12} className="animate-pulse" />
                      <span>Speaking...</span>
                      <button
                        type="button"
                        onClick={handleStopSpeaking}
                        className="ml-1 text-xs text-indigo-900 underline font-semibold hover:text-indigo-950"
                      >
                        Mute
                      </button>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => setShowAudioDiagnostics((prev) => !prev)}
                    className={`px-2 py-1 rounded-md text-[11px] font-medium flex items-center gap-1 transition-colors ${
                      showAudioDiagnostics
                        ? "bg-blue-100 text-blue-800 font-semibold"
                        : "text-gray-500 hover:text-gray-800 hover:bg-gray-100"
                    }`}
                    title="Toggle Operator Audio Diagnostics"
                  >
                    <Activity size={12} />
                    <span>Audio Diagnostics</span>
                  </button>
                </div>
              </div>

              {/* Operator Audio Diagnostics Panel */}
              {showAudioDiagnostics && (
                <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl space-y-2.5 text-xs text-gray-700 animate-fadeIn">
                  <div className="flex items-center justify-between border-b border-gray-200 pb-1.5">
                    <span className="font-semibold text-gray-900 flex items-center gap-1.5">
                      <Activity size={13} className="text-blue-600" />
                      Operator Audio Diagnostics
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowAudioDiagnostics(false)}
                      className="text-gray-400 hover:text-gray-700"
                    >
                      <X size={13} />
                    </button>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                    <div className="p-2 bg-white rounded border border-gray-200/80">
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">Secure Context</span>
                      <span className={diagCapabilities.isSecure ? "text-emerald-700 font-medium" : "text-amber-700 font-medium"}>
                        {diagCapabilities.isSecure ? "YES (HTTPS/Local)" : "NO (Insecure)"}
                      </span>
                    </div>

                    <div className="p-2 bg-white rounded border border-gray-200/80">
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">Speech Recognition</span>
                      <span className={diagCapabilities.recognitionSupported ? "text-emerald-700 font-medium" : "text-rose-700 font-medium"}>
                        {diagCapabilities.recognitionSupported ? "Available" : "Not supported"}
                      </span>
                    </div>

                    <div className="p-2 bg-white rounded border border-gray-200/80">
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">Speech Synthesis</span>
                      <span className={diagCapabilities.synthesisSupported ? "text-emerald-700 font-medium" : "text-rose-700 font-medium"}>
                        {diagCapabilities.synthesisSupported ? `${diagCapabilities.voicesCount} voices loaded` : "Not supported"}
                      </span>
                    </div>

                    <div className="p-2 bg-white rounded border border-gray-200/80">
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">Engine State</span>
                      <span className="text-blue-700 font-medium font-mono text-[10px]">
                        STT: {recognitionState} | Voice: {voiceSessionState}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={handleTestMicrophone}
                      disabled={diagTesting !== null}
                      className="px-2.5 py-1 bg-white border border-gray-300 hover:bg-gray-100 rounded text-[11px] font-medium text-gray-700 disabled:opacity-50"
                    >
                      {diagTesting === "microphone" ? "Testing Mic..." : "Test Microphone"}
                    </button>

                    <button
                      type="button"
                      onClick={handleTestSpeechRecognition}
                      disabled={diagTesting !== null || !diagCapabilities.recognitionSupported}
                      className="px-2.5 py-1 bg-white border border-gray-300 hover:bg-gray-100 rounded text-[11px] font-medium text-gray-700 disabled:opacity-50"
                    >
                      {diagTesting === "recognition" ? "Testing STT..." : "Test Speech Recognition"}
                    </button>

                    <button
                      type="button"
                      onClick={handleTestSpeaker}
                      disabled={diagTesting !== null || !diagCapabilities.synthesisSupported}
                      className="px-2.5 py-1 bg-white border border-gray-300 hover:bg-gray-100 rounded text-[11px] font-medium text-gray-700 disabled:opacity-50"
                    >
                      {diagTesting === "speaker" ? "Speaking Sample..." : "Test Speaker"}
                    </button>

                    <button
                      type="button"
                      onClick={handleStopAllAudio}
                      className="px-2.5 py-1 bg-rose-50 border border-rose-200 hover:bg-rose-100 rounded text-[11px] font-medium text-rose-700 ml-auto"
                    >
                      Stop All Audio
                    </button>
                  </div>
                </div>
              )}

              {/* Dictation Mode Active Banner */}
              {voiceMode === "DICTATION" && (recognitionState === "LISTENING" || recognitionState === "STARTING") && (
                <div className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs animate-fadeIn">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                    <Mic size={13} className="text-blue-600" />
                    <span className="font-medium">
                      Dictating... speak clearly into your microphone. Words appear in textarea.
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => speechRecognizerRef.current?.stop()}
                    className="text-xs text-blue-800 font-semibold hover:underline"
                  >
                    Stop Dictating
                  </button>
                </div>
              )}

              {/* Voice Chat Mode Status Cards */}
              {voiceMode === "VOICE_CONVERSATION" && (
                <>
                  {voiceSessionState === "INACTIVE" && (
                    <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-gradient-to-r from-blue-50 via-indigo-50 to-purple-50 border border-blue-200/80 animate-fadeIn">
                      <div className="flex items-center gap-2.5">
                        <div className="p-1.5 rounded-lg bg-blue-100/80 text-blue-700">
                          <Sparkles size={14} />
                        </div>
                        <div>
                          <span className="text-xs font-semibold text-gray-800 block">Voice Chat Ready</span>
                          <span className="text-[11px] text-gray-500 block">
                            Tap Start to begin continuous turn-based voice conversation.
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => voiceSessionRef.current?.startSession()}
                        className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs transition-all cursor-pointer"
                      >
                        <Mic size={13} />
                        <span>Start Voice Chat</span>
                      </button>
                    </div>
                  )}

                  {(voiceSessionState === "LISTENING" || voiceSessionState === "STARTING" || voiceSessionState === "READY") && (
                    <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-rose-50 border border-rose-200 text-xs animate-fadeIn">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping" />
                        <Mic size={14} className="text-rose-600" />
                        <span className="font-semibold text-rose-800">Listening...</span>
                        {voiceTranscript ? (
                          <span className="text-rose-900 font-medium italic">"{voiceTranscript}"</span>
                        ) : (
                          <span className="text-rose-600 italic">speak your question clearly</span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => voiceSessionRef.current?.endSession()}
                        className="text-xs text-rose-800 font-semibold hover:underline cursor-pointer"
                      >
                        End Voice Chat
                      </button>
                    </div>
                  )}

                  {(voiceSessionState === "TRANSCRIBING" || voiceSessionState === "SUBMITTING") && (
                    <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-800 animate-fadeIn">
                      <div className="flex items-center gap-2">
                        <Spinner size="sm" />
                        <span className="font-semibold">Submitting speech turn:</span>
                        <span className="italic">"{voiceTranscript}"</span>
                      </div>
                    </div>
                  )}

                  {voiceSessionState === "THINKING" && (
                    <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-indigo-50 border border-indigo-200 text-xs text-indigo-800 animate-fadeIn">
                      <div className="flex items-center gap-2">
                        <Spinner size="sm" />
                        <span className="font-semibold">Assistant is thinking...</span>
                      </div>
                    </div>
                  )}

                  {voiceSessionState === "SPEAKING" && (
                    <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-indigo-50 border border-indigo-200 text-xs text-indigo-800 animate-fadeIn">
                      <div className="flex items-center gap-2">
                        <Volume2 size={14} className="text-indigo-600 animate-pulse" />
                        <span className="font-semibold">Assistant is speaking aloud...</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => voiceSessionRef.current?.stopAudio()}
                          className="px-2 py-0.5 rounded bg-indigo-200 hover:bg-indigo-300 text-indigo-900 font-semibold text-[11px] cursor-pointer"
                        >
                          Mute Audio
                        </button>
                        <button
                          type="button"
                          onClick={() => voiceSessionRef.current?.endSession()}
                          className="text-indigo-700 hover:underline text-[11px] cursor-pointer"
                        >
                          End Voice Chat
                        </button>
                      </div>
                    </div>
                  )}

                  {voiceSessionState === "WAITING_FOR_APPROVAL" && (
                    <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-amber-50 border border-amber-300 text-xs text-amber-900 animate-fadeIn">
                      <div className="flex items-center gap-2">
                        <ShieldAlert size={14} className="text-amber-600" />
                        <span className="font-semibold">Voice Paused:</span>
                        <span>Tool execution requires authorization. Review and approve/deny in chat above.</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => voiceSessionRef.current?.endSession()}
                        className="text-amber-800 hover:underline font-semibold cursor-pointer"
                      >
                        Cancel Voice Chat
                      </button>
                    </div>
                  )}

                  {voiceSessionState === "ERROR" && (
                    <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800 animate-fadeIn">
                      <div className="flex items-center gap-2">
                        <AlertCircle size={14} className="text-red-600" />
                        <span>Voice error detected. Check microphone permissions.</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => voiceSessionRef.current?.startSession()}
                        className="font-semibold underline cursor-pointer"
                      >
                        Retry
                      </button>
                    </div>
                  )}
                </>
              )}

              {/* Speech Error Banner */}
              {speechError && (
                <div className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs">
                  <div className="flex items-center gap-1.5">
                    <AlertCircle size={13} className="text-amber-600" />
                    <span>{speechError}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSpeechError(null)}
                    className="text-amber-600 hover:text-amber-900"
                  >
                    <X size={12} />
                  </button>
                </div>
              )}

              <form onSubmit={handleSendMessage} className="space-y-2">
                {/* Chat Control Toolbar: In-Chat Model Selector & Real-Time Token Usage */}
                <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs">
                  <div className="flex items-center gap-1.5">
                    <label className="text-[11px] font-medium text-gray-500 flex items-center gap-1">
                      <Sparkles size={11} className="text-blue-500" />
                      Model:
                    </label>
                    <select
                      value={activeChatModel}
                      onChange={(e) => setActiveChatModel(e.target.value)}
                      disabled={streaming}
                      className="text-[11px] font-medium bg-white border border-gray-200 rounded-md py-0.5 px-2 text-gray-700 outline-none hover:border-gray-300 focus:border-blue-500 shadow-2xs cursor-pointer"
                      title="Select model for this conversation"
                    >
                      <option value="auto">Auto ({activeAssistant?.default_model || "Provider Default"})</option>
                      <option value="openai/gpt-oss-20b">GPT-OSS 20B (Groq LPU — Free Tier)</option>
                      <option value="openai/gpt-oss-120b">GPT-OSS 120B (Groq LPU)</option>
                      <option value="gemini-3.5-flash-lite">Gemini 3.5 Flash-Lite (Google)</option>
                      <option value="gemini-3.8-flash">Gemini 3.8 Flash (Google)</option>
                      <option value="gpt-4o-mini">GPT-4o mini (OpenAI)</option>
                      <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet (Anthropic)</option>
                    </select>
                  </div>

                  {/* Usage & Token Counter */}
                  <div className="flex items-center gap-2 text-[11px] text-gray-500">
                    {lastUsage ? (
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-mono ${
                        lastUsage.is_estimated
                          ? "bg-amber-50 text-amber-700 border border-amber-200/60"
                          : "bg-emerald-50 text-emerald-700 border border-emerald-200/60"
                      }`}>
                        <Activity size={10} className={lastUsage.is_estimated ? "text-amber-500" : "text-emerald-500"} />
                        <span>
                          {lastUsage.is_estimated ? (
                            `~${lastUsage.total_tokens} tokens (est.)`
                          ) : (
                            `${lastUsage.total_tokens} tokens (${lastUsage.input_tokens} in / ${lastUsage.output_tokens} out)`
                          )}
                        </span>
                        <span className="text-gray-300">·</span>
                        <span>{Math.round(lastUsage.duration_ms)}ms</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-gray-50 text-gray-500 border border-gray-200 font-mono">
                        <Activity size={10} className="text-gray-400" />
                        <span>Session: {messages.reduce((acc, m) => acc + (m.token_count || 0), 0)} tokens ({messages.length} msgs)</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="relative flex items-center">
                  {/* Hidden File Input for Paperclip */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx,.txt,.csv,.html,.htm"
                    onChange={handleFileUpload}
                  />

                  {/* Attachment, Webpage & Mic Controls (Left of Textarea) */}
                  <div className="absolute left-2 flex items-center gap-1 z-10">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={uploadingAttachment || streaming}
                      className="p-1.5 rounded-lg text-gray-500 hover:text-blue-600 hover:bg-gray-100 transition-colors"
                      title="Attach document (PDF, DOCX, TXT, CSV, HTML)"
                    >
                      {uploadingAttachment ? (
                        <Spinner size="sm" />
                      ) : (
                        <Paperclip size={16} />
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setWebpageUrlError(null);
                        setShowAddWebModal(true);
                      }}
                      disabled={streaming}
                      className="p-1.5 rounded-lg text-gray-500 hover:text-blue-600 hover:bg-gray-100 transition-colors"
                      title="Add Webpage (Paste documentation or article URL to read)"
                    >
                      <Globe size={16} />
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
                        : `Message ${activeAssistant?.name || "Assistant"}... (e.g. paste URL or click globe to read)`
                    }
                    disabled={streaming}
                    className="w-full resize-none pl-28 pr-24 py-2.5 text-sm bg-gray-50 border border-gray-300 rounded-xl text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-600 focus:bg-white focus:ring-2 focus:ring-blue-500/20"
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
      {inspectCitation && (() => {
        const isWeb = inspectCitation.source_type === "web" || !!inspectCitation.source_url;
        const webUrl = inspectCitation.source_url || (inspectCitation.document_name.startsWith("http") ? inspectCitation.document_name : null);
        return (
          <Modal
            isOpen={true}
            onClose={() => setInspectCitation(null)}
            title={`Citation [${inspectCitation.citation_num}]: ${inspectCitation.document_name || "Document"}`}
            description={isWeb ? "Web Source · Verified Page Reference" : `Page ${inspectCitation.page_number || 1} · Verified Chunk Reference`}
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
                  <span className="font-semibold block text-gray-700">
                    {isWeb ? "Source Website:" : "Source Document:"}
                  </span>
                  <span className="truncate block">{inspectCitation.document_name}</span>
                </div>
                <div>
                  <span className="font-semibold block text-gray-700">
                    {isWeb ? "Source URL / Domain:" : "Page Reference:"}
                  </span>
                  {isWeb && webUrl ? (
                    <a
                      href={webUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline truncate block"
                    >
                      {inspectCitation.domain || webUrl}
                    </a>
                  ) : (
                    <span>Page {inspectCitation.page_number || 1}</span>
                  )}
                </div>
              </div>

              <div className="flex justify-between items-center pt-2 border-t border-gray-100">
                <div className="flex items-center gap-2">
                  {isWeb && webUrl && (
                    <>
                      <Button
                        variant="outline"
                        size="xs"
                        icon={ExternalLink}
                        onClick={() => window.open(webUrl, "_blank", "noopener,noreferrer")}
                      >
                        Open Source
                      </Button>
                      <Button
                        variant="secondary"
                        size="xs"
                        icon={Bookmark}
                        onClick={() => {
                          const cit = inspectCitation;
                          setInspectCitation(null);
                          handleOpenSaveWebSource(cit);
                        }}
                      >
                        Save to KB
                      </Button>
                    </>
                  )}
                </div>
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
        );
      })()}

      {/* M27: Save Web Source to Knowledge Base Modal */}
      {saveWebCitation && (
        <Modal
          isOpen={true}
          onClose={() => setSaveWebCitation(null)}
          title="Save Web Source to Knowledge Base"
          description="Index this external web reference into a shared Knowledge Base."
          maxWidth="md"
        >
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-emerald-50/60 border border-emerald-200/80 text-xs space-y-1">
              <div className="font-semibold text-emerald-950 flex items-center gap-1.5">
                <Globe size={13} className="text-emerald-600" />
                <span className="truncate">{saveWebCitation.document_name}</span>
              </div>
              <div className="text-emerald-700/80 font-mono text-[11px] truncate">
                {saveWebCitation.source_url || (saveWebCitation.document_name.startsWith("http") ? saveWebCitation.document_name : "")}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-gray-700">
                  Destination Knowledge Base
                </label>
                {activeAssistant && (
                  <span className="text-[10px] text-gray-500 font-medium">
                    Assistant: {activeAssistant.name}
                  </span>
                )}
              </div>
              {knowledgeBases.length === 0 ? (
                <p className="text-xs text-rose-600">
                  No Knowledge Bases found in this workspace. Please create a Knowledge Base first.
                </p>
              ) : (
                <div className="space-y-1.5">
                  <select
                    value={saveWebKbId}
                    onChange={(e) => setSaveWebKbId(e.target.value)}
                    className="w-full text-xs bg-white border border-gray-300 rounded-lg p-2 text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="">-- Select destination Knowledge Base --</option>
                    {connectedKBs.length > 0 && (
                      <optgroup label={`Connected to ${activeAssistant?.name || "Assistant"}`}>
                        {connectedKBs.map((kb) => (
                          <option key={kb.id} value={kb.id}>
                            ★ {kb.name} (Connected)
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {otherKBs.length > 0 && (
                      <optgroup label="Other Workspace Knowledge Bases">
                        {otherKBs.map((kb) => (
                          <option key={kb.id} value={kb.id}>
                            {kb.name}
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>

                  {/* Destination Status Indicator */}
                  {saveWebKbId ? (
                    connectedKbIds.includes(saveWebKbId) ? (
                      <p className="text-[11px] text-emerald-700 flex items-center gap-1 font-medium">
                        <CheckCircle2 size={12} className="text-emerald-600 shrink-0" />
                        <span>Connected to <strong>{activeAssistant?.name}</strong>. This assistant will be able to search and cite this source.</span>
                      </p>
                    ) : (
                      <div className="p-2 rounded bg-amber-50 border border-amber-200/70 text-[11px] text-amber-800 flex items-start gap-1.5">
                        <AlertCircle size={13} className="text-amber-600 shrink-0 mt-0.5" />
                        <span>Notice: <strong>{knowledgeBases.find((k) => k.id === saveWebKbId)?.name}</strong> is not connected to <strong>{activeAssistant?.name}</strong>. This assistant will not be able to retrieve from it until connected.</span>
                      </div>
                    )
                  ) : connectedKBs.length === 0 ? (
                    <div className="p-2 rounded bg-gray-50 border border-gray-200 text-[11px] text-gray-600">
                      This assistant doesn't have a connected Knowledge Base. Please choose a workspace Knowledge Base.
                    </div>
                  ) : (
                    <p className="text-[11px] text-gray-500">
                      Please select a destination Knowledge Base to save this web source.
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700">
                Document Title (Optional)
              </label>
              <input
                type="text"
                value={saveWebTitle}
                onChange={(e) => setSaveWebTitle(e.target.value)}
                placeholder="Title for saved web source"
                className="w-full text-xs bg-white border border-gray-300 rounded-lg p-2 text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700">
                Storage Mode
              </label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setSaveWebMode("REFERENCE")}
                  className={`p-2.5 rounded-lg border text-left transition-colors ${
                    saveWebMode === "REFERENCE"
                      ? "border-blue-500 bg-blue-50/50 text-blue-900"
                      : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  <div className="font-semibold text-xs flex items-center gap-1.5">
                    <Bookmark size={12} className="text-blue-600" />
                    <span>Reference</span>
                  </div>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    Bookmark URL & metadata. Safe and lightweight.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setSaveWebMode("NOTES")}
                  className={`p-2.5 rounded-lg border text-left transition-colors ${
                    saveWebMode === "NOTES"
                      ? "border-blue-500 bg-blue-50/50 text-blue-900"
                      : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  <div className="font-semibold text-xs flex items-center gap-1.5">
                    <FileText size={12} className="text-blue-600" />
                    <span>Notes</span>
                  </div>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    Index your notes linked to the source.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setSaveWebMode("SEARCHABLE_CONTENT")}
                  className={`p-2.5 rounded-lg border text-left transition-colors ${
                    saveWebMode === "SEARCHABLE_CONTENT" || saveWebMode === "FULL_CONTENT"
                      ? "border-blue-500 bg-blue-50/50 text-blue-900"
                      : "border-gray-200 bg-white text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  <div className="font-semibold text-xs flex items-center gap-1.5">
                    <FileText size={12} className="text-blue-600" />
                    <span>Searchable</span>
                  </div>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    Index full text for RAG (requires rights).
                  </p>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700">
                Notes / Summary (Optional)
              </label>
              <textarea
                value={saveWebNotes}
                onChange={(e) => setSaveWebNotes(e.target.value)}
                placeholder="Add optional notes or commentary about this web source..."
                rows={2}
                className="w-full text-xs bg-white border border-gray-300 rounded-lg p-2 text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-gray-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSaveWebCitation(null)}
                disabled={isSavingWebSource}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={Bookmark}
                onClick={handleSaveWebSource}
                disabled={isSavingWebSource || !saveWebKbId}
              >
                {isSavingWebSource ? "Saving..." : "Save Web Source"}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* M22 / M28.13: Knowledge Base Save / Promotion Modal */}
      {promoteAttachment && (
        <Modal
          isOpen={true}
          onClose={() => setPromoteAttachment(null)}
          title="Save to Knowledge"
          description="Permanently index this conversation attachment into a shared Knowledge Base."
          maxWidth="md"
        >
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 text-xs space-y-1">
              <div className="font-semibold text-gray-800">
                {promoteAttachment.filename || (promoteAttachment as any).original_filename || "Attachment"}
              </div>
              <div className="text-gray-500 font-mono">
                {(promoteAttachment.file_size / 1024).toFixed(0)} KB · {promoteAttachment.total_chunks ?? (promoteAttachment as any).chunk_count ?? 0} chunks extracted
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-gray-700">
                  Destination Knowledge Base
                </label>
                {activeAssistant && (
                  <span className="text-[10px] text-gray-500 font-medium">
                    Assistant: {activeAssistant.name}
                  </span>
                )}
              </div>
              {knowledgeBases.length === 0 ? (
                <p className="text-xs text-rose-600">
                  No Knowledge Bases found in this workspace. Please create a Knowledge Base first.
                </p>
              ) : (
                <div className="space-y-1.5">
                  <select
                    value={targetKbId}
                    onChange={(e) => setTargetKbId(e.target.value)}
                    className="w-full text-xs bg-white border border-gray-300 rounded-lg p-2 text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="">-- Select destination Knowledge Base --</option>
                    {connectedKBs.length > 0 && (
                      <optgroup label={`Connected to ${activeAssistant?.name || "Assistant"}`}>
                        {connectedKBs.map((kb) => (
                          <option key={kb.id} value={kb.id}>
                            ★ {kb.name} (Connected)
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {otherKBs.length > 0 && (
                      <optgroup label="Other Workspace Knowledge Bases">
                        {otherKBs.map((kb) => (
                          <option key={kb.id} value={kb.id}>
                            {kb.name}
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>

                  {/* Destination Status Indicator */}
                  {targetKbId ? (
                    connectedKbIds.includes(targetKbId) ? (
                      <p className="text-[11px] text-emerald-700 flex items-center gap-1 font-medium">
                        <CheckCircle2 size={12} className="text-emerald-600 shrink-0" />
                        <span>Connected to <strong>{activeAssistant?.name}</strong>. This assistant will be able to search and cite this document.</span>
                      </p>
                    ) : (
                      <div className="p-2 rounded bg-amber-50 border border-amber-200/70 text-[11px] text-amber-800 flex items-start gap-1.5">
                        <AlertCircle size={13} className="text-amber-600 shrink-0 mt-0.5" />
                        <span>Notice: <strong>{knowledgeBases.find((k) => k.id === targetKbId)?.name}</strong> is not connected to <strong>{activeAssistant?.name}</strong>. This assistant will not be able to retrieve answers from it until connected.</span>
                      </div>
                    )
                  ) : connectedKBs.length === 0 ? (
                    <div className="p-2 rounded bg-gray-50 border border-gray-200 text-[11px] text-gray-600">
                      This assistant doesn't have a connected Knowledge Base. Please choose a workspace Knowledge Base.
                    </div>
                  ) : (
                    <p className="text-[11px] text-gray-500">
                      Please select a destination Knowledge Base to save this document.
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-700">
                Document Title (Optional)
              </label>
              <input
                type="text"
                value={promoteTitle || ""}
                onChange={(e) => setPromoteTitle(e.target.value)}
                placeholder={promoteAttachment.filename || (promoteAttachment as any).original_filename || "Document title"}
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
                {isPromoting ? "Saving..." : "Save to Knowledge"}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* M28.7: Add Webpage Modal */}
      {showAddWebModal && (
        <Modal
          isOpen={true}
          onClose={() => {
            setShowAddWebModal(false);
            setWebpageUrlError(null);
          }}
          title="Add Webpage to Conversation"
          description="Read and analyze public documentation, articles, or tutorials in real time."
          maxWidth="md"
        >
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-gray-700">
                Webpage URL <span className="text-rose-500">*</span>
              </label>
              <input
                type="url"
                autoFocus
                value={webpageUrlInput}
                onChange={(e) => {
                  setWebpageUrlInput(e.target.value);
                  setWebpageUrlError(null);
                }}
                placeholder="https://www.w3schools.com/cpp/cpp_for_loop.asp"
                className="w-full text-xs bg-white border border-gray-300 rounded-lg p-2.5 text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono"
              />
              {webpageUrlError && (
                <p className="text-[11px] text-rose-600 font-medium">{webpageUrlError}</p>
              )}
            </div>

            {/* Quick Example Chips */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-medium text-gray-500">Quick test examples:</span>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => {
                    setWebpageUrlInput("https://www.w3schools.com/cpp/cpp_for_loop.asp");
                    setWebpagePromptInput("Explain C++ for loop syntax and show standard code examples.");
                    setWebpageUrlError(null);
                  }}
                  className="px-2.5 py-1 text-[11px] bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors"
                >
                  W3Schools C++ Loop
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setWebpageUrlInput("https://docs.python.org/3/tutorial/controlflow.html");
                    setWebpagePromptInput("Summarize Python control flow tools.");
                    setWebpageUrlError(null);
                  }}
                  className="px-2.5 py-1 text-[11px] bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors"
                >
                  Python Control Flow
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-gray-700">
                Question or Prompt (Optional)
              </label>
              <input
                type="text"
                value={webpagePromptInput}
                onChange={(e) => setWebpagePromptInput(e.target.value)}
                placeholder="e.g. Read this page and explain the syntax and examples"
                className="w-full text-xs bg-white border border-gray-300 rounded-lg p-2.5 text-gray-900 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="p-3 rounded-lg bg-blue-50/70 border border-blue-200/70 text-[11px] text-blue-900 space-y-1">
              <div className="font-semibold flex items-center gap-1.5">
                <Sparkles size={13} className="text-blue-600" />
                <span>Reading vs Permanent Knowledge Base</span>
              </div>
              <p className="text-blue-800">
                <strong>Read in Chat:</strong> Safe outbound fetch extracts main article content cleanly for this conversation.
              </p>
              <p className="text-blue-800">
                <strong>Save to KB:</strong> Permanently indexes this URL with vector embeddings for all assistants in your workspace.
              </p>
            </div>

            <div className="flex justify-between items-center pt-3 border-t border-gray-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setShowAddWebModal(false);
                  setWebpageUrlError(null);
                }}
              >
                Cancel
              </Button>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon={Bookmark}
                  onClick={() => {
                    const trimmed = webpageUrlInput.trim();
                    if (!trimmed || (!trimmed.startsWith("http://") && !trimmed.startsWith("https://"))) {
                      setWebpageUrlError("Please enter a valid HTTP/HTTPS URL first.");
                      return;
                    }
                    setShowAddWebModal(false);
                    handleOpenSaveWebSource({
                      id: `temp-${Date.now()}`,
                      chunk_id: null,
                      citation_text: "",
                      source_type: "web",
                      source_url: trimmed,
                      document_name: trimmed,
                      domain: trimmed.replace(/^https?:\/\//, "").split("/")[0],
                      snippet: "",
                      retrieved_at: new Date().toISOString(),
                      page_number: null,
                      citation_num: 1,
                    });
                  }}
                >
                  Save to KB
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  icon={Globe}
                  onClick={() => {
                    const trimmed = webpageUrlInput.trim();
                    if (!trimmed) {
                      setWebpageUrlError("Please enter a webpage URL.");
                      return;
                    }
                    if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
                      setWebpageUrlError("URL must begin with http:// or https://");
                      return;
                    }
                    const prompt = webpagePromptInput.trim()
                      ? `${webpagePromptInput.trim()}\n\nSource: ${trimmed}`
                      : `Please read this webpage and explain the key points: ${trimmed}`;
                    setInputMessage(prompt);
                    setShowAddWebModal(false);
                    setWebpageUrlInput("");
                    setWebpagePromptInput("");
                    setWebpageUrlError(null);
                  }}
                >
                  Read in Chat
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default function ConversationsWorkspacePage() {
  return (
    <React.Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-gray-50">
          <div className="flex flex-col items-center gap-2">
            <Spinner size="lg" />
            <span className="text-xs text-gray-500">Loading conversation workspace...</span>
          </div>
        </div>
      }
    >
      <ConversationsContent />
    </React.Suspense>
  );
}
