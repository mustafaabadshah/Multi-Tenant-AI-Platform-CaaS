"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  AssistantItem,
  EvalDataset,
  EvalRun,
  EvalRunResult,
} from "@/lib/api";
import {
  Sparkles,
  Play,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  Database,
  BarChart3,
  Layers,
  ArrowRight,
  Plus,
  AlertTriangle,
  ChevronRight,
  TrendingUp,
  Cpu,
  BookOpen,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";
import Badge from "@/components/ui/Badge";
import Modal from "@/components/ui/Modal";

export default function EvaluationsDashboardPage() {
  const { activeWorkspace } = useAuth();

  // Tabs: "datasets" | "run" | "history" | "compare"
  const [activeTab, setActiveTab] = useState<"datasets" | "run" | "history">("datasets");

  // Data states
  const [assistants, setAssistants] = useState<AssistantItem[]>([]);
  const [datasets, setDatasets] = useState<EvalDataset[]>([]);
  const [selectedDatasetDetail, setSelectedDatasetDetail] = useState<EvalDataset | null>(null);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [selectedRunDetail, setSelectedRunDetail] = useState<EvalRun | null>(null);

  // Run Configuration state
  const [targetAssistantId, setTargetAssistantId] = useState<string>("");
  const [targetDatasetId, setTargetDatasetId] = useState<string>("");
  const [isRunningEval, setIsRunningEval] = useState(false);

  // Seeding & dataset creation modal
  const [isSeeding, setIsSeeding] = useState(false);
  const [createDatasetModalOpen, setCreateDatasetModalOpen] = useState(false);
  const [newDatasetName, setNewDatasetName] = useState("");
  const [newDatasetDesc, setNewDatasetDesc] = useState("");
  const [newDatasetQuestion, setNewDatasetQuestion] = useState("");
  const [newDatasetExpectedAnswer, setNewDatasetExpectedAnswer] = useState("");
  const [isCreatingDataset, setIsCreatingDataset] = useState(false);

  // Loading & error states
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Initial load
  useEffect(() => {
    async function init() {
      try {
        setLoadingInitial(true);
        setErrorMessage(null);
        const [assts, dsets, rlist] = await Promise.all([
          api.listAssistants().catch(() => []),
          api.listEvalDatasets().catch(() => []),
          api.listEvalRuns().catch(() => []),
        ]);
        setAssistants(assts);
        setDatasets(dsets);
        setRuns(rlist);

        if (assts.length > 0) setTargetAssistantId(assts[0].id);
        if (dsets.length > 0) setTargetDatasetId(dsets[0].id);
      } catch (err: any) {
        setErrorMessage(err.message || "Failed to initialize Evaluation Studio.");
      } finally {
        setLoadingInitial(false);
      }
    }
    init();
  }, [activeWorkspace?.tenant_id]);

  // Seed Starter Benchmarks
  const handleSeedBenchmarks = async () => {
    try {
      setIsSeeding(true);
      setErrorMessage(null);
      await api.seedStarterBenchmarks();
      const updated = await api.listEvalDatasets();
      setDatasets(updated);
      setSuccessMessage("Starter benchmarks seeded successfully.");
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to seed starter benchmarks.");
    } finally {
      setIsSeeding(false);
    }
  };

  // Inspect Dataset Details
  const handleInspectDataset = async (datasetId: string) => {
    try {
      setLoadingDetail(true);
      const detail = await api.getEvalDataset(datasetId);
      setSelectedDatasetDetail(detail);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load dataset details.");
    } finally {
      setLoadingDetail(false);
    }
  };

  // Inspect Run Details
  const handleInspectRun = async (runId: string) => {
    try {
      setLoadingDetail(true);
      const detail = await api.getEvalRun(runId);
      setSelectedRunDetail(detail);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load evaluation run details.");
    } finally {
      setLoadingDetail(false);
    }
  };

  // Trigger Benchmark Run
  const handleExecuteRun = async () => {
    if (!targetAssistantId || !targetDatasetId) {
      setErrorMessage("Please select both an assistant and a benchmark dataset.");
      return;
    }
    try {
      setIsRunningEval(true);
      setErrorMessage(null);
      const newRun = await api.executeEvalRun({
        assistant_id: targetAssistantId,
        dataset_id: targetDatasetId,
        eval_type: "deterministic",
      });
      // Fetch full details and switch to history view
      const detail = await api.getEvalRun(newRun.id);
      setSelectedRunDetail(detail);
      const updatedRuns = await api.listEvalRuns();
      setRuns(updatedRuns);
      setActiveTab("history");
      setSuccessMessage("Evaluation completed successfully.");
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || "Evaluation run failed.");
    } finally {
      setIsRunningEval(false);
    }
  };

  // Create Custom Dataset
  const handleCreateDataset = async () => {
    if (!newDatasetName.trim() || !newDatasetQuestion.trim()) {
      setErrorMessage("Dataset name and at least one test question are required.");
      return;
    }
    try {
      setIsCreatingDataset(true);
      await api.createEvalDataset({
        name: newDatasetName.trim(),
        description: newDatasetDesc.trim() || undefined,
        items: [
          {
            question: newDatasetQuestion.trim(),
            expected_answer: newDatasetExpectedAnswer.trim() || undefined,
          },
        ],
      });
      const updated = await api.listEvalDatasets();
      setDatasets(updated);
      setCreateDatasetModalOpen(false);
      setNewDatasetName("");
      setNewDatasetDesc("");
      setNewDatasetQuestion("");
      setNewDatasetExpectedAnswer("");
      setSuccessMessage("Custom benchmark dataset created.");
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to create dataset.");
    } finally {
      setIsCreatingDataset(false);
    }
  };

  if (loadingInitial) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-gray-900">RAG Evaluation Studio</h1>
            <Badge variant="blue">M28 Benchmark Runner</Badge>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Empirically evaluate assistant retrieval quality, context recall, faithfulness, and latency using reproducible benchmark test sets.
          </p>
        </div>

        {/* Global tab navigation */}
        <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-xl text-xs font-medium text-gray-600">
          <button
            type="button"
            onClick={() => setActiveTab("datasets")}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === "datasets"
                ? "bg-white text-gray-900 shadow-xs font-semibold"
                : "hover:text-gray-900"
            }`}
          >
            Datasets ({datasets.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("run")}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === "run"
                ? "bg-white text-gray-900 shadow-xs font-semibold"
                : "hover:text-gray-900"
            }`}
          >
            Run Benchmark
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("history")}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              activeTab === "history"
                ? "bg-white text-gray-900 shadow-xs font-semibold"
                : "hover:text-gray-900"
            }`}
          >
            History & Scorecards ({runs.length})
          </button>
        </div>
      </div>

      {/* Alert Banners */}
      {errorMessage && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center justify-between">
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage(null)} className="text-rose-500 hover:text-rose-700 font-bold">✕</button>
        </div>
      )}
      {successMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700 flex items-center justify-between">
          <span>{successMessage}</span>
          <button type="button" onClick={() => setSuccessMessage(null)} className="text-emerald-500 hover:text-emerald-700 font-bold">✕</button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: DATASETS */}
      {/* ========================================================================= */}
      {activeTab === "datasets" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Benchmark Test Datasets</h2>
              <p className="text-xs text-gray-500">Standardized question sets with ground truth references for objective model evaluation.</p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                icon={Database}
                disabled={isSeeding}
                onClick={handleSeedBenchmarks}
              >
                {isSeeding ? "Seeding..." : "Seed Starter Benchmarks"}
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={Plus}
                onClick={() => setCreateDatasetModalOpen(true)}
              >
                Create Dataset
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {datasets.map((ds) => (
              <div
                key={ds.id}
                className="p-5 bg-white border border-gray-200 rounded-2xl shadow-xs hover:border-blue-300 transition-all flex flex-col justify-between space-y-4"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-sm text-gray-900">{ds.name}</h3>
                    {ds.is_system && <Badge variant="gray">System</Badge>}
                  </div>
                  <p className="text-xs text-gray-500 line-clamp-2">
                    {ds.description || "No description provided."}
                  </p>
                </div>

                <div className="pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
                  <span className="font-medium text-gray-600">{ds.item_count} test items</span>
                  <button
                    type="button"
                    onClick={() => handleInspectDataset(ds.id)}
                    className="text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                  >
                    View Items <ArrowRight size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {datasets.length === 0 && (
            <div className="text-center p-12 bg-gray-50 border border-dashed border-gray-200 rounded-2xl space-y-3">
              <p className="text-sm text-gray-500">No benchmark datasets found for this tenant.</p>
              <Button variant="outline" size="sm" onClick={handleSeedBenchmarks}>
                Seed Starter Benchmarks
              </Button>
            </div>
          )}

          {/* Dataset Detail Inspection Modal */}
          {selectedDatasetDetail && (
            <Modal
              isOpen={!!selectedDatasetDetail}
              onClose={() => setSelectedDatasetDetail(null)}
              title={selectedDatasetDetail.name}
            >
              <div className="space-y-4 text-xs">
                <p className="text-gray-500">{selectedDatasetDetail.description}</p>
                <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                  {(selectedDatasetDetail.items || []).map((item, idx) => (
                    <div key={item.id} className="p-3 bg-gray-50 border border-gray-200 rounded-xl space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] font-semibold text-gray-700">
                        <span>Question {idx + 1}</span>
                        {item.is_adversarial && <Badge variant="amber">Adversarial</Badge>}
                        {item.is_unanswerable && <Badge variant="gray">Unanswerable</Badge>}
                      </div>
                      <p className="font-medium text-gray-900">{item.question}</p>
                      {item.expected_answer && (
                        <div className="text-gray-600 bg-white p-2 rounded-lg border border-gray-100">
                          <span className="text-[10px] uppercase font-semibold text-gray-400 block mb-0.5">Ground Truth:</span>
                          {item.expected_answer}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </Modal>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: RUN BENCHMARK */}
      {/* ========================================================================= */}
      {activeTab === "run" && (
        <div className="max-w-2xl mx-auto p-6 bg-white border border-gray-200 rounded-2xl shadow-xs space-y-6">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Run Evaluation Suite</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Select an active assistant and a benchmark dataset to evaluate retrieval groundedness and response quality.
            </p>
          </div>

          <div className="space-y-4 text-xs">
            {/* Assistant selector */}
            <div className="space-y-1.5">
              <label className="font-medium text-gray-700">Target Assistant</label>
              <select
                value={targetAssistantId}
                onChange={(e) => setTargetAssistantId(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-gray-800"
              >
                {assistants.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.llm_provider || "OmniRoute"} • {a.default_model || "auto"})
                  </option>
                ))}
              </select>
            </div>

            {/* Dataset selector */}
            <div className="space-y-1.5">
              <label className="font-medium text-gray-700">Evaluation Dataset</label>
              <select
                value={targetDatasetId}
                onChange={(e) => setTargetDatasetId(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-gray-800"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.item_count} test questions)
                  </option>
                ))}
              </select>
            </div>

            {/* Execution mode info */}
            <div className="p-3 bg-blue-50/60 border border-blue-100 rounded-xl text-blue-900 space-y-1">
              <span className="font-semibold flex items-center gap-1.5">
                <Cpu size={13} className="text-blue-600" />
                Deterministic Local RAG Evaluation (Free-First Mode)
              </span>
              <p className="text-[11px] text-blue-700 leading-relaxed">
                Evaluates hybrid keyword and vector retrieval, context recall, answer completeness, and claim grounding directly against the assistant's connected Knowledge Bases. Zero paid API keys or external LLM judge tokens required.
              </p>
            </div>
          </div>

          <div className="pt-2">
            <Button
              variant="primary"
              size="md"
              icon={Play}
              disabled={isRunningEval || !targetAssistantId || !targetDatasetId}
              onClick={handleExecuteRun}
              className="w-full justify-center"
            >
              {isRunningEval ? "Running Benchmark Test Suite..." : "Start Evaluation Run"}
            </Button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: RUN HISTORY & SCORECARD */}
      {/* ========================================================================= */}
      {activeTab === "history" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Run History & Quality Scorecards</h2>
              <p className="text-xs text-gray-500">Audit logs and calculated performance metrics across completed evaluation runs.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Runs list column */}
            <div className="lg:col-span-1 space-y-3 max-h-[600px] overflow-y-auto pr-1">
              {runs.map((r) => {
                const isSelected = selectedRunDetail?.id === r.id;
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => handleInspectRun(r.id)}
                    className={`w-full text-left p-4 rounded-2xl border transition-all cursor-pointer ${
                      isSelected
                        ? "bg-blue-50/70 border-blue-300 shadow-xs"
                        : "bg-white border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-bold text-gray-900 truncate max-w-[150px]">
                        {(r as any).assistant_name || "Assistant"}
                      </span>
                      <Badge variant={r.status === "COMPLETED" ? "green" : "gray"}>
                        {r.status}
                      </Badge>
                    </div>
                    <p className="text-[11px] text-gray-500 truncate mb-2">{(r as any).dataset_name || "Benchmark Dataset"}</p>
                    <div className="flex items-center justify-between text-[10px] text-gray-400">
                      <span>{r.result_count || r.metrics_summary?.total_items || 0} items</span>
                      <span>{new Date(r.created_at).toLocaleDateString()}</span>
                    </div>
                  </button>
                );
              })}

              {runs.length === 0 && (
                <div className="p-8 text-center bg-gray-50 border border-dashed border-gray-200 rounded-2xl text-xs text-gray-400">
                  No evaluation runs recorded yet.
                </div>
              )}
            </div>

            {/* Scorecard detail column */}
            <div className="lg:col-span-2">
              {loadingDetail ? (
                <div className="py-20 flex justify-center">
                  <Spinner size="md" />
                </div>
              ) : selectedRunDetail ? (
                <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-xs space-y-6">
                  {/* Scorecard Header */}
                  <div className="flex items-start justify-between border-b border-gray-100 pb-4">
                    <div>
                      <h3 className="font-bold text-base text-gray-900">{(selectedRunDetail as any).assistant_name || "Assistant"} Scorecard</h3>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Dataset: <span className="font-medium text-gray-600">{(selectedRunDetail as any).dataset_name || "Benchmark Dataset"}</span> • Run: {new Date(selectedRunDetail.created_at).toLocaleString()}
                      </p>
                    </div>
                    <Badge variant={selectedRunDetail.status === "COMPLETED" ? "green" : "amber"}>
                      {selectedRunDetail.status}
                    </Badge>
                  </div>

                  {/* High-level Metric Gauges */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 bg-gray-50 border border-gray-100 rounded-xl text-center">
                      <span className="text-[10px] uppercase font-bold text-gray-400">Context Recall</span>
                      <div className="text-lg font-bold text-blue-600 mt-0.5">
                        {typeof selectedRunDetail.metrics_summary?.avg_recall === "number"
                          ? `${(selectedRunDetail.metrics_summary.avg_recall * 100).toFixed(1)}%`
                          : "NOT_EVALUATED"}
                      </div>
                    </div>
                    <div className="p-3 bg-gray-50 border border-gray-100 rounded-xl text-center">
                      <span className="text-[10px] uppercase font-bold text-gray-400">Precision@k</span>
                      <div className="text-lg font-bold text-emerald-600 mt-0.5">
                        {typeof selectedRunDetail.metrics_summary?.avg_precision === "number"
                          ? `${(selectedRunDetail.metrics_summary.avg_precision * 100).toFixed(1)}%`
                          : "NOT_EVALUATED"}
                      </div>
                    </div>
                    <div className="p-3 bg-gray-50 border border-gray-100 rounded-xl text-center">
                      <span className="text-[10px] uppercase font-bold text-gray-400">MRR Score</span>
                      <div className="text-lg font-bold text-purple-600 mt-0.5">
                        {typeof selectedRunDetail.metrics_summary?.mrr === "number"
                          ? selectedRunDetail.metrics_summary.mrr.toFixed(3)
                          : "NOT_EVALUATED"}
                      </div>
                    </div>
                    <div className="p-3 bg-gray-50 border border-gray-100 rounded-xl text-center">
                      <span className="text-[10px] uppercase font-bold text-gray-400">Avg Latency</span>
                      <div className="text-lg font-bold text-gray-700 mt-0.5">
                        {typeof selectedRunDetail.metrics_summary?.avg_latency_ms === "number"
                          ? `${Math.round(selectedRunDetail.metrics_summary.avg_latency_ms)} ms`
                          : "NOT_EVALUATED"}
                      </div>
                    </div>
                  </div>

                  {/* Individual test results table */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider">Individual Case Outcomes ({selectedRunDetail.results?.length || 0})</h4>
                    <div className="border border-gray-100 rounded-xl overflow-hidden text-xs max-h-72 overflow-y-auto">
                      <table className="w-full text-left border-collapse">
                        <thead className="bg-gray-50 text-[11px] text-gray-500 border-b border-gray-100">
                          <tr>
                            <th className="py-2.5 px-3">Status</th>
                            <th className="py-2.5 px-3">Question</th>
                            <th className="py-2.5 px-3">Chunks</th>
                            <th className="py-2.5 px-3 text-right">Latency</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 text-gray-700">
                          {selectedRunDetail.results?.map((res, i) => (
                            <tr key={res.id || i} className="hover:bg-gray-50/50">
                              <td className="py-2 px-3">
                                {!res.error_message ? (
                                  <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold text-[11px]">
                                    <CheckCircle2 size={13} /> Pass
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 text-rose-600 font-semibold text-[11px]">
                                    <XCircle size={13} /> Fail
                                  </span>
                                )}
                              </td>
                              <td className="py-2 px-3 font-medium text-gray-900 truncate max-w-xs">{res.question}</td>
                              <td className="py-2 px-3 text-gray-500">{res.retrieved_chunks?.length || 0}</td>
                              <td className="py-2 px-3 text-right text-gray-500">{res.latency_ms ? `${Math.round(res.latency_ms)} ms` : "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-12 text-center bg-gray-50 border border-dashed border-gray-200 rounded-2xl text-xs text-gray-400">
                  Select a completed evaluation run to inspect its detailed scorecard.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal: Create Dataset */}
      {createDatasetModalOpen && (
        <Modal
          isOpen={createDatasetModalOpen}
          onClose={() => setCreateDatasetModalOpen(false)}
          title="Create Custom Benchmark Dataset"
        >
          <div className="space-y-4 text-xs">
            <div className="space-y-1">
              <label className="font-semibold text-gray-700">Dataset Name</label>
              <input
                type="text"
                value={newDatasetName}
                onChange={(e) => setNewDatasetName(e.target.value)}
                placeholder="e.g., Support Policy Q&A 2026"
                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-gray-800"
              />
            </div>
            <div className="space-y-1">
              <label className="font-semibold text-gray-700">Description (Optional)</label>
              <input
                type="text"
                value={newDatasetDesc}
                onChange={(e) => setNewDatasetDesc(e.target.value)}
                placeholder="Brief summary of test coverage..."
                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-gray-800"
              />
            </div>
            <div className="space-y-1">
              <label className="font-semibold text-gray-700">Test Question 1</label>
              <input
                type="text"
                value={newDatasetQuestion}
                onChange={(e) => setNewDatasetQuestion(e.target.value)}
                placeholder="What is our SLA for critical priority issues?"
                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-gray-800"
              />
            </div>
            <div className="space-y-1">
              <label className="font-semibold text-gray-700">Expected Ground Truth Answer (Optional)</label>
              <textarea
                value={newDatasetExpectedAnswer}
                onChange={(e) => setNewDatasetExpectedAnswer(e.target.value)}
                rows={2}
                placeholder="Critical priority issues must be acknowledged within 15 minutes..."
                className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 text-gray-800"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setCreateDatasetModalOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" disabled={isCreatingDataset} onClick={handleCreateDataset}>
                {isCreatingDataset ? "Creating..." : "Save Dataset"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
