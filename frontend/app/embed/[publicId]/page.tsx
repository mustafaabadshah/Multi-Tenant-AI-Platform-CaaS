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
  BookOpen,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  X,
  Minimize2,
} from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: MessageCitationItem[];
}

function EmbedChatWidgetContent() {
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
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      let token = sessionStorage.getItem(`mmaip_embed_session_${publicId}`);
      if (!token) {
        token = "embed_" + Math.random().toString(36).substring(2, 15);
        sessionStorage.setItem(`mmaip_embed_session_${publicId}`, token);
      }
      setSessionToken(token);
    }
  }, [publicId]);

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
        setError(err.message || "Assistant unavailable.");
      })
      .finally(() => setLoading(false));
  }, [publicId]);

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
      const errMsg = err instanceof Error ? err.message : "Connection failed";
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, content: `Error: ${errMsg}` }
            : msg
        )
      );
    } finally {
      setIsStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleCloseParentWidget = () => {
    // Notify host window to toggle widget collapse
    if (typeof window !== "undefined" && window.parent) {
      window.parent.postMessage({ type: "mmaip:toggle-widget" }, "*");
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900 text-slate-200">
        <Loader2 className="h-6 w-6 animate-spin text-sky-500" />
      </div>
    );
  }

  if (error || !assistant) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900 p-4 text-center text-slate-200">
        <div className="flex flex-col items-center gap-2">
          <AlertCircle className="h-6 w-6 text-rose-400" />
          <p className="text-xs text-slate-400">{error || "Assistant unavailable"}</p>
        </div>
      </div>
    );
  }

  const brandColor = assistant.brand_color || "#0284c7";

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100 antialiased select-none">
      {/* Widget Header */}
      <header
        className="flex h-14 shrink-0 items-center justify-between px-4 text-white shadow-md"
        style={{ backgroundColor: brandColor }}
      >
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/20 backdrop-blur-sm">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-white leading-tight">
              {assistant.name}
            </h2>
            <span className="text-[11px] text-white/80">Support Assistant</span>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={handleCloseParentWidget}
            className="flex h-7 w-7 items-center justify-center rounded-md bg-white/10 hover:bg-white/20 text-white transition-colors cursor-pointer"
            title="Minimize"
          >
            <Minimize2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      {/* Widget Messages */}
      <main className="flex-1 overflow-y-auto p-3 space-y-3 bg-slate-950 text-xs">
        {messages.map((msg, i) => (
          <div
            key={msg.id || i}
            className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-white shadow-sm mt-0.5"
                style={{ backgroundColor: brandColor }}
              >
                <Bot className="h-3 w-3" />
              </div>
            )}

            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 leading-relaxed ${
                msg.role === "user"
                  ? "bg-sky-600 text-white rounded-tr-none"
                  : "bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none shadow-sm"
              }`}
            >
              <div className="whitespace-pre-wrap break-words">{msg.content || (isStreaming && i === messages.length - 1 ? "..." : "")}</div>

              {/* Citations */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-800 text-[10px]">
                  <div className="flex flex-wrap gap-1">
                    {msg.citations.map((c, cIdx) => (
                      <button
                        key={cIdx}
                        type="button"
                        onClick={() =>
                          setExpandedCitationIndex(
                            expandedCitationIndex === cIdx ? null : cIdx
                          )
                        }
                        className="inline-flex items-center gap-0.5 rounded bg-slate-800 px-1.5 py-0.5 text-slate-300 hover:bg-slate-700"
                      >
                        [{c.citation_num || (c as any).citation_number || cIdx + 1}] {c.document_name || (c as any).document_title || "Document"}
                      </button>
                    ))}
                  </div>
                  {expandedCitationIndex !== null && msg.citations[expandedCitationIndex] && (
                    <div className="mt-1.5 rounded bg-slate-950 p-2 text-[10px] text-slate-400 italic">
                      &ldquo;{msg.citations[expandedCitationIndex].snippet || msg.citations[expandedCitationIndex].citation_text}&rdquo;
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </main>

      {/* Widget Input Bar */}
      <footer className="border-t border-slate-800 bg-slate-900/90 p-2.5">
        <form onSubmit={handleSend} className="flex items-center gap-1.5">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your question..."
            disabled={isStreaming}
            className="flex-1 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-slate-700"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-600 text-white transition-opacity hover:opacity-90 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
            style={{ backgroundColor: input.trim() && !isStreaming ? brandColor : undefined }}
          >
            {isStreaming ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
          </button>
        </form>
      </footer>
    </div>
  );
}

export default function EmbedChatWidgetPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-slate-900 text-slate-200">
          <Loader2 className="h-6 w-6 animate-spin text-sky-500" />
        </div>
      }
    >
      <EmbedChatWidgetContent />
    </Suspense>
  );
}
