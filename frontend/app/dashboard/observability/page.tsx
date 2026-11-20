"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  AssistantTraceItem,
  ObservabilityMetrics,
  ObservabilityPolicy,
} from "@/lib/api";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  BarChart2,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Clock,
  Compass,
  Database,
  DollarSign,
  Eye,
  EyeOff,
  Filter,
  HelpCircle,
  Layers,
  MessageSquare,
  RefreshCw,
  Search,
  Server,
  Settings,
  Shield,
  ShieldAlert,
  Trash2,
  TrendingDown,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";

export default function ObservabilityPage() {
  const [metrics, setMetrics] = useState<ObservabilityMetrics | null>(null);
  const [traces, setTraces] = useState<AssistantTraceItem[]>([]);
  const [policy, setPolicy] = useState<ObservabilityPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filters & Period
  const [period, setPeriod] = useState<string>("24h");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [trafficFilter, setTrafficFilter] = useState<string>("");
  const [providerFilter, setProviderFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Trace Drilldown Modal
  const [selectedTrace, setSelectedTrace] = useState<AssistantTraceItem | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "timeline" | "retrieval" | "preview" | "error">("overview");
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Policy Settings Modal
  const [showPolicyModal, setShowPolicyModal] = useState(false);
  const [savingPolicy, setSavingPolicy] = useState(false);
  const [purging, setPurging] = useState(false);
  const [editCaptureMode, setEditCaptureMode] = useState<"METADATA_ONLY" | "REDACTED_PREVIEW">("METADATA_ONLY");
  const [editMaxLength, setEditMaxLength] = useState<number>(250);
  const [editRetentionDays, setEditRetentionDays] = useState<number>(30);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, tList, pol] = await Promise.all([
        api.getObservabilityMetrics(period),
        api.listTraces({
          status: statusFilter || undefined,
          traffic_type: trafficFilter || undefined,
          provider: providerFilter || undefined,
          search: searchQuery || undefined,
          limit: 100,
        }),
        api.getObservabilityPolicy().catch(() => null),
      ]);
      setMetrics(m);
      setTraces(tList);
      if (pol) {
        setPolicy(pol);
        setEditCaptureMode(pol.capture_mode);
        setEditMaxLength(pol.max_preview_length);
        setEditRetentionDays(pol.retention_days);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load observability telemetry");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [period, statusFilter, trafficFilter, providerFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  const handleOpenTrace = async (traceId: string) => {
    setLoadingDetail(true);
    try {
      const detail = await api.getTraceDetail(traceId);
      setSelectedTrace(detail);
      setActiveTab(detail.error ? "error" : "overview");
    } catch (err: any) {
      setError(err.message || "Failed to fetch trace details");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleSavePolicy = async () => {
    setSavingPolicy(true);
    setError(null);
    try {
      const updated = await api.updateObservabilityPolicy({
        capture_mode: editCaptureMode,
        max_preview_length: editMaxLength,
        retention_days: editRetentionDays,
      });
      setPolicy(updated);
      setSuccessMsg("Observability capture policy updated successfully.");
      setShowPolicyModal(false);
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.message || "Failed to update observability policy");
    } finally {
      setSavingPolicy(false);
    }
  };

  const handlePurgeTraces = async () => {
    if (!confirm(`Are you sure you want to purge telemetry records older than ${editRetentionDays} days? This cannot be undone.`)) {
      return;
    }
    setPurging(true);
    setError(null);
    try {
      const res = await api.purgeExpiredTraces();
      setSuccessMsg(`Purged ${res.purged_count} expired traces successfully.`);
      loadData();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.message || "Failed to purge telemetry traces");
    } finally {
      setPurging(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-blue-600">
            <Activity className="w-4 h-4" />
            <span>AI Request Intelligence & Reliability</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 mt-1">
            System Observability & Tracing
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Durable request execution spans, latency profiles, retrieval diagnostics, token accounting, and cost estimation.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          {/* Period Selector */}
          <div className="flex items-center rounded-xl bg-gray-100 p-1 border border-gray-200 text-xs font-medium">
            {(["24h", "7d", "30d", "all"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 rounded-lg transition cursor-pointer ${
                  period === p
                    ? "bg-white text-gray-900 shadow-xs font-semibold"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {p === "24h" ? "24h" : p === "7d" ? "7d" : p === "30d" ? "30d" : "All"}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowPolicyModal(true)}
            className="px-3.5 py-2 rounded-xl bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer shadow-xs"
          >
            <Settings className="w-3.5 h-3.5 text-gray-500" />
            <span>Policy & Retention</span>
          </button>

          <button
            onClick={loadData}
            disabled={loading}
            className="px-3.5 py-2 rounded-xl bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-medium flex items-center gap-2 transition cursor-pointer shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-blue-600 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
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

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-600 hover:text-emerald-800 cursor-pointer">
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
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">PostgreSQL persisted</span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Error Rate</span>
            <p className={`text-2xl font-bold font-mono mt-1 ${metrics.error_rate > 0 ? "text-red-600" : "text-emerald-600"}`}>
              {(metrics.error_rate * 100).toFixed(1)}%
            </p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">
              {(metrics.by_status?.FAILED ?? 0) + (metrics.by_status?.CANCELLED ?? 0)} failed / cancelled
            </span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">p50 / p95 Latency</span>
            <p className="text-2xl font-bold text-blue-600 font-mono mt-1">
              {metrics.p50_latency_ms?.toFixed(0) || metrics.avg_latency_ms?.toFixed(0) || 0} <span className="text-xs font-normal text-gray-400">/</span> {metrics.p95_latency_ms?.toFixed(0) || 0} <span className="text-xs font-normal text-gray-400">ms</span>
            </p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">p99: {metrics.p99_latency_ms?.toFixed(0) || 0} ms</span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Avg TTFT</span>
            <p className="text-2xl font-bold text-emerald-600 font-mono mt-1">{metrics.avg_ttft_ms.toFixed(0)} ms</p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">Time to first token</span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Total Tokens</span>
            <p className="text-2xl font-bold text-sky-600 font-mono mt-1">{metrics.total_tokens.toLocaleString()}</p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">Prompt + Completion</span>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Estimated Cost</span>
            <p className="text-2xl font-bold text-emerald-700 font-mono mt-1">
              ${metrics.estimated_cost_usd != null ? metrics.estimated_cost_usd.toFixed(4) : "0.0000"}
            </p>
            <span className="text-[10px] text-gray-400 font-mono mt-1 block">Verified provider rates</span>
          </div>
        </div>
      )}

      {/* Traffic & Provider Activity Distribution */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-3">
            <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-blue-600" />
              <span>Channel Distribution</span>
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
                <span className="text-xs text-gray-400 py-1 font-mono">No provider activity recorded in this period.</span>
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
              {traces.length} recorded
            </span>
          </div>

          {/* Filters Bar */}
          <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
              <input
                type="text"
                placeholder="Search trace ID, assistant..."
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
              <option value="CANCELLED">CANCELLED</option>
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
              <option value="preview">Test Preview</option>
            </select>
          </form>
        </div>

        {traces.length === 0 ? (
          <div className="p-12 text-center text-xs text-gray-400 space-y-1">
            <p className="font-semibold text-gray-600">No request traces found</p>
            <p>Traces will appear here as AI assistant conversations and developer queries are executed.</p>
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
                  <th className="py-2.5 px-3">Duration</th>
                  <th className="py-2.5 px-3">TTFT</th>
                  <th className="py-2.5 px-3">Tokens</th>
                  <th className="py-2.5 px-3">Cost</th>
                  <th className="py-2.5 px-3">Citations</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 font-mono text-[11px]">
                {traces.map((t) => (
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
                            : t.status === "CANCELLED"
                            ? "bg-amber-50 border border-amber-200 text-amber-700"
                            : "bg-red-50 border border-red-200 text-red-700"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-gray-700">
                      {t.total_duration_ms != null ? `${t.total_duration_ms.toFixed(0)} ms` : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-emerald-600">
                      {t.ttft_ms != null ? `${t.ttft_ms.toFixed(0)} ms` : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500">
                      {t.total_tokens || "—"}
                    </td>
                    <td className="py-2.5 px-3 text-gray-700">
                      {t.estimated_cost_usd != null ? `$${t.estimated_cost_usd.toFixed(4)}` : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-gray-500">
                      {t.citation_count}
                    </td>
                    <td className="py-2.5 px-3 text-gray-400 font-sans text-[11px]">
                      {t.created_at ? new Date(t.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"}
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

      {/* Trace Detail Modal Inspector */}
      {selectedTrace && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white border border-gray-200 rounded-2xl max-w-4xl w-full p-6 space-y-4 shadow-2xl max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-gray-200 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase font-bold text-blue-600 tracking-wider">
                    Trace Inspector
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                      selectedTrace.status === "COMPLETED"
                        ? "bg-emerald-50 border border-emerald-200 text-emerald-700"
                        : selectedTrace.status === "CANCELLED"
                        ? "bg-amber-50 border border-amber-200 text-amber-700"
                        : "bg-red-50 border border-red-200 text-red-700"
                    }`}
                  >
                    {selectedTrace.status}
                  </span>
                </div>
                <h3 className="text-base font-bold text-gray-900 font-mono mt-0.5">
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

            {/* Inspector Navigation Tabs */}
            <div className="flex border-b border-gray-200 gap-1 text-xs font-medium">
              <button
                onClick={() => setActiveTab("overview")}
                className={`px-3 py-2 border-b-2 transition cursor-pointer ${
                  activeTab === "overview"
                    ? "border-blue-600 text-blue-600 font-semibold"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                Overview & Metrics
              </button>
              <button
                onClick={() => setActiveTab("timeline")}
                className={`px-3 py-2 border-b-2 transition cursor-pointer ${
                  activeTab === "timeline"
                    ? "border-blue-600 text-blue-600 font-semibold"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                Execution Spans ({selectedTrace.spans?.length || 0})
              </button>
              <button
                onClick={() => setActiveTab("retrieval")}
                className={`px-3 py-2 border-b-2 transition cursor-pointer ${
                  activeTab === "retrieval"
                    ? "border-blue-600 text-blue-600 font-semibold"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                RAG Retrieval
              </button>
              <button
                onClick={() => setActiveTab("preview")}
                className={`px-3 py-2 border-b-2 transition cursor-pointer ${
                  activeTab === "preview"
                    ? "border-blue-600 text-blue-600 font-semibold"
                    : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
              >
                Input / Output Preview
              </button>
              {selectedTrace.error && (
                <button
                  onClick={() => setActiveTab("error")}
                  className={`px-3 py-2 border-b-2 transition cursor-pointer text-red-600 ${
                    activeTab === "error"
                      ? "border-red-600 font-semibold"
                      : "border-transparent hover:text-red-700"
                  }`}
                >
                  Error Details
                </button>
              )}
            </div>

            {/* Tab Contents */}
            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {/* Tab 1: Overview */}
              {activeTab === "overview" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Assistant</span>
                      <span className="text-gray-900 font-sans font-semibold truncate block">
                        {selectedTrace.assistant_name}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Provider / Model</span>
                      <span className="text-purple-600 truncate block">
                        {selectedTrace.provider || "none"} / {selectedTrace.model || "auto"}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Traffic Channel</span>
                      <span className="text-blue-600 uppercase font-semibold">
                        {selectedTrace.traffic_type}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Estimated Cost</span>
                      <span className="text-emerald-700 font-bold block">
                        {selectedTrace.estimated_cost_usd != null
                          ? `$${selectedTrace.estimated_cost_usd.toFixed(6)}`
                          : selectedTrace.pricing_status === "zero_cost"
                          ? "$0.00 (Mock)"
                          : "Unknown"}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Total Duration</span>
                      <span className="text-gray-800 font-bold">
                        {selectedTrace.total_duration_ms != null ? `${selectedTrace.total_duration_ms.toFixed(1)} ms` : "—"}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Time To First Token</span>
                      <span className="text-emerald-600 font-bold">
                        {selectedTrace.ttft_ms != null ? `${selectedTrace.ttft_ms.toFixed(1)} ms` : "—"}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Tokens (In / Out)</span>
                      <span className="text-sky-600 font-bold">
                        {selectedTrace.input_tokens} / {selectedTrace.output_tokens}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Citations Emitted</span>
                      <span className="text-gray-800 font-bold">{selectedTrace.citation_count}</span>
                    </div>
                  </div>

                  {selectedTrace.conversation_id && (
                    <div className="p-3 rounded-xl bg-blue-50/60 border border-blue-200 text-xs text-blue-900 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-blue-600" />
                        <span>Associated Conversation: <strong className="font-mono">{selectedTrace.conversation_id}</strong></span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 2: Execution Spans Waterfall */}
              {activeTab === "timeline" && (
                <div className="space-y-2">
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
                                <span className="text-gray-800 truncate">
                                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                                </span>
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
                    <div className="p-8 text-center text-xs text-gray-400">
                      No execution spans recorded for this trace.
                    </div>
                  )}
                </div>
              )}

              {/* Tab 3: RAG Retrieval Intelligence */}
              {activeTab === "retrieval" && (
                <div className="space-y-4 text-xs font-mono">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Mode</span>
                      <span className="text-blue-600 font-bold uppercase">{selectedTrace.retrieval_mode || "none"}</span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Authorized Chunks</span>
                      <span className="text-emerald-600 font-bold">{selectedTrace.retrieved_chunk_count}</span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Vector Store</span>
                      <span className="text-gray-800">{selectedTrace.retrieval_metadata?.vector_store || "pgvector"}</span>
                    </div>
                    <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                      <span className="text-[10px] text-gray-400 uppercase block">Citations</span>
                      <span className="text-purple-600 font-bold">{selectedTrace.citation_count}</span>
                    </div>
                  </div>

                  {selectedTrace.retrieval_metadata?.timing_ms && (
                    <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-2">
                      <h5 className="font-bold text-gray-800 uppercase text-[10px] tracking-wider">
                        Retrieval Latency Breakdown
                      </h5>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                        {Object.entries(selectedTrace.retrieval_metadata.timing_ms).map(([stage, ms]) => (
                          <div key={stage} className="p-2 rounded-lg bg-white border border-gray-200">
                            <span className="text-gray-400 block text-[10px] truncate">{stage.replace("_ms", "")}</span>
                            <span className="text-gray-900 font-bold">{String(ms)} ms</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedTrace.retrieval_metadata?.fusion && Object.keys(selectedTrace.retrieval_metadata.fusion).length > 0 && (
                    <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-2">
                      <h5 className="font-bold text-gray-800 uppercase text-[10px] tracking-wider">
                        Hybrid Fusion (RRF) Metadata
                      </h5>
                      <pre className="text-[11px] p-2 bg-white rounded-lg border border-gray-200 overflow-x-auto text-gray-700">
                        {JSON.stringify(selectedTrace.retrieval_metadata.fusion, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4: Safe Input / Output Previews */}
              {activeTab === "preview" && (
                <div className="space-y-4">
                  {selectedTrace.has_preview ? (
                    <div className="space-y-4 text-xs">
                      <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-1.5">
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">
                          Sanitized Request Input Preview
                        </span>
                        <p className="text-gray-900 font-sans whitespace-pre-wrap leading-relaxed">
                          {selectedTrace.input_preview || "No input preview recorded."}
                        </p>
                      </div>

                      <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-1.5">
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">
                          Sanitized Generated Output Preview
                        </span>
                        <p className="text-gray-900 font-sans whitespace-pre-wrap leading-relaxed">
                          {selectedTrace.output_preview || "No output preview recorded."}
                        </p>
                      </div>

                      <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] flex items-center gap-2">
                        <Shield className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Previews are redacted for API keys, passwords, bearer tokens, and truncated according to workspace policy.</span>
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 text-center text-xs space-y-2 bg-gray-50 rounded-2xl border border-dashed border-gray-300">
                      <Shield className="w-8 h-8 text-gray-400 mx-auto" />
                      <p className="font-semibold text-gray-700">Input/Output previews are not available for this trace</p>
                      <p className="text-gray-500 max-w-md mx-auto">
                        Your workspace is operating in <strong>Metadata Only</strong> mode, or this trace was captured before previews were enabled. You can enable redacted previews in Policy & Retention settings.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 5: Error Details */}
              {activeTab === "error" && (
                <div className="space-y-4 text-xs font-mono">
                  <div className="p-4 rounded-xl bg-red-50 border border-red-200 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-200 text-red-900 uppercase">
                        {selectedTrace.error_category || "ERROR"}
                      </span>
                    </div>
                    <p className="text-red-900 font-bold text-sm">
                      {selectedTrace.error || "An unspecified error occurred."}
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-1.5 text-gray-700 font-sans">
                    <h5 className="font-bold text-gray-900 text-xs">Diagnostic Guidance</h5>
                    {selectedTrace.error_category === "QUOTA_EXCEEDED" && (
                      <p>The workspace exceeded its allocated token or request quota. Increase quota under Administration or wait for the quota window reset.</p>
                    )}
                    {selectedTrace.error_category === "AUTH_ERROR" && (
                      <p>The selected provider credentials were missing or rejected. Verify your BYOK API key under Providers & Keys.</p>
                    )}
                    {selectedTrace.error_category === "CANCELLED_STREAM" && (
                      <p>The client aborted or disconnected before the stream completed. This is normal when users close the browser or stop generation.</p>
                    )}
                    {selectedTrace.error_category === "RATE_LIMITED" && (
                      <p>The upstream provider returned HTTP 429. Consider using an alternate model or configuring OmniRoute fallback routing.</p>
                    )}
                    {!["QUOTA_EXCEEDED", "AUTH_ERROR", "CANCELLED_STREAM", "RATE_LIMITED"].includes(selectedTrace.error_category || "") && (
                      <p>Review the execution spans waterfall to identify which specific phase failed.</p>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end pt-2 border-t border-gray-200">
              <button
                onClick={() => setSelectedTrace(null)}
                className="px-4 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-800 text-xs font-medium cursor-pointer shadow-xs"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Policy & Retention Settings Modal */}
      {showPolicyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white border border-gray-200 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 pb-3">
              <div className="flex items-center gap-2">
                <Settings className="w-4 h-4 text-gray-600" />
                <h3 className="text-sm font-bold text-gray-900">Observability Policy & Retention</h3>
              </div>
              <button
                onClick={() => setShowPolicyModal(false)}
                className="p-1 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              {/* Capture Mode Toggle */}
              <div className="space-y-1.5">
                <label className="font-bold text-gray-900 block">Telemetry Capture Mode</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setEditCaptureMode("METADATA_ONLY")}
                    className={`p-3 rounded-xl border text-left cursor-pointer transition ${
                      editCaptureMode === "METADATA_ONLY"
                        ? "border-blue-600 bg-blue-50/50 text-blue-900"
                        : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    <span className="font-bold block flex items-center gap-1.5">
                      <EyeOff className="w-3.5 h-3.5" />
                      Metadata Only
                    </span>
                    <span className="text-[10px] text-gray-500 mt-0.5 block">
                      Recommended. Zero prompt or completion storage.
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setEditCaptureMode("REDACTED_PREVIEW")}
                    className={`p-3 rounded-xl border text-left cursor-pointer transition ${
                      editCaptureMode === "REDACTED_PREVIEW"
                        ? "border-blue-600 bg-blue-50/50 text-blue-900"
                        : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    <span className="font-bold block flex items-center gap-1.5">
                      <Eye className="w-3.5 h-3.5" />
                      Redacted Preview
                    </span>
                    <span className="text-[10px] text-gray-500 mt-0.5 block">
                      Stores short, scrubbed preview snippets for debugging.
                    </span>
                  </button>
                </div>
              </div>

              {/* Max Preview Length */}
              {editCaptureMode === "REDACTED_PREVIEW" && (
                <div className="space-y-1">
                  <label className="font-bold text-gray-900 block">Max Preview Snippet Length (characters)</label>
                  <input
                    type="number"
                    min={50}
                    max={500}
                    value={editMaxLength}
                    onChange={(e) => setEditMaxLength(parseInt(e.target.value) || 250)}
                    className="w-full px-3 py-1.5 rounded-xl border border-gray-300 text-gray-900 text-xs focus:border-blue-500 shadow-xs outline-none"
                  />
                  <span className="text-[10px] text-gray-400">Values between 50 and 500 characters. Default: 250.</span>
                </div>
              )}

              {/* Retention Days */}
              <div className="space-y-1">
                <label className="font-bold text-gray-900 block">Telemetry Retention Period</label>
                <select
                  value={editRetentionDays}
                  onChange={(e) => setEditRetentionDays(parseInt(e.target.value))}
                  className="w-full px-3 py-1.5 rounded-xl border border-gray-300 text-gray-900 text-xs focus:border-blue-500 shadow-xs outline-none"
                >
                  <option value={7}>7 Days</option>
                  <option value={14}>14 Days</option>
                  <option value={30}>30 Days (Recommended for Neon Free)</option>
                  <option value={60}>60 Days</option>
                  <option value={90}>90 Days</option>
                </select>
                <span className="text-[10px] text-gray-400">Older traces are eligible for manual or automated purge.</span>
              </div>

              {/* Purge Button */}
              <div className="pt-2 border-t border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-bold text-gray-900 block">Purge Expired Traces</span>
                    <span className="text-[10px] text-gray-400">Removes records older than {editRetentionDays} days.</span>
                  </div>
                  <button
                    type="button"
                    onClick={handlePurgeTraces}
                    disabled={purging}
                    className="px-3 py-1.5 rounded-xl bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-600" />
                    <span>{purging ? "Purging..." : "Purge Now"}</span>
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-gray-200">
              <button
                type="button"
                onClick={() => setShowPolicyModal(false)}
                className="px-4 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-800 text-xs font-medium cursor-pointer shadow-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSavePolicy}
                disabled={savingPolicy}
                className="px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium cursor-pointer shadow-xs"
              >
                {savingPolicy ? "Saving..." : "Save Policy"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
