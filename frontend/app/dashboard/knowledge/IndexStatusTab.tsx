"use client";

import React, { useEffect, useState, useCallback } from "react";
import { api, IndexStatusItem, EmbeddingJobItem } from "@/lib/api";
import {
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  Clock,
  Activity,
} from "lucide-react";

interface IndexStatusTabProps {
  kbId: string;
  kbName: string;
}

export default function IndexStatusTab({ kbId, kbName }: IndexStatusTabProps) {
  const [status, setStatus] = useState<IndexStatusItem | null>(null);
  const [jobs, setJobs] = useState<EmbeddingJobItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMsg, setReindexMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [st, jbs] = await Promise.all([
        api.getKBIndexStatus(kbId),
        api.listKBEmbeddingJobs(kbId).catch(() => []),
      ]);
      setStatus(st);
      setJobs(jbs);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load index status.");
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleReindex = async () => {
    if (
      !confirm(
        `Trigger full reindexing for '${kbName}'? This will recalculate embeddings and update vector store records.`
      )
    ) {
      return;
    }

    setReindexing(true);
    setReindexMsg(null);
    setErrorMsg(null);
    try {
      const res = await api.reindexKB(kbId);
      setReindexMsg(res.message || "Reindexing completed successfully.");
      await loadData();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Reindexing failed.");
    } finally {
      setReindexing(false);
    }
  };

  if (loading) {
    return (
      <div className="p-16 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
        <span>Loading index telemetry & statistics...</span>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="p-8 text-center text-xs text-red-400">
        Failed to load index status metrics.
      </div>
    );
  }

  const isFts = status.vector_store === "fts" || status.retrieval_mode === "lexical";
  const pctIndexed =
    status.total_chunks > 0
      ? Math.min(100, Math.round((status.indexed_embeddings / status.total_chunks) * 100))
      : 0;

  return (
    <div className="space-y-6 max-w-5xl animate-fadeIn">
      {/* Notifications */}
      {reindexMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{reindexMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-800 text-red-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {/* Metric 1: Vector Health */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="font-medium">Vector Store</span>
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                status.vector_store_healthy
                  ? "bg-emerald-400 shadow-sm shadow-emerald-400/50"
                  : "bg-red-400"
              }`}
            />
          </div>
          <div className="text-base font-bold text-white uppercase tracking-tight font-mono">
            {status.vector_store}
          </div>
          <span className="text-[11px] text-slate-400 block">
            {status.vector_store_healthy ? "Online & Healthy" : "Connection Issue"}
          </span>
        </div>

        {/* Metric 2: Active Version */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl space-y-1">
          <span className="text-slate-400 text-xs font-medium block">Embedding Version</span>
          <div className="text-base font-bold text-amber-400 font-mono">
            v{status.active_embedding_version}
          </div>
          <span className="text-[11px] text-slate-400 block">Active Vector Space</span>
        </div>

        {/* Metric 3: Total Chunks */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl space-y-1">
          <span className="text-slate-400 text-xs font-medium block">Total Chunks</span>
          <div className="text-base font-bold text-white font-mono">
            {status.total_chunks}
          </div>
          <span className="text-[11px] text-slate-400 block">
            Across {status.total_documents} documents
          </span>
        </div>

        {/* Metric 4: Indexed Vectors */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl space-y-1">
          <span className="text-slate-400 text-xs font-medium block">
            {isFts ? "FTS Indexing" : "Indexed Vectors"}
          </span>
          <div className="text-base font-bold text-emerald-400 font-mono">
            {isFts ? "Complete (FTS)" : `${status.indexed_embeddings} / ${status.total_chunks}`}
          </div>
          <span className="text-[11px] text-slate-400 block">
            {isFts ? "Zero embedding cost" : `${pctIndexed}% synchronized`}
          </span>
        </div>
      </div>

      {/* Progress & Reindex Card */}
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-400" />
              <span>Index Synchronization & Maintenance</span>
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Ensure all document chunks are hash-verified and synchronized with the vector engine.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadData}
              className="p-2 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-white transition cursor-pointer"
              title="Refresh status"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleReindex}
              disabled={reindexing}
              className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs transition cursor-pointer disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-amber-600/20"
            >
              {reindexing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{reindexing ? "Reindexing Chunks..." : "Reindex Knowledge Base"}</span>
            </button>
          </div>
        </div>

        {/* Progress Bar (for vector mode) */}
        {!isFts && status.total_chunks > 0 && (
          <div className="space-y-1.5 pt-2">
            <div className="flex justify-between text-[11px] font-mono text-slate-400">
              <span>Embedding Coverage</span>
              <span>{pctIndexed}%</span>
            </div>
            <div className="w-full h-2 rounded-full bg-slate-950 overflow-hidden border border-slate-800">
              <div
                className="h-full bg-amber-500 rounded-full transition-all duration-500"
                style={{ width: `${pctIndexed}%` }}
              />
            </div>
          </div>
        )}

        <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono text-slate-500">
          <span>Active Mode: {status.retrieval_mode.toUpperCase()}</span>
          <span>
            Last Activity:{" "}
            {status.last_indexed_at
              ? new Date(status.last_indexed_at).toLocaleString()
              : "Never"}
          </span>
        </div>
      </div>

      {/* Embedding Jobs History */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <Clock className="w-4 h-4 text-amber-400" />
          <span>Embedding & Indexing Jobs ({jobs.length})</span>
        </h3>

        {jobs.length === 0 ? (
          <div className="p-8 text-center border border-slate-800 rounded-2xl bg-slate-900/30 text-xs text-slate-400">
            No indexing jobs recorded yet. Ingest documents or trigger reindex above.
          </div>
        ) : (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden backdrop-blur-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Provider / Model</th>
                    <th className="py-3 px-4 text-center">Version</th>
                    <th className="py-3 px-4 text-center">Chunks</th>
                    <th className="py-3 px-4">Started</th>
                    <th className="py-3 px-4">Completed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono ${
                            job.status === "COMPLETED"
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : job.status === "FAILED"
                              ? "bg-red-950 text-red-400 border border-red-800"
                              : "bg-blue-950 text-blue-400 border border-blue-800"
                          }`}
                        >
                          {job.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-200">
                        <span className="font-bold text-amber-400">{job.provider}</span>
                        <span className="text-slate-500 mx-1.5">&bull;</span>
                        <span className="text-slate-300">{job.model}</span>
                      </td>
                      <td className="py-3 px-4 text-center font-mono text-slate-400">
                        v{job.version}
                      </td>
                      <td className="py-3 px-4 text-center font-mono font-semibold text-white">
                        {job.processed_chunks} / {job.total_chunks}
                      </td>
                      <td className="py-3 px-4 text-slate-400 text-[11px] font-mono">
                        {new Date(job.created_at).toLocaleTimeString()}
                      </td>
                      <td className="py-3 px-4 text-slate-400 text-[11px] font-mono">
                        {job.completed_at
                          ? new Date(job.completed_at).toLocaleTimeString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
