"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  AssistantItem,
  AssistantVersionItem,
  KnowledgeBaseItem,
} from "@/lib/api";
import {
  Bot,
  Layers,
  Sliders,
  History,
  Database,
  FileText,
  RotateCcw,
  Check,
  Save,
  Trash2,
  Sparkles,
  ShieldCheck,
  Eye,
  X,
  ChevronRight,
  Send,
  MessageSquare,
} from "lucide-react";

interface AssistantWorkspaceViewProps {
  assistant: AssistantItem;
  tenantKBs: KnowledgeBaseItem[];
  onUpdate: (updated: AssistantItem) => void;
  onDelete: (assistantId: string) => void;
  onStartChat: (assistant: AssistantItem) => void;
}

export default function AssistantWorkspaceView({
  assistant,
  tenantKBs,
  onUpdate,
  onDelete,
  onStartChat,
}: AssistantWorkspaceViewProps) {
  const [activeTab, setActiveTab] = useState<
    "overview" | "instructions" | "config" | "knowledge" | "versions"
  >("overview");

  // Form State
  const [name, setName] = useState(assistant.name);
  const [description, setDescription] = useState(assistant.description || "");
  const [audienceLevel, setAudienceLevel] = useState(assistant.audience_level || "general");
  const [responseStyle, setResponseStyle] = useState(assistant.response_style || "balanced");
  const [uncertaintyBehavior, setUncertaintyBehavior] = useState(assistant.uncertainty_behavior || "admit");
  const [citationStyle, setCitationStyle] = useState(assistant.citation_style || "strict");
  const [systemPrompt, setSystemPrompt] = useState(assistant.system_prompt || "");

  // Advanced technical settings
  const [mode, setMode] = useState<"simple" | "advanced">("simple");
  const [llmProvider, setLlmProvider] = useState(assistant.llm_provider || "omniroute");
  const [defaultModel, setDefaultModel] = useState(assistant.default_model || "auto");
  const [temperature, setTemperature] = useState(assistant.temperature ?? 0.7);
  const [maxTokens, setMaxTokens] = useState(assistant.max_tokens ?? 1024);
  const [retrievalMode, setRetrievalMode] = useState(assistant.retrieval_mode || "hybrid");
  const [topK, setTopK] = useState(assistant.top_k ?? 5);
  const [selectedKBIds, setSelectedKBIds] = useState<string[]>(assistant.connected_kb_ids || []);

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Versions State
  const [versions, setVersions] = useState<AssistantVersionItem[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState<AssistantVersionItem | null>(null);
  const [rollingBack, setRollingBack] = useState(false);

  // Sync state if assistant prop changes
  useEffect(() => {
    setName(assistant.name);
    setDescription(assistant.description || "");
    setAudienceLevel(assistant.audience_level || "general");
    setResponseStyle(assistant.response_style || "balanced");
    setUncertaintyBehavior(assistant.uncertainty_behavior || "admit");
    setCitationStyle(assistant.citation_style || "strict");
    setSystemPrompt(assistant.system_prompt || "");
    setLlmProvider(assistant.llm_provider || "omniroute");
    setDefaultModel(assistant.default_model || "auto");
    setTemperature(assistant.temperature ?? 0.7);
    setMaxTokens(assistant.max_tokens ?? 1024);
    setRetrievalMode(assistant.retrieval_mode || "hybrid");
    setTopK(assistant.top_k ?? 5);
    setSelectedKBIds(assistant.connected_kb_ids || []);
  }, [assistant]);

  // Load versions when versions tab is selected
  useEffect(() => {
    if (activeTab !== "versions") return;
    setLoadingVersions(true);
    api
      .listAssistantVersions(assistant.id)
      .then((res) => setVersions(res))
      .catch((err) => console.error("Failed to load versions", err))
      .finally(() => setLoadingVersions(false));
  }, [activeTab, assistant.id]);

  const handleSave = async (changeSummaryText?: string) => {
    setSaving(true);
    setError(null);
    setSaveSuccess(false);

    try {
      const updated = await api.updateAssistant(assistant.id, {
        name: name.trim(),
        description: description.trim() || undefined,
        audience_level: audienceLevel,
        response_style: responseStyle,
        uncertainty_behavior: uncertaintyBehavior,
        citation_style: citationStyle,
        llm_provider: llmProvider,
        default_model: defaultModel.trim(),
        temperature,
        max_tokens: maxTokens,
        retrieval_mode: retrievalMode,
        top_k: topK,
        system_prompt: systemPrompt.trim() || undefined,
        knowledge_base_ids: selectedKBIds,
        change_summary: changeSummaryText || "Updated configuration from Assistant Workspace",
      });

      onUpdate(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to update assistant");
    } finally {
      setSaving(false);
    }
  };

  const handleRollback = async (versionNum: number) => {
    if (!confirm(`Are you sure you want to rollback to version ${versionNum}? This will create a new version with that historical configuration.`)) {
      return;
    }

    setRollingBack(true);
    setError(null);
    try {
      const restored = await api.rollbackAssistantVersion(
        assistant.id,
        versionNum,
        `Rollback to configuration of version ${versionNum}`
      );
      onUpdate(restored);
      // Reload versions list
      const freshVersions = await api.listAssistantVersions(assistant.id);
      setVersions(freshVersions);
      setSelectedSnapshot(null);
    } catch (err: any) {
      setError(err.message || "Rollback failed");
    } finally {
      setRollingBack(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 overflow-hidden text-slate-100">
      {/* Header Banner */}
      <div className="px-6 py-5 border-b border-slate-800/80 bg-slate-900/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center shrink-0">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white tracking-tight">{assistant.name}</h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-blue-950 text-blue-400 border border-blue-900">
                v{assistant.current_version_num || 1}
              </span>
              {assistant.template_id && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
                  {assistant.template_id}
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Slug: <span className="font-mono text-slate-300">{assistant.slug}</span> &middot; Model:{" "}
              <span className="font-mono text-slate-300">{assistant.default_model}</span>
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onStartChat(assistant)}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
          >
            <MessageSquare className="w-3.5 h-3.5 text-blue-400" />
            <span>Open Chat</span>
          </button>

          <button
            type="button"
            disabled={saving}
            onClick={() => handleSave()}
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer shadow-lg shadow-blue-600/20 disabled:opacity-50"
          >
            {saving ? (
              <span>Saving...</span>
            ) : saveSuccess ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-300" />
                <span>Saved!</span>
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" />
                <span>Save Changes</span>
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-6 mt-4 p-3 rounded-xl bg-red-950/60 border border-red-800 text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Studio Navigation Tabs */}
      <div className="px-6 border-b border-slate-800/80 bg-slate-950 flex items-center gap-2 overflow-x-auto text-xs">
        <button
          onClick={() => setActiveTab("overview")}
          className={`py-3 px-3 font-semibold border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "overview"
              ? "border-blue-500 text-white"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Overview</span>
        </button>

        <button
          onClick={() => setActiveTab("instructions")}
          className={`py-3 px-3 font-semibold border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "instructions"
              ? "border-blue-500 text-white"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Instructions & Behavior</span>
        </button>

        <button
          onClick={() => setActiveTab("config")}
          className={`py-3 px-3 font-semibold border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "config"
              ? "border-blue-500 text-white"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>Model & Retrieval</span>
        </button>

        <button
          onClick={() => setActiveTab("knowledge")}
          className={`py-3 px-3 font-semibold border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "knowledge"
              ? "border-blue-500 text-white"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          <span>Knowledge Bases ({selectedKBIds.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("versions")}
          className={`py-3 px-3 font-semibold border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "versions"
              ? "border-blue-500 text-white"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <History className="w-3.5 h-3.5" />
          <span>Version History</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="flex-1 overflow-y-auto p-6 bg-slate-950">
        {/* ================================================================= */}
        {/* OVERVIEW TAB                                                      */}
        {/* ================================================================= */}
        {activeTab === "overview" && (
          <div className="max-w-4xl space-y-5 animate-fadeIn">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-[11px] text-slate-400 font-medium">Active Configuration</span>
                <div className="text-lg font-bold text-white">v{assistant.current_version_num || 1}</div>
                <span className="text-[10px] text-slate-500 font-mono">Immutable audit snapshots</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-[11px] text-slate-400 font-medium">Connected Knowledge</span>
                <div className="text-lg font-bold text-white">{selectedKBIds.length} Knowledge Bases</div>
                <span className="text-[10px] text-slate-500 font-mono">Grounded RAG sources</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-[11px] text-slate-400 font-medium">Target Audience</span>
                <div className="text-lg font-bold text-white capitalize">{audienceLevel}</div>
                <span className="text-[10px] text-slate-500 font-mono">Tone: {responseStyle}</span>
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Identity & Scope</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">Assistant Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:border-blue-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Template Blueprint</label>
                  <input
                    type="text"
                    disabled
                    value={assistant.template_id || "Custom Domain"}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950/60 border border-slate-800 text-slate-400 font-mono"
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-slate-400 mb-1">Description</label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:border-blue-500 outline-none"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* INSTRUCTIONS & BEHAVIOR TAB                                       */}
        {/* ================================================================= */}
        {activeTab === "instructions" && (
          <div className="max-w-4xl space-y-5 animate-fadeIn">
            {/* 4-Tier Trust Hierarchy Badge */}
            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex items-start gap-3 text-xs">
              <ShieldCheck className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-white block">Prompt Trust Hierarchy & Safety Layers</span>
                <span className="text-[11px] text-slate-400 block mt-0.5">
                  1. Platform Security (Immutable) &rarr; 2. Organization Policy &rarr; 3. Assistant Instructions (Configured below) &rarr; 4. Retrieved Documents (Untrusted reference material).
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Target Audience</label>
                <select
                  value={audienceLevel}
                  onChange={(e) => setAudienceLevel(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:border-blue-500 outline-none"
                >
                  <option value="general">General Public</option>
                  <option value="school">School Students</option>
                  <option value="undergraduate">University / Undergraduate</option>
                  <option value="employees">Employees</option>
                  <option value="customers">Customers</option>
                  <option value="researchers">Researchers</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Response Style</label>
                <select
                  value={responseStyle}
                  onChange={(e) => setResponseStyle(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:border-blue-500 outline-none"
                >
                  <option value="balanced">Balanced</option>
                  <option value="socratic">Socratic (Questions & active recall)</option>
                  <option value="concise">Concise (Bullet-points)</option>
                  <option value="detailed">Detailed (Comprehensive)</option>
                  <option value="professional">Professional</option>
                  <option value="friendly">Friendly & Empathetic</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">When Information is Missing</label>
                <select
                  value={uncertaintyBehavior}
                  onChange={(e) => setUncertaintyBehavior(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:border-blue-500 outline-none"
                >
                  <option value="admit">Honestly state missing</option>
                  <option value="clarify">Ask clarifying questions</option>
                  <option value="synthesize">Synthesize with disclaimer</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-slate-400 text-xs mb-1 font-semibold">
                Assistant Persona & Custom Instructions
              </label>
              <textarea
                rows={10}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-blue-500 outline-none font-mono text-xs leading-relaxed"
              />
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* MODEL & RETRIEVAL CONFIG TAB                                      */}
        {/* ================================================================= */}
        {activeTab === "config" && (
          <div className="max-w-4xl space-y-5 animate-fadeIn">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white tracking-tight">Model & Retrieval Parameters</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Tune technical inference and vector search parameters.
                </p>
              </div>

              {/* Mode Toggle */}
              <div className="flex items-center bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setMode("simple")}
                  className={`px-3 py-1 rounded-lg font-medium transition cursor-pointer ${
                    mode === "simple" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
                  }`}
                >
                  Simple Mode
                </button>
                <button
                  type="button"
                  onClick={() => setMode("advanced")}
                  className={`px-3 py-1 rounded-lg font-medium transition cursor-pointer ${
                    mode === "advanced" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
                  }`}
                >
                  Advanced Mode
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">LLM Provider</label>
                <select
                  value={llmProvider}
                  onChange={(e) => setLlmProvider(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono outline-none"
                >
                  <option value="omniroute">OmniRoute (Local Gateway)</option>
                  <option value="openai">OpenAI (Direct BYOK)</option>
                  <option value="mock">Offline Mock</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Model Name</label>
                <input
                  type="text"
                  value={defaultModel}
                  onChange={(e) => setDefaultModel(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Temperature ({temperature})</label>
                <input
                  type="range"
                  min="0.0"
                  max="1.5"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-blue-500 mt-2"
                />
              </div>
            </div>

            {mode === "advanced" && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs pt-3 border-t border-slate-800/80">
                <div>
                  <label className="block text-slate-400 mb-1">Retrieval Mode</label>
                  <select
                    value={retrievalMode}
                    onChange={(e) => setRetrievalMode(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono outline-none"
                  >
                    <option value="hybrid">Hybrid (BM25 + Semantic RRF)</option>
                    <option value="semantic">Semantic Only</option>
                    <option value="lexical">Lexical Only</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Top-K Chunks ({topK})</label>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={topK}
                    onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono outline-none"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Max Output Tokens</label>
                  <input
                    type="number"
                    min="64"
                    max="4096"
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(parseInt(e.target.value) || 1024)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono outline-none"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* CONNECTED KNOWLEDGE TAB                                           */}
        {/* ================================================================= */}
        {activeTab === "knowledge" && (
          <div className="max-w-4xl space-y-4 animate-fadeIn text-xs">
            <div>
              <h3 className="text-sm font-bold text-white tracking-tight">Connected Knowledge Bases</h3>
              <p className="text-slate-400 mt-0.5">
                Check or uncheck knowledge bases to include or exclude from this assistant's retrieval scope.
              </p>
            </div>

            {tenantKBs.length === 0 ? (
              <div className="p-8 rounded-2xl bg-slate-900/40 border border-slate-800 text-center text-slate-500">
                No knowledge bases created yet in this workspace.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {tenantKBs.map((kb) => {
                  const checked = selectedKBIds.includes(kb.id);
                  return (
                    <label
                      key={kb.id}
                      className={`p-3.5 rounded-2xl border transition cursor-pointer flex items-center justify-between select-none ${
                        checked
                          ? "bg-blue-950/20 border-blue-500 text-white"
                          : "bg-slate-900/40 border-slate-800 text-slate-300 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0 pr-2">
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
                          className="accent-blue-500 rounded w-4 h-4"
                        />
                        <div className="min-w-0">
                          <span className="font-semibold block truncate">{kb.name}</span>
                          <span className="text-[10px] text-slate-500 block truncate">
                            {kb.description || "No description"}
                          </span>
                        </div>
                      </div>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300 shrink-0">
                        {kb.document_count} docs
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* VERSION HISTORY & AUDITABLE ROLLBACK TAB                          */}
        {/* ================================================================= */}
        {activeTab === "versions" && (
          <div className="max-w-4xl space-y-4 animate-fadeIn text-xs">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white tracking-tight">Configuration Version History</h3>
                <p className="text-slate-400 mt-0.5">
                  Every configuration change generates an immutable, auditable snapshot. Rolling back creates a new forward version.
                </p>
              </div>

              <span className="px-2.5 py-1 rounded-full text-[11px] font-mono bg-slate-900 text-slate-400 border border-slate-800">
                {versions.length} total versions
              </span>
            </div>

            {loadingVersions ? (
              <div className="p-8 text-center text-slate-500">Loading version history...</div>
            ) : versions.length === 0 ? (
              <div className="p-8 text-center text-slate-500">No versions recorded yet.</div>
            ) : (
              <div className="rounded-2xl border border-slate-800 overflow-hidden bg-slate-900/40">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-mono text-[10px] uppercase">
                    <tr>
                      <th className="py-2.5 px-4">Version</th>
                      <th className="py-2.5 px-4">Change Summary</th>
                      <th className="py-2.5 px-4">Model</th>
                      <th className="py-2.5 px-4">Created At</th>
                      <th className="py-2.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                    {versions.map((v) => {
                      const isCurrent = v.version_num === (assistant.current_version_num || 1);
                      return (
                        <tr key={v.id} className="hover:bg-slate-900/60 transition">
                          <td className="py-3 px-4 font-bold text-white">
                            <span className="flex items-center gap-1.5">
                              v{v.version_num}
                              {isCurrent && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] bg-emerald-950 text-emerald-400 border border-emerald-900">
                                  Current
                                </span>
                              )}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-slate-300 font-sans text-xs">
                            {v.change_summary || "Configuration update"}
                          </td>
                          <td className="py-3 px-4 text-slate-400">{v.model_name}</td>
                          <td className="py-3 px-4 text-slate-500">
                            {new Date(v.created_at).toLocaleString()}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                type="button"
                                onClick={() => setSelectedSnapshot(v)}
                                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-sans transition cursor-pointer flex items-center gap-1"
                              >
                                <Eye className="w-3 h-3" />
                                <span>Inspect</span>
                              </button>

                              {!isCurrent && (
                                <button
                                  type="button"
                                  disabled={rollingBack}
                                  onClick={() => handleRollback(v.version_num)}
                                  className="px-2.5 py-1 rounded-lg bg-blue-950/60 hover:bg-blue-900 text-blue-300 border border-blue-900 text-[10px] font-sans transition cursor-pointer flex items-center gap-1 disabled:opacity-50"
                                >
                                  <RotateCcw className="w-3 h-3" />
                                  <span>Rollback</span>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Inspect Snapshot Modal */}
            {selectedSnapshot && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
                <div className="bg-slate-950 border border-slate-800 rounded-2xl max-w-2xl w-full p-5 space-y-3 shadow-2xl">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <h4 className="text-xs font-bold text-white font-mono">
                      Version Snapshot: v{selectedSnapshot.version_num}
                    </h4>
                    <button
                      onClick={() => setSelectedSnapshot(null)}
                      className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="max-h-96 overflow-y-auto p-3 rounded-xl bg-slate-900/60 border border-slate-800 font-mono text-[11px] text-slate-300">
                    <pre className="whitespace-pre-wrap">
                      {JSON.stringify(selectedSnapshot.config_snapshot, null, 2)}
                    </pre>
                  </div>

                  <div className="flex justify-end pt-2">
                    <button
                      onClick={() => setSelectedSnapshot(null)}
                      className="px-4 py-1.5 rounded-xl bg-slate-800 text-white text-xs font-medium hover:bg-slate-700"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
