"use client";

import React, { useEffect, useState, useRef, Suspense } from "react";
import { useParams } from "next/navigation";
import {
  api,
  PublicAssistantMetadata,
  MessageCitationItem,
} from "@/lib/api";
import {
  Bot,
  Send,
  Loader2,
  Sparkles,
  BookOpen,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  ShieldCheck,
} from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: MessageCitationItem[];
}

function PublicAssistantContent() {
  const params = useParams();
  const publicId = typeof params?.publicId === "string" ? params.publicId : "";

  const [assistant, setAssistant] = useState<PublicAssistantMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [expandedCitationIndex, setExpandedCitationIndex] = useState<number | null>(null);
  const [sessionToken, setSessionToken] = useState<string>("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Initialize or retrieve persistent anonymous visitor session token
  useEffect(() => {
    if (typeof window !== "undefined") {
      let token = localStorage.getItem(`mmaip_pub_session_${publicId}`);
      if (!token) {
        token = "sess_" + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
        localStorage.setItem(`mmaip_pub_session_${publicId}`, token);
      }
      setSessionToken(token);
    }
  }, [publicId]);

  // Load public assistant metadata
  useEffect(() => {
    if (!publicId) return;
    setLoading(true);
    api.getPublicAssistant(publicId)
      .then((data) => {
        setAssistant(data);
        if (data.custom_greeting) {
          setMessages([
            {
              id: "greeting",
              role: "assistant",
              content: data.custom_greeting,
            },
          ]);
        }
      })
      .catch((err) => {
        setError(err.message || "This assistant is not available or is currently private.");
      })
      .finally(() => setLoading(false));
  }, [publicId]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = input.trim();
    if (!query || isStreaming || !assistant) return;

    const userMsgId = "usr_" + Date.now();
    const assistantMsgId = "asst_" + Date.now();

    const newMessages: ChatMessage[] = [
      ...messages,
      { id: userMsgId, role: "user", content: query },
      { id: assistantMsgId, role: "assistant", content: "" },
    ];

    setMessages(newMessages);
    setInput("");
    setIsStreaming(true);
    setExpandedCitationIndex(null);

    let streamBuffer = "";
    const activeCitations: MessageCitationItem[] = [];

    try {
      await api.streamPublicChat(
        publicId,
        query,
        sessionToken,
        {
          onToken: (token: string) => {
            streamBuffer += token;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId ? { ...msg, content: streamBuffer } : msg
              )
            );
          },
          onCitations: (citations: MessageCitationItem[]) => {
            activeCitations.push(...citations);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId ? { ...msg, citations: [...activeCitations] } : msg
              )
            );
          },
          onCitation: (citation: MessageCitationItem) => {
            activeCitations.push(citation);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId ? { ...msg, citations: [...activeCitations] } : msg
              )
            );
          },
          onError: (err: string) => {
            streamBuffer += `\n\n*[Error: ${err}]*`;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId ? { ...msg, content: streamBuffer } : msg
              )
            );
          },
          onComplete: () => {
            setIsStreaming(false);
          },
        }
      );
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Network error";
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, content: `Error: Unable to connect to assistant (${errMsg}).` }
            : msg
        )
      );
    } finally {
      setIsStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-100">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-sky-500" />
          <p className="text-sm text-slate-400 font-mono">Connecting to assistant...</p>
        </div>
      </div>
    );
  }

  if (error || !assistant) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 p-4 text-slate-100">
        <div className="max-w-md w-full rounded-2xl border border-slate-800 bg-slate-900/60 p-8 text-center backdrop-blur-xl shadow-2xl">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-400">
            <AlertCircle className="h-7 w-7" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-100">Assistant Unavailable</h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">{error || "This assistant is currently private or unlisted."}</p>
        </div>
      </div>
    );
  }

  const brandColor = assistant.brand_color || "#0284c7";

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100 antialiased selection:bg-sky-500/20 selection:text-sky-300">
      {/* Top Header */}
      <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between border-b border-slate-800/80 bg-slate-950/80 px-6 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-xl font-bold text-white shadow-sm ring-1 ring-white/10"
            style={{ backgroundColor: brandColor }}
          >
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold tracking-tight text-slate-100">{assistant.name}</h1>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400 ring-1 ring-inset ring-emerald-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live
              </span>
            </div>
            {assistant.description && (
              <p className="text-xs text-slate-400 line-clamp-1">{assistant.description}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <ShieldCheck className="h-3.5 w-3.5 text-slate-500" />
          <span className="hidden sm:inline">Verified Public Assistant</span>
        </div>
      </header>

      {/* Chat Messages View */}
      <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div
                className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl shadow-lg ring-1 ring-white/10"
                style={{ backgroundColor: brandColor }}
              >
                <Sparkles className="h-7 w-7 text-white" />
              </div>
              <h2 className="text-lg font-semibold tracking-tight text-slate-200">
                Ask {assistant.name} anything
              </h2>
              <p className="mt-1 max-w-md text-xs text-slate-400">
                Ground-truth answers verified against public documentation with cited footnotes.
              </p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={msg.id || i}
                className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div
                    className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-xl text-white shadow-sm"
                    style={{ backgroundColor: brandColor }}
                  >
                    <Bot className="h-4 w-4" />
                  </div>
                )}

                <div
                  className={`relative max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                    msg.role === "user"
                      ? "bg-sky-600 text-white rounded-tr-sm"
                      : "bg-slate-900/90 text-slate-200 border border-slate-800/80 rounded-tl-sm backdrop-blur-md"
                  }`}
                >
                  <div className="whitespace-pre-wrap break-words">{msg.content || (isStreaming && i === messages.length - 1 ? <span className="inline-flex items-center gap-1 text-slate-400"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking...</span> : null)}</div>

                  {/* Citation Footnotes */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-800">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[11px] font-medium text-slate-400 flex items-center gap-1">
                          <BookOpen className="h-3 w-3" /> Sources:
                        </span>
                        {msg.citations.map((c, cIdx) => (
                          <button
                            key={cIdx}
                            type="button"
                            onClick={() =>
                              setExpandedCitationIndex(
                                expandedCitationIndex === cIdx ? null : cIdx
                              )
                            }
                            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-mono transition-colors ${
                              expandedCitationIndex === cIdx
                                ? "bg-sky-500/20 text-sky-300 ring-1 ring-sky-500/30"
                                : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
                            }`}
                          >
                            [{c.citation_num || (c as any).citation_number || cIdx + 1}] {c.document_name || (c as any).document_title || "Document"}
                            {expandedCitationIndex === cIdx ? (
                              <ChevronUp className="h-3 w-3" />
                            ) : (
                              <ChevronDown className="h-3 w-3" />
                            )}
                          </button>
                        ))}
                      </div>

                      {/* Expanded Citation Preview */}
                      {expandedCitationIndex !== null && msg.citations[expandedCitationIndex] && (
                        <div className="mt-2 rounded-lg border border-slate-800 bg-slate-950/80 p-3 text-xs text-slate-300">
                          <div className="flex items-center justify-between pb-1 text-[11px] font-semibold text-slate-400 border-b border-slate-800">
                            <span>{msg.citations[expandedCitationIndex].document_name || (msg.citations[expandedCitationIndex] as any).document_title}</span>
                            {msg.citations[expandedCitationIndex].page_number && (
                              <span>Page {msg.citations[expandedCitationIndex].page_number}</span>
                            )}
                          </div>
                          <p className="mt-2 italic leading-relaxed text-slate-300">
                            &ldquo;{msg.citations[expandedCitationIndex].snippet || msg.citations[expandedCitationIndex].citation_text}&rdquo;
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Bottom Message Input Bar */}
      <footer className="sticky bottom-0 z-20 border-t border-slate-800/80 bg-slate-950/90 p-4 backdrop-blur-md">
        <div className="mx-auto max-w-3xl">
          <form
            onSubmit={handleSend}
            className="flex items-end gap-2 rounded-2xl border border-slate-800 bg-slate-900/90 p-2 shadow-xl ring-1 ring-white/5 focus-within:border-slate-700 focus-within:ring-sky-500/30"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Message ${assistant.name}... (Press Enter to send, Shift+Enter for newline)`}
              rows={1}
              disabled={isStreaming}
              className="max-h-36 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-600 text-white shadow-md transition-all hover:bg-sky-500 disabled:opacity-40 disabled:hover:bg-sky-600 cursor-pointer disabled:cursor-not-allowed"
              style={{ backgroundColor: input.trim() && !isStreaming ? brandColor : undefined }}
            >
              {isStreaming ? (
                <Loader2 className="h-4 w-4 animate-spin text-white" />
              ) : (
                <Send className="h-4 w-4 text-white" />
              )}
            </button>
          </form>
          <div className="mt-2 flex items-center justify-between px-2 text-[11px] text-slate-400">
            <span>Powered by Multi-Tenant AI Platform</span>
            <span>All responses grounded in verified sources</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function PublicAssistantPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-100">
          <Loader2 className="h-8 w-8 animate-spin text-sky-500" />
        </div>
      }
    >
      <PublicAssistantContent />
    </Suspense>
  );
}
