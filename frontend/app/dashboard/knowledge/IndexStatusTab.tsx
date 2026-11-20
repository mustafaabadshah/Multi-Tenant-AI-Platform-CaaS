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
      <div className="p-16 text-center text-xs text-gray-500 flex items-center justify-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
        <span>Loading index telemetry & statistics...</span>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="p-8 text-center text-xs text-red-600">
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
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-600" />
          <span>{reindexMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {/* Metric 1: Vector Health */}
        <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-1">
          <div className="flex items-center justify-between text-gray-500 text-xs">
            <span className="font-medium">Vector Store</span>
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                status.vector_store_healthy
                  ? "bg-emerald-500 shadow-xs shadow-emerald-500/50"
                  : "bg-red-500"
              }`}
            />
          </div>
          <div className="text-base font-bold text-gray-900 uppercase tracking-tight font-mono">
            {status.vector_store}
          </div>
          <span className="text-[11px] text-gray-500 block">
            {status.vector_store_healthy ? "Online & Healthy" : "Connection Issue"}
          </span>
        </div>

        {/* Metric 2: Active Version */}
        <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-1">
          <span className="text-gray-500 text-xs font-medium block">Embedding Version</span>
          <div className="text-base font-bold text-amber-600 font-mono">
            v{status.active_embedding_version}
          </div>
          <span className="text-[11px] text-gray-500 block">Active Vector Space</span>
        </div>

        {/* Metric 3: Total Chunks */}
        <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-1">
          <span className="text-gray-500 text-xs font-medium block">Total Chunks</span>
          <div className="text-base font-bold text-gray-900 font-mono">
            {status.total_chunks}
          </div>
          <span className="text-[11px] text-gray-500 block">
            Across {status.total_documents} documents
          </span>
        </div>

        {/* Metric 4: Indexed Vectors */}
        <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-1">
          <span className="text-gray-500 text-xs font-medium block">
            {isFts ? "FTS Indexing" : "Indexed Vectors"}
          </span>
          <div className="text-base font-bold text-emerald-600 font-mono">
            {isFts ? "Complete (FTS)" : `${status.indexed_embeddings} / ${status.total_chunks}`}
          </div>
          <span className="text-[11px] text-gray-500 block">
            {isFts ? "Zero embedding cost" : `${pctIndexed}% synchronized`}
          </span>
        </div>
      </div>

      {/* Progress & Reindex Card */}
      <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-600" />
              <span>Index Synchronization & Maintenance</span>
            </h3>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Ensure all document chunks are hash-verified and synchronized with the vector engine.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadData}
              className="p-2 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-600 hover:text-gray-900 transition cursor-pointer"
              title="Refresh status"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={handleReindex}
              disabled={reindexing}
              className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs transition cursor-pointer disabled:opacity-50 flex items-center gap-2 shadow-xs"
            >
              {reindexing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{reindexing ? "Reindexing Chunks..." : "Reindex Knowledge Base"}</span>
            </button>
          </div>
        </div>

        {/* Progress Bar (for vector mode) */}
        {!isFts && status.total_chunks > 0 && (
          <div className="space-y-1.5 pt-2">
            <div className="flex justify-between text-[11px] font-mono text-gray-500">
              <span>Embedding Coverage</span>
              <span>{pctIndexed}%</span>
            </div>
            <div className="w-full h-2 rounded-full bg-gray-100 overflow-hidden border border-gray-200">
              <div
                className="h-full bg-amber-500 rounded-full transition-all duration-500"
                style={{ width: `${pctIndexed}%` }}
              />
            </div>
          </div>
        )}

        <div className="pt-2 border-t border-gray-100 flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono text-gray-500">
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
        <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2">
          <Clock className="w-4 h-4 text-amber-600" />
          <span>Embedding & Indexing Jobs ({jobs.length})</span>
        </h3>

        {jobs.length === 0 ? (
          <div className="p-8 text-center border border-gray-200 rounded-2xl bg-white shadow-xs text-xs text-gray-500">
            No indexing jobs recorded yet. Ingest documents or trigger reindex above.
          </div>
        ) : (
          <div className="rounded-2xl border border-gray-200 bg-white shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold uppercase tracking-wider text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Provider / Model</th>
                    <th className="py-3 px-4 text-center">Version</th>
                    <th className="py-3 px-4 text-center">Chunks</th>
                    <th className="py-3 px-4">Started</th>
                    <th className="py-3 px-4">Completed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 text-gray-700">
                  {jobs.map((job) => (
                    <tr key={job.id} className="hover:bg-gray-50/60 transition">
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold font-mono ${
                            job.status === "COMPLETED"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : job.status === "FAILED"
                              ? "bg-red-50 text-red-700 border border-red-200"
                              : "bg-blue-50 text-blue-700 border border-blue-200"
                          }`}
                        >
                          {job.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-gray-800">
                        <span className="font-bold text-amber-700">{job.provider}</span>
                        <span className="text-gray-400 mx-1.5">&bull;</span>
                        <span className="text-gray-600">{job.model}</span>
                      </td>
                      <td className="py-3 px-4 text-center font-mono text-gray-500">
                        v{job.version}
                      </td>
                      <td className="py-3 px-4 text-center font-mono font-semibold text-gray-900">
                        {job.processed_chunks} / {job.total_chunks}
                      </td>
                      <td className="py-3 px-4 text-gray-500 text-[11px] font-mono">
                        {new Date(job.created_at).toLocaleTimeString()}
                      </td>
                      <td className="py-3 px-4 text-gray-500 text-[11px] font-mono">
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
