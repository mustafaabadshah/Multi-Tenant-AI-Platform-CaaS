"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  AssistantTraceItem,
  ObservabilityMetrics,
} from "@/lib/api";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart2,
  CheckCircle2,
  ChevronRight,
  Clock,
  Compass,
  Database,
  Filter,
  Layers,
  MessageSquare,
  RefreshCw,
  Search,
  Server,
  Shield,
  TrendingDown,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";

export default function ObservabilityPage() {
  const [metrics, setMetrics] = useState<ObservabilityMetrics | null>(null);
  const [traces, setTraces] = useState<AssistantTraceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [trafficFilter, setTrafficFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Trace Drilldown Modal
  const [selectedTrace, setSelectedTrace] = useState<AssistantTraceItem | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, tList] = await Promise.all([
        api.getObservabilityMetrics(),
        api.listTraces({
          status: statusFilter || undefined,
          traffic_type: trafficFilter || undefined,
          limit: 100,
        }),
      ]);
      setMetrics(m);
      setTraces(tList);
    } catch (err: any) {
      setError(err.message || "Failed to load observability telemetry");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter, trafficFilter]);

  const handleOpenTrace = async (traceId: string) => {
    setLoadingDetail(true);
    try {
      const detail = await api.getTraceDetail(traceId);
      setSelectedTrace(detail);
    } catch (err: any) {
      setError(err.message || "Failed to fetch trace details");
    } finally {
      setLoadingDetail(false);
    }
  };

  const filteredTraces = traces.filter((t) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      t.trace_id.toLowerCase().includes(q) ||
      t.assistant_name.toLowerCase().includes(q) ||
      (t.provider && t.provider.toLowerCase().includes(q)) ||
      (t.model && t.model.toLowerCase().includes(q))
    );
  });

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-blue-600">
            <Activity className="w-4 h-4" />
            <span>Platform Telemetry & Tracing</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 mt-1">
            System Observability & Request Tracing
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Real-time execution spans, latency profiles, time-to-first-token, and attribution across all assistant channels.
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="px-3.5 py-2 rounded-xl bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-medium flex items-center gap-2 transition cursor-pointer self-start sm:self-auto shadow-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-blue-600 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Traces</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800 cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Primary Telemetry Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Total Requests</span>
            <p className="text-2xl font-bold text-gray-900 font-mono mt-1">{metrics.total_requests}</p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">In-memory buffer</span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Error Rate</span>
            <p className={`text-2xl font-bold font-mono mt-1 ${metrics.error_rate > 0 ? "text-red-600" : "text-emerald-600"}`}>
              {(metrics.error_rate * 100).toFixed(1)}%
            </p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">
              {metrics.by_status?.FAILED ?? 0} failures
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Avg Latency</span>
            <p className="text-2xl font-bold text-blue-600 font-mono mt-1">{metrics.avg_latency_ms.toFixed(0)} ms</p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">End-to-end</span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">p95 Latency</span>
            <p className="text-2xl font-bold text-purple-600 font-mono mt-1">{metrics.p95_latency_ms.toFixed(0)} ms</p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">95th percentile</span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Avg TTFT</span>
            <p className="text-2xl font-bold text-emerald-600 font-mono mt-1">{metrics.avg_ttft_ms.toFixed(0)} ms</p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">First streaming token</span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Total Tokens</span>
            <p className="text-2xl font-bold text-sky-600 font-mono mt-1">{metrics.total_tokens.toLocaleString()}</p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">Prompt + Completion</span>
          </div>
        </div>
      )}

      {/* Traffic & Provider Breakdown Bars */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-3">
            <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-blue-600" />
              <span>Traffic Distribution by Channel</span>
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              {["internal", "developer", "public", "embed"].map((ch) => (
                <div key={ch} className="p-2.5 rounded-xl bg-gray-50 border border-gray-200">
                  <span className="text-[10px] uppercase text-gray-400 block">{ch}</span>
                  <span className="text-base font-bold text-gray-900">
                    {metrics.by_traffic_type?.[ch] ?? 0}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-3">
            <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-2">
              <Server className="w-3.5 h-3.5 text-purple-600" />
              <span>Activity by Provider</span>
            </h4>
            <div className="flex flex-wrap gap-2 text-xs font-mono">
              {Object.entries(metrics.by_provider || {}).map(([prov, count]) => (
                <div key={prov} className="px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 flex items-center gap-2">
                  <span className="text-gray-600">{prov}:</span>
                  <span className="text-purple-600 font-bold">{count}</span>
                </div>
              ))}
              {Object.keys(metrics.by_provider || {}).length === 0 && (
                <span className="text-xs text-gray-400 py-1 font-mono">No provider calls recorded yet.</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Trace Explorer Table */}
      <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-gray-900">Recent Request Traces</h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-gray-100 text-gray-600 border border-gray-200">
              {filteredTraces.length} recorded
            </span>
          </div>

          {/* Filters Bar */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
              <input
                type="text"
                placeholder="Search trace or assistant..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-xl bg-white border border-gray-300 text-gray-900 placeholder:text-gray-400 text-xs focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 w-48 sm:w-56 shadow-xs"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1.5 rounded-xl bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-500 shadow-xs outline-none"
            >
              <option value="">All Statuses</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="RUNNING">RUNNING</option>
              <option value="FAILED">FAILED</option>
            </select>

            <select
              value={trafficFilter}
              onChange={(e) => setTrafficFilter(e.target.value)}
              className="px-2.5 py-1.5 rounded-xl bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-500 shadow-xs outline-none"
            >
              <option value="">All Channels</option>
              <option value="internal">Internal Workspace</option>
              <option value="developer">Developer API</option>
              <option value="public">Public Standalone</option>
              <option value="embed">Embed Widget</option>
            </select>
          </div>
        </div>

        {filteredTraces.length === 0 ? (
          <div className="p-12 text-center text-xs text-gray-400">
            No request traces match the selected filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[10px] uppercase font-bold text-gray-500 border-b border-gray-200 bg-gray-50/50">
                <tr>
                  <th className="py-2.5 px-3">Trace ID</th>
                  <th className="py-2.5 px-3">Assistant</th>
                  <th className="py-2.5 px-3">Channel</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Latency</th>
                  <th className="py-2.5 px-3">TTFT</th>
                  <th className="py-2.5 px-3">Tokens</th>
                  <th className="py-2.5 px-3">Citations</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 font-mono text-[11px]">
                {filteredTraces.map((t) => (
                  <tr
                    key={t.trace_id}
                    onClick={() => handleOpenTrace(t.trace_id)}
                    className="hover:bg-gray-50/80 transition cursor-pointer"
                  >
                    <td className="py-2.5 px-3 font-semibold text-blue-600">
                      {t.trace_id.slice(0, 11)}...
                    </td>
                    <td className="py-2.5 px-3 text-gray-900 font-sans font-medium">
                      {t.assistant_name}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-gray-100 text-gray-700 border border-gray-200">
                        {t.traffic_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          t.status === "COMPLETED"
                            ? "bg-emerald-50 border border-emerald-200 text-emerald-700"
                            : t.status === "RUNNING"
                            ? "bg-blue-50 border border-blue-200 text-blue-700 animate-pulse"
                            : "bg-red-50 border border-red-200 text-red-700"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-gray-700">
                      {t.total_duration_ms != null ? `${t.total_duration_ms} ms` : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-emerald-600">
                      {t.ttft_ms != null ? `${t.ttft_ms} ms` : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500">
                      {t.total_tokens || "—"}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500">
                      {t.citation_count}
                    </td>
                    <td className="py-2.5 px-3 text-gray-400 font-sans text-[11px]">
                      {new Date(t.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <ChevronRight className="w-4 h-4 text-gray-400 inline-block" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Trace Detail Modal */}
      {selectedTrace && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white border border-gray-200 rounded-2xl max-w-3xl w-full p-6 space-y-4 shadow-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-gray-200 pb-3">
              <div>
                <span className="text-[10px] uppercase font-bold text-blue-600 tracking-wider">
                  Request Trace Spans
                </span>
                <h3 className="text-sm font-bold text-gray-900 font-mono mt-0.5">
                  {selectedTrace.trace_id}
                </h3>
              </div>
              <button
                onClick={() => setSelectedTrace(null)}
                className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Overview Attributes */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div className="p-2.5 rounded-xl bg-gray-50 border border-gray-200">
                <span className="text-[10px] text-gray-400 uppercase block">Assistant</span>
                <span className="text-gray-900 font-sans font-semibold">{selectedTrace.assistant_name}</span>
              </div>
              <div className="p-2.5 rounded-xl bg-gray-50 border border-gray-200">
                <span className="text-[10px] text-gray-400 uppercase block">Channel</span>
                <span className="text-blue-600 uppercase">{selectedTrace.traffic_type}</span>
              </div>
              <div className="p-2.5 rounded-xl bg-gray-50 border border-gray-200">
                <span className="text-[10px] text-gray-400 uppercase block">Provider / Model</span>
                <span className="text-purple-600 truncate block">
                  {selectedTrace.provider || "none"} / {selectedTrace.model || "none"}
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-gray-50 border border-gray-200">
                <span className="text-[10px] text-gray-400 uppercase block">Tokens</span>
                <span className="text-emerald-600 font-bold">{selectedTrace.total_tokens}</span>
              </div>
            </div>

            {selectedTrace.error && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
                <span className="font-bold">Error:</span> {selectedTrace.error}
              </div>
            )}

            {/* Spans Waterfall */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              <h4 className="text-xs font-bold uppercase tracking-wider text-gray-600">
                Lifecycle Execution Spans ({selectedTrace.spans?.length || 0})
              </h4>

              {selectedTrace.spans && selectedTrace.spans.length > 0 ? (
                selectedTrace.spans.map((sp, idx) => (
                  <div
                    key={sp.span_id || idx}
                    className="p-3 rounded-xl bg-gray-50 border border-gray-200 space-y-1.5 text-xs font-mono"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-md bg-white border border-gray-200 flex items-center justify-center text-[10px] font-bold text-gray-600 shadow-2xs">
                          {idx + 1}
                        </span>
                        <span className="font-bold text-gray-900">{sp.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-emerald-600 font-bold">
                          {sp.duration_ms != null ? `${sp.duration_ms} ms` : "in progress"}
                        </span>
                        <span className="px-1.5 py-0.5 rounded text-[9px] bg-white border border-gray-200 text-gray-700 uppercase shadow-2xs">
                          {sp.status}
                        </span>
                      </div>
                    </div>

                    {sp.attributes && Object.keys(sp.attributes).length > 0 && (
                      <div className="pl-7 text-[11px] text-gray-600 space-y-0.5">
                        {Object.entries(sp.attributes).map(([k, v]) => (
                          <div key={k} className="flex gap-2">
                            <span className="text-gray-400">{k}:</span>
                            <span className="text-gray-800 truncate">{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {sp.error && (
                      <div className="pl-7 text-[11px] text-red-600">
                        Error: {sp.error}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-xs text-gray-400">
                  No child spans recorded for this trace.
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-gray-200">
              <button
                onClick={() => setSelectedTrace(null)}
                className="px-4 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-800 text-xs font-medium cursor-pointer shadow-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
