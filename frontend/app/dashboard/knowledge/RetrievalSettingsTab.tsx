"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  api,
  RetrievalConfigItem,
  EmbeddingProviderItem,
} from "@/lib/api";
import {
  Sliders,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Key,
  ShieldCheck,
  Cpu,
  Layers,
  Database,
  RefreshCw,
} from "lucide-react";

interface RetrievalSettingsTabProps {
  kbId: string;
  onConfigSaved?: () => void;
}

export default function RetrievalSettingsTab({
  kbId,
  onConfigSaved,
}: RetrievalSettingsTabProps) {
  const [config, setConfig] = useState<RetrievalConfigItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Providers metadata
  const [providers, setProviders] = useState<EmbeddingProviderItem[]>([]);

  // Secret inputs
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [qdrantKeyInput, setQdrantKeyInput] = useState("");

  // Validation states
  const [validatingProvider, setValidatingProvider] = useState(false);
  const [providerValidationMsg, setProviderValidationMsg] = useState<{
    valid: boolean;
    message: string;
  } | null>(null);

  const [validatingStore, setValidatingStore] = useState(false);
  const [storeValidationMsg, setStoreValidationMsg] = useState<{
    valid: boolean;
    message: string;
  } | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [cfg, provs] = await Promise.all([
        api.getRetrievalConfig(kbId),
        api.listEmbeddingProviders().catch(() => []),
      ]);
      setConfig(cfg);
      setProviders(provs);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load retrieval config.");
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const payload: Partial<RetrievalConfigItem> & {
        api_key?: string;
        qdrant_api_key?: string;
      } = {
        retrieval_mode: config.retrieval_mode,
        vector_store: config.vector_store,
        embedding_provider: config.embedding_provider,
        embedding_model: config.embedding_model,
        embedding_dimensions: config.embedding_dimensions,
        top_k: Number(config.top_k),
        similarity_metric: config.similarity_metric,
        similarity_threshold: config.similarity_threshold ? Number(config.similarity_threshold) : null,
        rrf_k: Number(config.rrf_k),
        reranking_enabled: Boolean(config.reranking_enabled),
        qdrant_url: config.qdrant_url || undefined,
        qdrant_collection: config.qdrant_collection || undefined,
      };

      if (apiKeyInput.trim()) {
        payload.api_key = apiKeyInput.trim();
      }
      if (qdrantKeyInput.trim()) {
        payload.qdrant_api_key = qdrantKeyInput.trim();
      }

      const updated = await api.updateRetrievalConfig(kbId, payload);
      setConfig(updated);
      setApiKeyInput("");
      setQdrantKeyInput("");
      setSuccessMsg("Retrieval & vector settings updated successfully.");
      if (onConfigSaved) onConfigSaved();
      setTimeout(() => setSuccessMsg(null), 3500);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to save configuration.");
    } finally {
      setSaving(false);
    }
  };

  const handleValidateProvider = async () => {
    if (!config) return;
    setValidatingProvider(true);
    setProviderValidationMsg(null);
    try {
      const res = await api.validateEmbeddingProvider({
        provider: config.embedding_provider,
        model: config.embedding_model,
        api_key: apiKeyInput.trim() || undefined,
      });
      setProviderValidationMsg({
        valid: res.valid,
        message: res.message,
      });
    } catch (err) {
      setProviderValidationMsg({
        valid: false,
        message: err instanceof Error ? err.message : "Provider validation failed.",
      });
    } finally {
      setValidatingProvider(false);
    }
  };

  const handleValidateStore = async () => {
    if (!config) return;
    setValidatingStore(true);
    setStoreValidationMsg(null);
    try {
      const res = await api.validateVectorStore({
        vector_store: config.vector_store,
        qdrant_url: config.qdrant_url || undefined,
        qdrant_api_key: qdrantKeyInput.trim() || undefined,
        qdrant_collection: config.qdrant_collection || undefined,
      });
      setStoreValidationMsg({
        valid: res.valid,
        message: res.message,
      });
    } catch (err) {
      setStoreValidationMsg({
        valid: false,
        message: err instanceof Error ? err.message : "Store validation failed.",
      });
    } finally {
      setValidatingStore(false);
    }
  };

  if (loading) {
    return (
      <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
        <span>Loading retrieval settings...</span>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="p-8 text-center text-xs text-red-400">
        Failed to load retrieval configuration.
      </div>
    );
  }

  const isFtsOnly = config.vector_store === "fts" || config.retrieval_mode === "lexical";
  const isQdrant = config.vector_store === "qdrant";
  const selectedProviderMeta = providers.find((p) => p.name === config.embedding_provider);

  return (
    <form onSubmit={handleSave} className="space-y-6 max-w-4xl animate-fadeIn">
      {/* Notifications */}
      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Section 1: Retrieval Mode & Strategy */}
      <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-gray-200">
          <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
            <Sliders className="w-3.5 h-3.5" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
              Retrieval Strategy & Mode
            </h2>
            <p className="text-[11px] text-gray-500">
              Select how queries are matched against document chunks
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Hybrid Mode */}
          <div
            onClick={() => setConfig({ ...config, retrieval_mode: "hybrid" })}
            className={`p-3.5 rounded-xl border transition cursor-pointer flex flex-col justify-between ${
              config.retrieval_mode === "hybrid"
                ? "bg-amber-50/60 border-amber-500 shadow-xs ring-1 ring-amber-500/20"
                : "bg-white border-gray-200 hover:border-gray-300 shadow-xs"
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-bold text-gray-900">Hybrid (RRF)</span>
                {config.retrieval_mode === "hybrid" && (
                  <span className="w-2 h-2 rounded-full bg-amber-600" />
                )}
              </div>
              <p className="text-[11px] text-gray-600 leading-relaxed">
                Combines full-text lexical keywords with dense semantic vector search using Reciprocal Rank Fusion.
              </p>
            </div>
            <span className="text-[10px] font-mono text-amber-700 font-semibold mt-3 block">
              Recommended for General RAG
            </span>
          </div>

          {/* Semantic Mode */}
          <div
            onClick={() => setConfig({ ...config, retrieval_mode: "semantic" })}
            className={`p-3.5 rounded-xl border transition cursor-pointer flex flex-col justify-between ${
              config.retrieval_mode === "semantic"
                ? "bg-amber-50/60 border-amber-500 shadow-xs ring-1 ring-amber-500/20"
                : "bg-white border-gray-200 hover:border-gray-300 shadow-xs"
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-bold text-gray-900">Semantic Only</span>
                {config.retrieval_mode === "semantic" && (
                  <span className="w-2 h-2 rounded-full bg-amber-600" />
                )}
              </div>
              <p className="text-[11px] text-gray-600 leading-relaxed">
                Uses vector embeddings and cosine similarity to find conceptual meanings even when keywords differ.
              </p>
            </div>
            <span className="text-[10px] font-mono text-gray-500 mt-3 block">
              Requires Active Embeddings
            </span>
          </div>

          {/* Lexical Mode */}
          <div
            onClick={() => setConfig({ ...config, retrieval_mode: "lexical" })}
            className={`p-3.5 rounded-xl border transition cursor-pointer flex flex-col justify-between ${
              config.retrieval_mode === "lexical"
                ? "bg-amber-50/60 border-amber-500 shadow-xs ring-1 ring-amber-500/20"
                : "bg-white border-gray-200 hover:border-gray-300 shadow-xs"
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-bold text-gray-900">Lexical Only (FTS)</span>
                {config.retrieval_mode === "lexical" && (
                  <span className="w-2 h-2 rounded-full bg-amber-600" />
                )}
              </div>
              <p className="text-[11px] text-gray-600 leading-relaxed">
                Pure PostgreSQL full-text search. Fast, zero embedding costs, no vector store required.
              </p>
            </div>
            <span className="text-[10px] font-mono text-emerald-700 mt-3 block">
              Zero Vector Overhead
            </span>
          </div>
        </div>
      </div>

      {/* Section 2: Vector Store Selection */}
      <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-gray-200">
          <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
            <Database className="w-3.5 h-3.5" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
              Vector Database Engine
            </h2>
            <p className="text-[11px] text-gray-500">
              Storage and indexing engine for vector embeddings
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* pgvector */}
          <div
            onClick={() => setConfig({ ...config, vector_store: "pgvector" })}
            className={`p-3.5 rounded-xl border transition cursor-pointer ${
              config.vector_store === "pgvector"
                ? "bg-amber-50/60 border-amber-500 shadow-xs ring-1 ring-amber-500/20"
                : "bg-white border-gray-200 hover:border-gray-300 shadow-xs"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-gray-900">PostgreSQL pgvector</span>
              {config.vector_store === "pgvector" && (
                <span className="w-2 h-2 rounded-full bg-amber-600" />
              )}
            </div>
            <p className="text-[11px] text-gray-600">
              Direct vector indexing inside PostgreSQL. Atomic ACID compliance with relational data.
            </p>
          </div>

          {/* Qdrant */}
          <div
            onClick={() => setConfig({ ...config, vector_store: "qdrant" })}
            className={`p-3.5 rounded-xl border transition cursor-pointer ${
              config.vector_store === "qdrant"
                ? "bg-amber-50/60 border-amber-500 shadow-xs ring-1 ring-amber-500/20"
                : "bg-white border-gray-200 hover:border-gray-300 shadow-xs"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-gray-900">Qdrant Vector DB</span>
              {config.vector_store === "qdrant" && (
                <span className="w-2 h-2 rounded-full bg-amber-600" />
              )}
            </div>
            <p className="text-[11px] text-gray-600">
              High-throughput external vector engine with HNSW indexing and payload filtering.
            </p>
          </div>

          {/* FTS only */}
          <div
            onClick={() => setConfig({ ...config, vector_store: "fts" })}
            className={`p-3.5 rounded-xl border transition cursor-pointer ${
              config.vector_store === "fts"
                ? "bg-amber-50/60 border-amber-500 shadow-xs ring-1 ring-amber-500/20"
                : "bg-white border-gray-200 hover:border-gray-300 shadow-xs"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-gray-900">PostgreSQL FTS (Vectorless)</span>
              {config.vector_store === "fts" && (
                <span className="w-2 h-2 rounded-full bg-amber-600" />
              )}
            </div>
            <p className="text-[11px] text-gray-600">
              Keyword ranking with language tokenization. No vector extensions needed.
            </p>
          </div>
        </div>

        {/* Qdrant Config Fields */}
        {isQdrant && (
          <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-3 mt-3">
            <span className="text-xs font-semibold text-gray-900 block">
              Qdrant Connection Settings
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-gray-700 text-[11px] mb-1">Qdrant Server URL</label>
                <input
                  type="text"
                  value={config.qdrant_url || "http://localhost:6333"}
                  onChange={(e) => setConfig({ ...config, qdrant_url: e.target.value })}
                  placeholder="http://localhost:6333"
                  className="w-full px-3 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-900 font-mono text-xs focus:border-amber-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-gray-700 text-[11px] mb-1">Collection Name</label>
                <input
                  type="text"
                  value={config.qdrant_collection || "mmaip_chunks"}
                  onChange={(e) => setConfig({ ...config, qdrant_collection: e.target.value })}
                  placeholder="mmaip_chunks"
                  className="w-full px-3 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-900 font-mono text-xs focus:border-amber-500 outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-gray-700 text-[11px] mb-1">
                Qdrant API Key (BYOK / Cloud)
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={qdrantKeyInput}
                  onChange={(e) => setQdrantKeyInput(e.target.value)}
                  placeholder={
                    config.has_qdrant_key
                      ? `Key configured: ${config.qdrant_key_masked} (leave empty to keep)`
                      : "Optional for local Qdrant"
                  }
                  className="flex-1 px-3 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-900 font-mono text-xs focus:border-amber-500 outline-none"
                />
                <button
                  type="button"
                  onClick={handleValidateStore}
                  disabled={validatingStore}
                  className="px-3 py-1.5 rounded-lg bg-white hover:bg-gray-100 border border-gray-200 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer shadow-xs"
                >
                  {validatingStore && <Loader2 className="w-3 h-3 animate-spin" />}
                  <span>Test Store</span>
                </button>
              </div>
              {storeValidationMsg && (
                <div
                  className={`mt-2 p-2 rounded-lg text-[11px] ${
                    storeValidationMsg.valid
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-red-50 text-red-700 border border-red-200"
                  }`}
                >
                  {storeValidationMsg.message}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Section 3: Embedding Provider (Hidden in FTS-only mode) */}
      {!isFtsOnly ? (
        <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-gray-200">
            <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Cpu className="w-3.5 h-3.5" />
            </div>
            <div>
              <h2 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                Embedding Provider & Model
              </h2>
              <p className="text-[11px] text-gray-500">
                Vector transformation models and BYOK credential configuration
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block text-gray-700 font-medium mb-1">
                Provider Architecture
              </label>
              <select
                value={config.embedding_provider}
                onChange={(e) => {
                  const prov = e.target.value as RetrievalConfigItem["embedding_provider"];
                  const meta = providers.find((p) => p.name === prov);
                  setConfig({
                    ...config,
                    embedding_provider: prov,
                    embedding_model: meta?.default_model || config.embedding_model,
                    embedding_dimensions: meta?.default_dimensions || config.embedding_dimensions,
                  });
                }}
                className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none"
              >
                <option value="omniroute">OmniRoute (Local AI Gateway • Default)</option>
                <option value="openai">OpenAI Direct API (BYOK)</option>
                <option value="local">Local CPU (Lightweight Feature Projection)</option>
                <option value="mock">Mock Provider (Deterministic Offline Testing)</option>
              </select>
              {selectedProviderMeta && (
                <span className="text-[11px] text-gray-500 mt-1 block">
                  {selectedProviderMeta.description}
                </span>
              )}
            </div>

            <div>
              <label className="block text-gray-700 font-medium mb-1">
                Model Identifier
              </label>
              <input
                type="text"
                value={config.embedding_model}
                onChange={(e) => setConfig({ ...config, embedding_model: e.target.value })}
                className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono focus:border-amber-500 outline-none"
              />
              <span className="text-[11px] text-gray-500 mt-1 block">
                Standard: text-embedding-3-small, text-embedding-ada-002, auto
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs pt-2">
            <div>
              <label className="block text-gray-700 font-medium mb-1">
                Vector Dimensions
              </label>
              <input
                type="number"
                value={config.embedding_dimensions}
                onChange={(e) =>
                  setConfig({ ...config, embedding_dimensions: parseInt(e.target.value) || 1536 })
                }
                className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono focus:border-amber-500 outline-none"
              />
              <span className="text-[11px] text-gray-500 mt-1 block">
                Matches vector store index dimensions (1536, 768, 384)
              </span>
            </div>

            <div>
              <label className="block text-gray-700 font-medium mb-1">
                Embedding Version
              </label>
              <div className="px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 text-amber-700 font-mono font-semibold flex items-center justify-between">
                <span>v{config.embedding_version}</span>
                <span className="text-[10px] text-gray-500 font-sans">
                  Incremented on model migration
                </span>
              </div>
            </div>
          </div>

          {/* BYOK API Key Input */}
          <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-2 mt-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-900 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-amber-600" />
                <span>Provider API Key (Fernet-Encrypted BYOK)</span>
              </span>
              {config.has_api_key && (
                <span className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  <ShieldCheck className="w-3 h-3" />
                  Key configured: {config.api_key_masked}
                </span>
              )}
            </div>

            <div className="flex gap-2 text-xs">
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder={
                  config.has_api_key
                    ? "Enter new API key to rotate secret..."
                    : "Enter API key (OmniRoute or OpenAI)..."
                }
                className="flex-1 px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono focus:border-amber-500 outline-none"
              />
              <button
                type="button"
                onClick={handleValidateProvider}
                disabled={validatingProvider}
                className="px-4 py-2 rounded-xl bg-white hover:bg-gray-100 border border-gray-200 text-gray-700 font-medium flex items-center gap-1.5 transition cursor-pointer shadow-xs"
              >
                {validatingProvider && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Validate Key</span>
              </button>
            </div>

            {providerValidationMsg && (
              <div
                className={`p-2.5 rounded-lg text-[11px] mt-1 ${
                  providerValidationMsg.valid
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-red-50 text-red-700 border border-red-200"
                }`}
              >
                {providerValidationMsg.message}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-700 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>
            <strong>FTS-Only Mode Active:</strong> Embedding generation is bypassed. Documents are indexed instantly for lexical full-text search with zero vector storage or API usage.
          </span>
        </div>
      )}

      {/* Section 4: Retrieval Hyperparameters & RRF */}
      <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-gray-200">
          <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
            <Layers className="w-3.5 h-3.5" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
              Retrieval Parameters & Ranking
            </h2>
            <p className="text-[11px] text-gray-500">
              Candidate limits, Reciprocal Rank Fusion constants, and reranking
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block text-gray-700 font-medium mb-1">
              Top-K Passages
            </label>
            <input
              type="number"
              min={1}
              max={50}
              value={config.top_k}
              onChange={(e) => setConfig({ ...config, top_k: parseInt(e.target.value) || 8 })}
              className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono focus:border-amber-500 outline-none"
            />
            <span className="text-[11px] text-gray-500 mt-1 block">
              Chunks returned per query
            </span>
          </div>

          <div>
            <label className="block text-gray-700 font-medium mb-1">
              Similarity Metric
            </label>
            <select
              value={config.similarity_metric}
              onChange={(e) => setConfig({ ...config, similarity_metric: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none"
            >
              <option value="cosine">Cosine Distance (Standard)</option>
              <option value="dot">Dot Product (Normalized)</option>
              <option value="euclidean">Euclidean (L2)</option>
            </select>
          </div>

          {config.retrieval_mode === "hybrid" && (
            <div>
              <label className="block text-gray-700 font-medium mb-1">
                RRF Constant (k)
              </label>
              <input
                type="number"
                min={1}
                max={200}
                value={config.rrf_k}
                onChange={(e) => setConfig({ ...config, rrf_k: parseInt(e.target.value) || 60 })}
                className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono focus:border-amber-500 outline-none"
              />
              <span className="text-[11px] text-gray-500 mt-1 block">
                Standard: 60 (smooths rank variance)
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Save Action Bar */}
      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={loadData}
          className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 text-gray-600 hover:text-gray-900 border border-gray-200 text-xs font-medium transition cursor-pointer flex items-center gap-1.5 shadow-xs"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Reset Changes</span>
        </button>

        <button
          type="submit"
          disabled={saving}
          className="px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-medium text-xs shadow-xs transition cursor-pointer disabled:opacity-50 flex items-center gap-2"
        >
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          <span>{saving ? "Saving Configuration..." : "Save Retrieval Settings"}</span>
        </button>
      </div>
    </form>
  );
}
