"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  EvalDataset,
  EvalRun,
  EvalRunComparison,
  EvalRunResult,
} from "@/lib/api";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Compass,
  FileCheck,
  FileText,
  HelpCircle,
  Layers,
  Play,
  Plus,
  RefreshCw,
  Scale,
  Shield,
  Sparkles,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";

interface EvaluationTabProps {
  assistantId: string;
  assistantName: string;
}

export default function EvaluationTab({
  assistantId,
  assistantName,
}: EvaluationTabProps) {
  const [datasets, setDatasets] = useState<EvalDataset[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [evalType, setEvalType] = useState<"deterministic" | "llm_judge">("deterministic");

  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selected run for detail drilldown
  const [selectedRun, setSelectedRun] = useState<EvalRun | null>(null);
  const [loadingRunDetail, setLoadingRunDetail] = useState(false);

  // Comparison State
  const [comparingWithRunId, setComparingWithRunId] = useState<string>("");
  const [comparison, setComparison] = useState<EvalRunComparison | null>(null);

  // Load datasets and existing runs
  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dsList, runList] = await Promise.all([
        api.listEvalDatasets(),
        api.listEvalRuns(assistantId),
      ]);
      setDatasets(dsList);
      setRuns(runList);
      if (dsList.length > 0 && !selectedDatasetId) {
        setSelectedDatasetId(dsList[0].id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load evaluation data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [assistantId]);

  // Seed default benchmarks
  const handleSeedStarter = async () => {
    setSeeding(true);
    setError(null);
    try {
      await api.seedStarterBenchmarks();
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to seed starter benchmarks");
    } finally {
      setSeeding(false);
    }
  };

  // Trigger evaluation
  const handleRunEvaluation = async () => {
    if (!selectedDatasetId) {
      setError("Please select a benchmark dataset to evaluate.");
      return;
    }
    setEvaluating(true);
    setError(null);
    try {
      const run = await api.triggerEvalRun({
        assistant_id: assistantId,
        dataset_id: selectedDatasetId,
        eval_type: evalType,
      });
      await loadData();
      // Automatically load the completed run details
      await handleSelectRun(run.id);
    } catch (err: any) {
      setError(err.message || "Evaluation failed to execute");
    } finally {
      setEvaluating(false);
    }
  };

  // Fetch run details
  const handleSelectRun = async (runId: string) => {
    setLoadingRunDetail(true);
    try {
      const detail = await api.getEvalRun(runId);
      setSelectedRun(detail);
      setComparison(null);
      setComparingWithRunId("");
    } catch (err: any) {
      setError(err.message || "Failed to fetch run details");
    } finally {
      setLoadingRunDetail(false);
    }
  };

  // Compare runs
  const handleCompare = async (targetRunId: string) => {
    if (!selectedRun || !targetRunId) return;
    try {
      const comp = await api.compareEvalRuns(selectedRun.id, targetRunId);
      setComparison(comp);
      setComparingWithRunId(targetRunId);
    } catch (err: any) {
      setError(err.message || "Failed to compare evaluation runs");
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-white border border-gray-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-blue-600">
            <Scale className="w-4 h-4" />
            <span>AI Quality & Retrieval Evaluation</span>
          </div>
          <h3 className="text-base font-semibold text-gray-900 mt-1">
            Deterministic Benchmarks & Quality Assessment
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Measure Recall@5, Mean Reciprocal Rank (MRR), Groundedness, and Citation Provenance against curated ground-truth datasets.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {datasets.length === 0 && (
            <button
              onClick={handleSeedStarter}
              disabled={seeding}
              className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer shadow-xs disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>{seeding ? "Seeding..." : "Seed Starter Benchmarks"}</span>
            </button>
          )}

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-xl bg-white hover:bg-gray-50 border border-gray-200 text-gray-500 hover:text-gray-900 transition cursor-pointer shadow-xs"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Benchmark Execution Card */}
      <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-4">
        <h4 className="text-xs font-bold uppercase tracking-wider text-gray-700 flex items-center gap-2">
          <Play className="w-3.5 h-3.5 text-emerald-600" />
          <span>Execute Evaluation Run</span>
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              Benchmark Dataset
            </label>
            {datasets.length > 0 ? (
              <select
                value={selectedDatasetId}
                onChange={(e) => setSelectedDatasetId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 text-xs focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.item_count} questions)
                  </option>
                ))}
              </select>
            ) : (
              <div className="text-xs text-gray-500 py-2">
                No datasets found. Click &quot;Seed Starter Benchmarks&quot; above to begin.
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              Evaluation Methodology
            </label>
            <select
              value={evalType}
              onChange={(e) => setEvalType(e.target.value as any)}
              className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 text-xs focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            >
              <option value="deterministic">
                Deterministic Offline (Zero-cost, Lexical & Mathematical)
              </option>
              <option value="llm_judge">
                LLM-as-a-Judge (Model-based grading via configured BYOK)
              </option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleRunEvaluation}
              disabled={evaluating || !selectedDatasetId}
              className="w-full px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer shadow-xs disabled:opacity-50"
            >
              <Play className={`w-3.5 h-3.5 ${evaluating ? "animate-spin" : ""}`} />
              <span>{evaluating ? "Evaluating Assistant..." : "Run Evaluation Now"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid: Run History + Detailed Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Col: Historical Evaluation Runs */}
        <div className="lg:col-span-4 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500">
              Evaluation Runs ({runs.length})
            </h4>
          </div>

          {runs.length === 0 ? (
            <div className="p-6 rounded-2xl bg-gray-50 border border-dashed border-gray-200 text-center text-xs text-gray-500">
              No evaluation runs recorded yet. Run a benchmark above to assess quality.
            </div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {runs.map((r) => {
                const isSelected = selectedRun?.id === r.id;
                const metrics = r.metrics_summary || {};
                const recall = metrics.mean_recall_at_5 ?? 0;
                const faithfulness = metrics.mean_faithfulness ?? 0;

                return (
                  <div
                    key={r.id}
                    onClick={() => handleSelectRun(r.id)}
                    className={`p-3.5 rounded-xl border transition cursor-pointer space-y-2 ${
                      isSelected
                        ? "bg-blue-50/70 border-blue-500 text-gray-900 shadow-xs ring-1 ring-blue-500/20"
                        : "bg-white border-gray-200 hover:border-gray-300 text-gray-700 shadow-xs"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-gray-900">
                        Run {new Date(r.created_at).toLocaleDateString()}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold ${
                          r.status === "COMPLETED"
                            ? "bg-emerald-50 border border-emerald-200 text-emerald-700"
                            : r.status === "RUNNING"
                            ? "bg-blue-50 border border-blue-200 text-blue-700 animate-pulse"
                            : "bg-red-50 border border-red-200 text-red-700"
                        }`}
                      >
                        {r.status}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                      <div className="p-1.5 rounded bg-gray-50 border border-gray-200">
                        <span className="text-gray-500 block text-[9px] uppercase">Recall@5</span>
                        <span className="text-emerald-600 font-bold">{(recall * 100).toFixed(1)}%</span>
                      </div>
                      <div className="p-1.5 rounded bg-gray-50 border border-gray-200">
                        <span className="text-gray-500 block text-[9px] uppercase">Faithfulness</span>
                        <span className="text-blue-600 font-bold">{(faithfulness * 100).toFixed(1)}%</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-gray-500 font-mono">
                      <span>{r.eval_type}</span>
                      <span>{new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Col: Selected Run Results & Regression Comparison */}
        <div className="lg:col-span-8 space-y-4">
          {loadingRunDetail ? (
            <div className="p-12 rounded-2xl bg-white border border-gray-200 flex items-center justify-center text-xs text-gray-500">
              <RefreshCw className="w-5 h-5 animate-spin text-blue-600 mr-2" />
              <span>Loading benchmark results...</span>
            </div>
          ) : selectedRun ? (
            <div className="space-y-4">
              {/* Summary Metrics Bar */}
              <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h4 className="text-sm font-bold text-gray-900">
                      Evaluation Run Summary
                    </h4>
                    <p className="text-xs text-gray-500 font-mono">
                      ID: {selectedRun.id.slice(0, 13)}... • Type: {selectedRun.eval_type}
                    </p>
                  </div>

                  {/* Compare Dropdown */}
                  {runs.length > 1 && (
                    <div className="flex items-center gap-2">
                      <label className="text-[11px] text-gray-500">Compare with:</label>
                      <select
                        value={comparingWithRunId}
                        onChange={(e) => handleCompare(e.target.value)}
                        className="px-2.5 py-1 rounded-lg bg-white border border-gray-300 text-gray-900 text-xs focus:outline-none focus:border-blue-500"
                      >
                        <option value="">Select prior run...</option>
                        {runs
                          .filter((r) => r.id !== selectedRun.id)
                          .map((r) => (
                            <option key={r.id} value={r.id}>
                              {new Date(r.created_at).toLocaleDateString()} ({r.status})
                            </option>
                          ))}
                      </select>
                    </div>
                  )}
                </div>

                {/* Metrics Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-2">
                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                    <span className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">Recall @ 5</span>
                    <p className="text-lg font-bold text-emerald-600 font-mono mt-0.5">
                      {((selectedRun.metrics_summary?.mean_recall_at_5 ?? 0) * 100).toFixed(1)}%
                    </p>
                    {comparison && (
                      <span className={`text-[10px] font-mono flex items-center gap-0.5 mt-0.5 ${
                        comparison.metrics_delta.recall_delta >= 0 ? "text-emerald-600" : "text-red-600"
                      }`}>
                        {comparison.metrics_delta.recall_delta >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {(comparison.metrics_delta.recall_delta * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                    <span className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">Mean Reciprocal Rank</span>
                    <p className="text-lg font-bold text-sky-600 font-mono mt-0.5">
                      {(selectedRun.metrics_summary?.mean_mrr ?? 0).toFixed(3)}
                    </p>
                    {comparison && (
                      <span className={`text-[10px] font-mono flex items-center gap-0.5 mt-0.5 ${
                        comparison.metrics_delta.mrr_delta >= 0 ? "text-emerald-600" : "text-red-600"
                      }`}>
                        {comparison.metrics_delta.mrr_delta >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {comparison.metrics_delta.mrr_delta.toFixed(3)}
                      </span>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                    <span className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">Faithfulness</span>
                    <p className="text-lg font-bold text-blue-600 font-mono mt-0.5">
                      {((selectedRun.metrics_summary?.mean_faithfulness ?? 0) * 100).toFixed(1)}%
                    </p>
                    {comparison && (
                      <span className={`text-[10px] font-mono flex items-center gap-0.5 mt-0.5 ${
                        comparison.metrics_delta.faithfulness_delta >= 0 ? "text-emerald-600" : "text-red-600"
                      }`}>
                        {comparison.metrics_delta.faithfulness_delta >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {(comparison.metrics_delta.faithfulness_delta * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                    <span className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">Avg Latency</span>
                    <p className="text-lg font-bold text-purple-600 font-mono mt-0.5">
                      {selectedRun.metrics_summary?.mean_latency_ms ?? 0} ms
                    </p>
                    {comparison && (
                      <span className={`text-[10px] font-mono flex items-center gap-0.5 mt-0.5 ${
                        comparison.metrics_delta.latency_delta_ms <= 0 ? "text-emerald-600" : "text-amber-600"
                      }`}>
                        {comparison.metrics_delta.latency_delta_ms} ms
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Individual Question Drilldown */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500">
                  Question Breakdown & Retrieval Provenance ({selectedRun.results?.length ?? 0})
                </h4>

                <div className="space-y-3">
                  {selectedRun.results?.map((res, idx) => (
                    <div
                      key={res.id}
                      className="p-4 rounded-xl bg-white border border-gray-200 shadow-xs space-y-3 text-xs"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <span className="text-[10px] font-mono font-bold text-blue-600 uppercase">
                            Q{idx + 1}
                          </span>
                          <p className="text-gray-900 font-medium">{res.question}</p>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0 font-mono text-[10px]">
                          <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                            Recall: {(res.recall_score * 100).toFixed(0)}%
                          </span>
                          <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                            Faith: {(res.faithfulness_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>

                      {/* Generated Answer */}
                      <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 text-gray-800 space-y-1">
                        <span className="text-[10px] text-gray-500 uppercase font-semibold block">Generated Response</span>
                        <p className="text-xs leading-relaxed">{res.generated_answer}</p>
                      </div>

                      {/* Citations & Retrieved Contexts */}
                      {res.retrieved_chunks && res.retrieved_chunks.length > 0 && (
                        <div className="space-y-1.5">
                          <span className="text-[10px] text-gray-500 uppercase font-semibold block">
                            Retrieved Sources ({res.retrieved_chunks.length})
                          </span>
                          <div className="flex flex-wrap gap-2">
                            {res.retrieved_chunks.map((chk, cIdx) => (
                              <div
                                key={cIdx}
                                className="p-2 rounded-lg bg-gray-50 border border-gray-200 max-w-sm space-y-1"
                              >
                                <div className="flex items-center justify-between text-[10px] font-mono text-gray-600">
                                  <span className="text-gray-900 font-semibold">{chk.document_name}</span>
                                  <span>Score: {chk.score.toFixed(3)}</span>
                                </div>
                                <p className="text-[11px] text-gray-600 line-clamp-2">{chk.content}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 rounded-2xl bg-gray-50 border border-dashed border-gray-200 text-center text-xs text-gray-500">
              Select an evaluation run on the left to view metrics breakdown, retrieved chunks, and question-level responses.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
