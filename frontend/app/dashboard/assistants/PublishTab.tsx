"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  AssistantPublication,
  AssistantPublicationCreate,
} from "@/lib/api";
import {
  Globe,
  Lock,
  Building,
  Copy,
  Check,
  ExternalLink,
  Code2,
  AlertTriangle,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Eye,
  RefreshCw,
  Palette,
} from "lucide-react";

interface PublishTabProps {
  assistantId: string;
  assistantName: string;
  connectedKbCount: number;
  hasSystemPrompt: boolean;
  defaultModel: string;
}

const BRAND_PRESETS = [
  { name: "Sky Blue", hex: "#0284c7" },
  { name: "Indigo", hex: "#6366f1" },
  { name: "Emerald", hex: "#10b981" },
  { name: "Violet", hex: "#8b5cf6" },
  { name: "Amber", hex: "#f59e0b" },
  { name: "Rose", hex: "#f43f5e" },
  { name: "Slate Dark", hex: "#334155" },
];

export default function PublishTab({
  assistantId,
  assistantName,
  connectedKbCount,
  hasSystemPrompt,
  defaultModel,
}: PublishTabProps) {
  const [publication, setPublication] = useState<AssistantPublication | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const [copiedIframe, setCopiedIframe] = useState(false);

  // Form Fields
  const [visibility, setVisibility] = useState<"PRIVATE" | "WORKSPACE" | "PUBLIC">("PRIVATE");
  const [allowedDomainsStr, setAllowedDomainsStr] = useState("*");
  const [customGreeting, setCustomGreeting] = useState("");
  const [brandColor, setBrandColor] = useState("#0284c7");

  const [origin, setOrigin] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setOrigin(window.location.origin);
    }
  }, []);

  const loadPublication = async () => {
    setLoading(true);
    setError(null);
    try {
      const pub = await api.getAssistantPublication(assistantId);
      setPublication(pub);
      setVisibility(pub.visibility);
      setAllowedDomainsStr(pub.allowed_domains ? pub.allowed_domains.join(", ") : "*");
      setCustomGreeting(pub.custom_greeting || "");
      setBrandColor(pub.brand_color || "#0284c7");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load publication settings";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPublication();
  }, [assistantId]);

  const handlePublish = async () => {
    setSaving(true);
    setError(null);

    const domains = allowedDomainsStr
      .split(",")
      .map((d) => d.trim())
      .filter(Boolean);

    const payload: AssistantPublicationCreate = {
      visibility,
      allowed_domains: domains.length > 0 ? domains : ["*"],
      custom_greeting: customGreeting.trim() || null,
      brand_color: brandColor,
    };

    try {
      const updated = await api.publishAssistant(assistantId, payload);
      setPublication(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Publishing failed";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleUnpublish = async () => {
    if (!confirm("Are you sure you want to unpublish this assistant? Public links and embed widgets will immediately stop answering.")) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await api.unpublishAssistant(assistantId);
      setPublication(updated);
      setVisibility("PRIVATE");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unpublishing failed";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const publicLink = publication ? `${origin}/p/${publication.public_id}` : "";
  const embedSnippet = publication
    ? `<script\n  src="${origin}/api/v1/public/embed.js"\n  data-assistant-id="${publication.public_id}"\n  data-brand-color="${brandColor}"\n  async>\n</script>`
    : "";
  const iframeSnippet = publication
    ? `<iframe\n  src="${origin}/embed/${publication.public_id}"\n  width="400"\n  height="600"\n  frameborder="0"\n  style="border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3);"\n></iframe>`
    : "";

  const copyToClipboard = (text: string, type: "link" | "snippet" | "iframe") => {
    navigator.clipboard.writeText(text);
    if (type === "link") {
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } else if (type === "snippet") {
      setCopiedSnippet(true);
      setTimeout(() => setCopiedSnippet(false), 2000);
    } else {
      setCopiedIframe(true);
      setTimeout(() => setCopiedIframe(false), 2000);
    }
  };

  const isPubliclyLive = publication?.is_active && publication?.visibility === "PUBLIC";

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-sky-500" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6 animate-fadeIn text-gray-900">
      {/* Status Alert Banner */}
      {isPubliclyLive ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 shadow-xs flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700">
              <Globe className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-emerald-900">
                Assistant is Live and Publicly Accessible
              </h3>
              <p className="mt-0.5 text-xs text-emerald-700">
                Anyone with the link or visiting your embedded website can chat with {assistantName}.
                Only documents with access level <span className="font-mono font-semibold text-emerald-800">PUBLIC</span> are retrieved.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleUnpublish}
            disabled={saving}
            className="rounded-xl border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100 transition cursor-pointer"
          >
            Unpublish
          </button>
        </div>
      ) : (
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-xs flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gray-100 text-gray-500">
            <Lock className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">
              Assistant is Currently Private
            </h3>
            <p className="mt-0.5 text-xs text-gray-500">
              Only authorized members inside your workspace can test or chat with this assistant.
              Configure publishing options below to enable public links or embeddable widgets.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Readiness Preflight Checklist */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Pre-Publish Readiness Checklist
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
          <div className="flex items-center gap-2.5 rounded-xl border border-gray-200 bg-gray-50/70 p-3 text-xs">
            {hasSystemPrompt ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
            )}
            <div>
              <div className="font-medium text-gray-900">System Instructions</div>
              <div className="text-[11px] text-gray-500">
                {hasSystemPrompt ? "Configured & active" : "Default prompt"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 rounded-xl border border-gray-200 bg-gray-50/70 p-3 text-xs">
            {connectedKbCount > 0 ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
            )}
            <div>
              <div className="font-medium text-gray-900">Knowledge Bases</div>
              <div className="text-[11px] text-gray-500">
                {connectedKbCount > 0 ? `${connectedKbCount} KBs attached` : "No KBs linked"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 rounded-xl border border-gray-200 bg-gray-50/70 p-3 text-xs">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            <div>
              <div className="font-medium text-gray-900">Active Model</div>
              <div className="text-[11px] text-gray-500 font-mono">{defaultModel}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Visibility Radio Options */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs space-y-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Access & Visibility Tier
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <label
            className={`flex flex-col gap-2 rounded-xl border p-4 cursor-pointer transition ${
              visibility === "PRIVATE"
                ? "border-blue-500 bg-blue-50/50 ring-1 ring-blue-500/20"
                : "border-gray-200 bg-white hover:border-gray-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-medium text-xs text-gray-900">
                <Lock className="h-3.5 w-3.5 text-gray-500" />
                <span>Private</span>
              </div>
              <input
                type="radio"
                name="visibility"
                value="PRIVATE"
                checked={visibility === "PRIVATE"}
                onChange={() => setVisibility("PRIVATE")}
                className="text-blue-600 focus:ring-blue-500"
              />
            </div>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Restricted strictly to authorized workspace creators and admins.
            </p>
          </label>

          <label
            className={`flex flex-col gap-2 rounded-xl border p-4 cursor-pointer transition ${
              visibility === "WORKSPACE"
                ? "border-blue-500 bg-blue-50/50 ring-1 ring-blue-500/20"
                : "border-gray-200 bg-white hover:border-gray-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-medium text-xs text-gray-900">
                <Building className="h-3.5 w-3.5 text-gray-500" />
                <span>Workspace</span>
              </div>
              <input
                type="radio"
                name="visibility"
                value="WORKSPACE"
                checked={visibility === "WORKSPACE"}
                onChange={() => setVisibility("WORKSPACE")}
                className="text-blue-600 focus:ring-blue-500"
              />
            </div>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Available to all logged-in employees and members of this workspace.
            </p>
          </label>

          <label
            className={`flex flex-col gap-2 rounded-xl border p-4 cursor-pointer transition ${
              visibility === "PUBLIC"
                ? "border-emerald-500 bg-emerald-50/50 ring-1 ring-emerald-500/20"
                : "border-gray-200 bg-white hover:border-gray-300"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-medium text-xs text-gray-900">
                <Globe className="h-3.5 w-3.5 text-emerald-600" />
                <span>Public</span>
              </div>
              <input
                type="radio"
                name="visibility"
                value="PUBLIC"
                checked={visibility === "PUBLIC"}
                onChange={() => setVisibility("PUBLIC")}
                className="text-emerald-600 focus:ring-emerald-500"
              />
            </div>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Accessible via standalone web link and embeddable JavaScript widget.
            </p>
          </label>
        </div>
      </div>

      {/* Distribution & Customization Settings */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs space-y-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Public Widget Customization
        </h4>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Custom Welcome Greeting
            </label>
            <input
              type="text"
              value={customGreeting}
              onChange={(e) => setCustomGreeting(e.target.value)}
              placeholder="e.g., Hi! How can I help you today?"
              className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-xs text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
            <span className="text-[10px] text-gray-500 mt-1 block">
              Displayed as the opening message when visitors first load the assistant.
            </span>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              Brand Accent Color
            </label>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              {BRAND_PRESETS.map((p) => (
                <button
                  key={p.hex}
                  type="button"
                  onClick={() => setBrandColor(p.hex)}
                  className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs transition cursor-pointer ${
                    brandColor.toLowerCase() === p.hex.toLowerCase()
                      ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                      : "border-gray-200 bg-white text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                  }`}
                >
                  <span
                    className="h-3 w-3 rounded-full ring-1 ring-gray-300"
                    style={{ backgroundColor: p.hex }}
                  />
                  <span>{p.name}</span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 max-w-xs">
              <input
                type="color"
                value={brandColor}
                onChange={(e) => setBrandColor(e.target.value)}
                className="h-8 w-12 rounded cursor-pointer bg-transparent border-0"
              />
              <input
                type="text"
                value={brandColor}
                onChange={(e) => setBrandColor(e.target.value)}
                className="flex-1 rounded-xl border border-gray-300 bg-white px-3 py-1.5 text-xs font-mono text-gray-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Origin Domain Whitelist (CORS & Embed Guard)
            </label>
            <input
              type="text"
              value={allowedDomainsStr}
              onChange={(e) => setAllowedDomainsStr(e.target.value)}
              placeholder="e.g., example.com, app.example.com, or *"
              className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-xs font-mono text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
            <span className="text-[10px] text-gray-500 mt-1 block">
              Comma-separated list of origins allowed to host the embed widget. Use <code className="font-mono text-gray-700 bg-gray-100 px-1 py-0.5 rounded">*</code> for unrestricted access.
            </span>
          </div>
        </div>

        <div className="pt-2">
          <button
            type="button"
            onClick={handlePublish}
            disabled={saving}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition cursor-pointer disabled:opacity-50"
          >
            {saving ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Applying Changes...</span>
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5" />
                <span>Save Publication Settings</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Integration Code Snippets (Available when published or public) */}
      {publication && (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-xs space-y-5">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Distribution Channels & Snippets
          </h4>

          {/* 1. Public Web Link */}
          <div className="space-y-2">
            <span className="text-xs font-medium text-gray-800 flex items-center gap-2">
              <Globe className="h-3.5 w-3.5 text-blue-600" />
              Standalone Public Chat Page
            </span>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={publicLink}
                className="flex-1 rounded-xl border border-gray-300 bg-gray-50 px-3 py-2 text-xs font-mono text-gray-800 select-all focus:outline-none"
              />
              <button
                type="button"
                onClick={() => copyToClipboard(publicLink, "link")}
                className="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 px-3 py-2 text-xs font-medium text-gray-700 transition cursor-pointer shadow-xs"
              >
                {copiedLink ? (
                  <Check className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                <span>{copiedLink ? "Copied" : "Copy"}</span>
              </button>
              <a
                href={`/p/${publication.public_id}`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 px-3 py-2 text-xs font-medium text-white transition cursor-pointer shadow-xs"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                <span>Open</span>
              </a>
            </div>
          </div>

          {/* 2. JavaScript Embed Script */}
          <div className="space-y-2 pt-2 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-800 flex items-center gap-2">
                <Code2 className="h-3.5 w-3.5 text-emerald-600" />
                Floating Chat Widget (Drop-in JavaScript)
              </span>
              <button
                type="button"
                onClick={() => copyToClipboard(embedSnippet, "snippet")}
                className="flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
              >
                {copiedSnippet ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                <span>{copiedSnippet ? "Copied Snippet" : "Copy Snippet"}</span>
              </button>
            </div>
            <pre className="rounded-xl border border-gray-800 bg-gray-900 p-3 text-[11px] font-mono text-gray-100 overflow-x-auto leading-relaxed">
              {embedSnippet}
            </pre>
            <p className="text-[10px] text-gray-500">
              Paste this tag into your website's <code className="text-gray-700 bg-gray-100 px-1 py-0.5 rounded font-mono">&lt;body&gt;</code> before closing. A floating trigger button will automatically appear.
            </p>
          </div>

          {/* 3. Inline Iframe */}
          <div className="space-y-2 pt-2 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-800 flex items-center gap-2">
                <Eye className="h-3.5 w-3.5 text-indigo-600" />
                Inline Embed (Iframe Container)
              </span>
              <button
                type="button"
                onClick={() => copyToClipboard(iframeSnippet, "iframe")}
                className="flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
              >
                {copiedIframe ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                <span>{copiedIframe ? "Copied Iframe" : "Copy Iframe"}</span>
              </button>
            </div>
            <pre className="rounded-xl border border-gray-800 bg-gray-900 p-3 text-[11px] font-mono text-gray-100 overflow-x-auto leading-relaxed">
              {iframeSnippet}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
