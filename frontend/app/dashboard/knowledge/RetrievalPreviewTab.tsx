"use client";

import React, { useState } from "react";
import { api, SearchResponse } from "@/lib/api";
import {
  Search,
  Loader2,
  FileText,
  Clock,
  Layers,
  Sparkles,
  BookOpen,
  AlertCircle,
  Copy,
} from "lucide-react";

interface RetrievalPreviewTabProps {
  kbId: string;
  kbName: string;
}

export default function RetrievalPreviewTab({
  kbId,
  kbName,
}: RetrievalPreviewTabProps) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"hybrid" | "semantic" | "lexical">("hybrid");
  const [topK, setTopK] = useState(6);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedChunkId, setCopiedChunkId] = useState<string | null>(null);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.previewKnowledge({
        query: query.trim(),
        knowledge_base_ids: [kbId],
        retrieval_mode: mode,
        top_k: topK,
      });
      setResults(res);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Search query execution failed.");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedChunkId(id);
    setTimeout(() => setCopiedChunkId(null), 1800);
  };

  return (
    <div className="space-y-6 max-w-5xl animate-fadeIn">
      {/* Search Bar & Parameter Controls */}
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl space-y-4">
        <form onSubmit={handleSearch} className="space-y-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-3.5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Ask a question or enter keywords to retrieve relevant passages from '${kbName}'...`}
              className="w-full pl-10 pr-24 py-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 text-xs placeholder:text-slate-500 focus:border-amber-500 outline-none shadow-inner"
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="absolute right-2 top-2 px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs transition cursor-pointer disabled:opacity-40 flex items-center gap-1.5"
            >
              {loading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5" />
              )}
              <span>{loading ? "Searching..." : "Retrieve"}</span>
            </button>
          </div>

          {/* Quick Filter Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs pt-1">
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400 font-medium">Retrieval Mode:</span>
              <div className="inline-flex rounded-lg bg-slate-950 p-0.5 border border-slate-800 text-[11px]">
                <button
                  type="button"
                  onClick={() => setMode("hybrid")}
                  className={`px-2.5 py-1 rounded-md transition cursor-pointer font-medium ${
                    mode === "hybrid"
                      ? "bg-amber-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Hybrid (RRF)
                </button>
                <button
                  type="button"
                  onClick={() => setMode("semantic")}
                  className={`px-2.5 py-1 rounded-md transition cursor-pointer font-medium ${
                    mode === "semantic"
                      ? "bg-amber-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Semantic
                </button>
                <button
                  type="button"
                  onClick={() => setMode("lexical")}
                  className={`px-2.5 py-1 rounded-md transition cursor-pointer font-medium ${
                    mode === "lexical"
                      ? "bg-amber-600 text-white shadow-sm"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Lexical (FTS)
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400 font-medium">Top Candidates:</span>
              <select
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value) || 6)}
                className="px-2 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 text-xs outline-none"
              >
                <option value={4}>4 Chunks</option>
                <option value={6}>6 Chunks</option>
                <option value={8}>8 Chunks</option>
                <option value={12}>12 Chunks</option>
              </select>
            </div>
          </div>
        </form>
      </div>

      {/* Error Message */}
      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-800 text-red-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Diagnostic & Telemetry Header */}
      {results && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-1 text-xs">
          <div className="flex items-center gap-2 text-slate-400">
            <span className="font-semibold text-white">
              {results.returned_candidates} candidates
            </span>
            <span>&bull;</span>
            <span className="capitalize font-mono text-[11px] text-amber-400">
              {results.retrieval_mode} Mode
            </span>
            <span>&bull;</span>
            <span className="font-mono text-[11px] text-slate-400">
              Store: {results.vector_store}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-slate-500 font-mono text-[11px]">
            <Clock className="w-3.5 h-3.5" />
            <span>{results.took_ms.toFixed(1)} ms</span>
          </div>
        </div>
      )}

      {/* Results List */}
      {results && results.candidates.length > 0 ? (
        <div className="space-y-3">
          {results.candidates.map((cand, idx) => (
            <div
              key={cand.chunk_id || idx}
              className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl hover:border-slate-700 transition space-y-3 group"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-lg bg-amber-500/10 text-amber-400 font-bold text-xs flex items-center justify-center font-mono">
                    #{idx + 1}
                  </span>
                  <span className="font-medium text-white text-xs flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-amber-400" />
                    <span>{cand.document_name || "Document Passage"}</span>
                  </span>
                  {cand.heading_path && (
                    <span className="px-2 py-0.5 rounded-md bg-slate-950 border border-slate-800 text-[10px] text-slate-400 font-medium truncate max-w-xs">
                      {cand.heading_path}
                    </span>
                  )}
                  {cand.page_number && (
                    <span className="px-1.5 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] text-slate-500 font-mono">
                      p. {cand.page_number}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {cand.fused_rank && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-950/80 text-amber-400 border border-amber-800/80">
                      Fused #{cand.fused_rank}
                    </span>
                  )}
                  {cand.semantic_rank && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-950/80 text-blue-400 border border-blue-800/80">
                      Sem #{cand.semantic_rank}
                    </span>
                  )}
                  {cand.lexical_rank && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/80">
                      Lex #{cand.lexical_rank}
                    </span>
                  )}
                  <span className="text-[11px] font-mono text-slate-400 font-semibold">
                    Score: {cand.score.toFixed(4)}
                  </span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(cand.content, cand.chunk_id)}
                    className="p-1 rounded text-slate-500 hover:text-slate-300 transition cursor-pointer"
                    title="Copy passage"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Passage Content */}
              <p className="text-xs text-slate-200 font-mono whitespace-pre-wrap leading-relaxed bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80">
                {cand.content}
              </p>

              {copiedChunkId === cand.chunk_id && (
                <div className="text-[10px] text-emerald-400 font-mono text-right">
                  Copied passage to clipboard!
                </div>
              )}
            </div>
          ))}

          {/* Formatted Citations Section */}
          {results.citations && results.citations.length > 0 && (
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800/80 space-y-3 mt-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                <BookOpen className="w-4 h-4 text-amber-400" />
                <span>Source Provenance & Structured Citations</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                {results.citations.map((cite) => (
                  <div
                    key={cite.citation_id}
                    className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 space-y-1 font-mono"
                  >
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="font-bold text-amber-400 truncate max-w-[200px]">
                        {cite.document_name}
                      </span>
                      <span className="text-slate-500 text-[10px]">
                        {cite.page_number ? `Page ${cite.page_number}` : "Chunk"}
                      </span>
                    </div>
                    <p className="text-slate-400 line-clamp-2 text-[10px]">
                      &ldquo;{cite.source_snippet}&rdquo;
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : results ? (
        <div className="p-16 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/30">
          <Layers className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-200">No matching chunks retrieved</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            Try adjusting your search terms, switching to another retrieval mode, or verify that your documents have been indexed.
          </p>
        </div>
      ) : (
        /* Empty State */
        <div className="p-16 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/30">
          <Sparkles className="w-10 h-10 text-amber-500/50 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-200">
            Interactive Retrieval Sandbox
          </h3>
          <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto leading-relaxed">
            Test semantic, lexical, or hybrid RRF retrieval in real time. Inspect ranked chunk candidates, similarity scores, and citation provenance before deploying to assistants.
          </p>
        </div>
      )}
    </div>
  );
}
