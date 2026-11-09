"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  ProviderCredential,
  ProviderDirectoryItem,
  ProviderUsageSummary,
} from "@/lib/api";
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Clock,
  Eye,
  EyeOff,
  Flame,
  Info,
  Key,
  Layers,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  Server,
  ShieldCheck,
  Trash2,
  Zap,
} from "lucide-react";

export default function ProvidersPage() {
  const [activeTab, setActiveTab] = useState<"vault" | "directory" | "usage">("vault");

  // Data states
  const [directory, setDirectory] = useState<ProviderDirectoryItem[]>([]);
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [usageSummary, setUsageSummary] = useState<ProviderUsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Add Credential Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("groq");
  const [credDisplayName, setCredDisplayName] = useState("");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [baseUrlInput, setBaseUrlInput] = useState("");
  const [isDefaultCred, setIsDefaultCred] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [savingCred, setSavingCred] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  // Rotate Key Modal
  const [rotatingCred, setRotatingCred] = useState<ProviderCredential | null>(null);
  const [newKeyInput, setNewKeyInput] = useState("");
  const [showRotatePassword, setShowRotatePassword] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [rotateError, setRotateError] = useState<string | null>(null);

  // Test status state mapping credId -> test result
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { valid: boolean; error: string | null }>>({});

  const fetchData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [dirData, credsData, usageData] = await Promise.all([
        api.getProviderDirectory().catch(() => []),
        api.listProviderCredentials().catch(() => []),
        api.getProviderUsageSummary().catch(() => null),
      ]);
      setDirectory(dirData);
      setCredentials(credsData);
      setUsageSummary(usageData);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load provider configuration.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAddCredential = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKeyInput.trim()) {
      setAddError("API Key cannot be empty.");
      return;
    }

    setSavingCred(true);
    setAddError(null);
    try {
      await api.createProviderCredential({
        provider_name: selectedProvider,
        display_name: credDisplayName.trim() || `${selectedProvider.toUpperCase()} Key`,
        api_key: apiKeyInput.trim(),
        base_url: baseUrlInput.trim() || undefined,
        is_default: isDefaultCred,
      });
      setShowAddModal(false);
      setApiKeyInput("");
      setBaseUrlInput("");
      setCredDisplayName("");
      setIsDefaultCred(false);
      await fetchData();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to store provider credential.");
    } finally {
      setSavingCred(false);
    }
  };

  const handleTestCredential = async (cred: ProviderCredential) => {
    setTestingId(cred.id);
    try {
      const res = await api.testProviderCredential(cred.id);
      setTestResults((prev) => ({ ...prev, [cred.id]: res }));
      // refresh status in table
      await fetchData();
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [cred.id]: { valid: false, error: err instanceof Error ? err.message : "Connection failed" },
      }));
    } finally {
      setTestingId(null);
    }
  };

  const handleRotateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rotatingCred || !newKeyInput.trim()) return;

    setRotating(true);
    setRotateError(null);
    try {
      await api.rotateProviderCredential(rotatingCred.id, newKeyInput.trim());
      setRotatingCred(null);
      setNewKeyInput("");
      await fetchData();
    } catch (err) {
      setRotateError(err instanceof Error ? err.message : "Failed to rotate credential.");
    } finally {
      setRotating(false);
    }
  };

  const handleRevokeCredential = async (id: string) => {
    if (!confirm("Are you sure you want to revoke this credential? Inference requiring this key will fail until a new key is added.")) {
      return;
    }
    try {
      await api.revokeProviderCredential(id);
      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to revoke credential");
    }
  };

  const handleDeleteCredential = async (id: string) => {
    if (!confirm("Permanently delete this BYOK credential? This cannot be undone.")) {
      return;
    }
    try {
      await api.deleteProviderCredential(id);
      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete credential");
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-600/10 text-blue-400 border border-blue-500/20 flex items-center justify-center">
              <Key className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-100">Providers & BYOK Vault</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Connect high-throughput inference engines, encrypt your own keys with authenticated Fernet storage, and monitor real token quotas.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900 text-slate-300 text-xs font-medium transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setAddError(null);
              setShowAddModal(true);
            }}
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-600/20 transition flex items-center gap-2 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Provider Key</span>
          </button>
        </div>
      </div>

      {/* Quota & Usage Overview Cards */}
      {usageSummary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Monthly Token Budget</span>
              <span className="font-mono text-blue-400 font-semibold">{usageSummary.percentage_used.toFixed(1)}%</span>
            </div>
            <div className="text-xl font-bold font-mono text-slate-100">
              {usageSummary.monthly_tokens_used.toLocaleString()}
              <span className="text-xs text-slate-500 font-normal ml-1">/ {usageSummary.monthly_tokens_limit.toLocaleString()}</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  usageSummary.percentage_used > 90 ? "bg-red-500" : usageSummary.percentage_used > 75 ? "bg-amber-500" : "bg-blue-500"
                }`}
                style={{ width: `${Math.min(usageSummary.percentage_used, 100)}%` }}
              />
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Today's Requests</span>
              <span className="text-slate-500 text-[11px]">Resets 00:00 UTC</span>
            </div>
            <div className="text-xl font-bold font-mono text-slate-100">
              {usageSummary.today_requests.toLocaleString()}
              <span className="text-xs text-slate-500 font-normal ml-1">/ {usageSummary.daily_request_limit.toLocaleString()} reqs</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${Math.min((usageSummary.today_requests / (usageSummary.daily_request_limit || 1)) * 100, 100)}%` }}
              />
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-1">
            <span className="text-xs text-slate-400 block">Prompt (Input) Tokens</span>
            <div className="text-xl font-bold font-mono text-slate-200">
              {usageSummary.monthly_prompt_tokens.toLocaleString()}
            </div>
            <span className="text-[11px] text-slate-500 block">System prompts & RAG context</span>
          </div>

          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-1">
            <span className="text-xs text-slate-400 block">Completion (Output) Tokens</span>
            <div className="text-xl font-bold font-mono text-slate-200">
              {usageSummary.monthly_completion_tokens.toLocaleString()}
            </div>
            <span className="text-[11px] text-slate-500 block">Generated assistant answers</span>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800 gap-8 text-xs font-semibold">
        <button
          type="button"
          onClick={() => setActiveTab("vault")}
          className={`pb-3 border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "vault"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          <span>Configured BYOK Vault ({credentials.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("directory")}
          className={`pb-3 border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "directory"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Server className="w-4 h-4" />
          <span>Provider Directory & Models ({directory.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("usage")}
          className={`pb-3 border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "usage"
              ? "border-blue-500 text-blue-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Usage Breakdown</span>
        </button>
      </div>

      {/* Error Alert */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tab 1: BYOK Vault Table */}
      {activeTab === "vault" && (
        <div className="space-y-4">
          {credentials.length === 0 ? (
            <div className="p-12 text-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/20 space-y-3">
              <Key className="w-8 h-8 text-slate-600 mx-auto" />
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-200">No BYOK credentials configured</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  By default, local requests route via OmniRoute gateway. Add your own Groq, Anthropic, Gemini, or OpenAI API key to execute direct provider inferences.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowAddModal(true)}
                className="mt-2 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition cursor-pointer inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Your First Key</span>
              </button>
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow-xl">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/80 text-slate-400 font-medium">
                    <th className="py-3 px-4">Provider</th>
                    <th className="py-3 px-4">Display Name</th>
                    <th className="py-3 px-4">Masked Secret</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Last Tested</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {credentials.map((cred) => {
                    const isTesting = testingId === cred.id;
                    const result = testResults[cred.id];

                    return (
                      <tr key={cred.id} className="hover:bg-slate-900/70 transition">
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="capitalize font-semibold text-slate-200">{cred.provider_name}</span>
                            {cred.is_default && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
                                Default
                              </span>
                            )}
                          </div>
                          {cred.base_url && (
                            <span className="text-[10px] text-slate-500 font-mono block truncate max-w-xs">{cred.base_url}</span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-slate-300 font-medium">{cred.display_name}</td>

                        <td className="py-3.5 px-4 font-mono text-slate-400 text-[11px]">
                          <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300">
                            {cred.api_key_masked}
                          </span>
                        </td>

                        <td className="py-3.5 px-4">
                          {cred.status === "HEALTHY" && (
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              <CheckCircle2 className="w-3 h-3" />
                              Healthy
                            </span>
                          )}
                          {cred.status === "UNHEALTHY" && (
                            <span
                              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-500/10 text-red-400 border border-red-500/20 cursor-help"
                              title={cred.error_message || "Endpoint error"}
                            >
                              <AlertCircle className="w-3 h-3" />
                              Unhealthy
                            </span>
                          )}
                          {cred.status === "REVOKED" && (
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
                              Revoked
                            </span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px]">
                          {cred.last_tested_at ? new Date(cred.last_tested_at).toLocaleString() : "Not tested yet"}
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {cred.is_active && (
                              <button
                                type="button"
                                onClick={() => handleTestCredential(cred)}
                                disabled={isTesting}
                                className="px-2.5 py-1 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900 text-slate-300 hover:text-slate-100 transition text-[11px] font-medium flex items-center gap-1 cursor-pointer disabled:opacity-50"
                              >
                                <Zap className={`w-3 h-3 text-amber-400 ${isTesting ? "animate-spin" : ""}`} />
                                <span>{isTesting ? "Testing..." : "Test"}</span>
                              </button>
                            )}

                            {cred.is_active && (
                              <button
                                type="button"
                                onClick={() => {
                                  setRotatingCred(cred);
                                  setNewKeyInput("");
                                  setRotateError(null);
                                }}
                                className="px-2.5 py-1 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900 text-slate-300 hover:text-slate-100 transition text-[11px] font-medium flex items-center gap-1 cursor-pointer"
                              >
                                <RotateCcw className="w-3 h-3 text-blue-400" />
                                <span>Rotate</span>
                              </button>
                            )}

                            {cred.is_active && (
                              <button
                                type="button"
                                onClick={() => handleRevokeCredential(cred.id)}
                                className="px-2.5 py-1 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900 text-slate-400 hover:text-amber-300 transition text-[11px] font-medium cursor-pointer"
                              >
                                Revoke
                              </button>
                            )}

                            <button
                              type="button"
                              onClick={() => handleDeleteCredential(cred.id)}
                              className="p-1 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-400 transition cursor-pointer"
                              title="Delete Credential"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Provider Directory */}
      {activeTab === "directory" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {directory.map((prov) => (
            <div
              key={prov.name}
              className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition space-y-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-sm text-slate-100 flex items-center gap-2">
                    <span>{prov.display_name}</span>
                    {prov.name === "groq" && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold flex items-center gap-1">
                        <Flame className="w-2.5 h-2.5" /> Ultra-Fast LPU
                      </span>
                    )}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">{prov.description}</p>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-mono">
                  {prov.name}
                </span>
              </div>

              {/* Verified Models Catalog */}
              <div className="space-y-2 border-t border-slate-800/60 pt-3">
                <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold block">
                  Verified Production Models ({prov.models.length})
                </span>
                <div className="space-y-2">
                  {prov.models.map((m) => (
                    <div
                      key={m.model_id}
                      className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold text-slate-200">{m.display_name}</span>
                        <span className="text-[10px] font-mono text-slate-500">{m.context_window.toLocaleString()} ctx</span>
                      </div>
                      <p className="text-[11px] text-slate-400 leading-normal">{m.description}</p>
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        {m.supports_streaming && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-slate-900 text-slate-300 border border-slate-800">
                            Streaming
                          </span>
                        )}
                        {m.supports_tools && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
                            Tool Calling
                          </span>
                        )}
                        {m.supports_vision && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-purple-500/10 text-purple-400 border border-purple-500/20 font-medium">
                            Vision
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 3: Usage Breakdown */}
      {activeTab === "usage" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow-xl">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/80 text-slate-400 font-medium">
                  <th className="py-3 px-4">Provider</th>
                  <th className="py-3 px-4">Requests</th>
                  <th className="py-3 px-4">Prompt Tokens</th>
                  <th className="py-3 px-4">Completion Tokens</th>
                  <th className="py-3 px-4 text-right">Total Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {!usageSummary?.by_provider || usageSummary.by_provider.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-500">
                      No provider usage recorded in the current monthly period yet.
                    </td>
                  </tr>
                ) : (
                  usageSummary.by_provider.map((p) => (
                    <tr key={p.provider} className="hover:bg-slate-900/70 transition">
                      <td className="py-3.5 px-4 font-semibold text-slate-200 capitalize">{p.provider}</td>
                      <td className="py-3.5 px-4 font-mono text-slate-300">{p.requests.toLocaleString()}</td>
                      <td className="py-3.5 px-4 font-mono text-slate-400">{p.prompt_tokens.toLocaleString()}</td>
                      <td className="py-3.5 px-4 font-mono text-slate-400">{p.completion_tokens.toLocaleString()}</td>
                      <td className="py-3.5 px-4 text-right font-mono font-bold text-blue-400">
                        {p.total_tokens.toLocaleString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add Credential Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-blue-400" />
                <h3 className="font-semibold text-sm text-slate-100">Add Provider Credential</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddCredential} className="space-y-4 text-xs">
              <div>
                <label className="text-slate-300 font-medium block mb-1">Provider Engine</label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-blue-500 focus:outline-none cursor-pointer"
                >
                  <option value="groq">Groq (Ultra-Fast LPUs)</option>
                  <option value="anthropic">Anthropic (Claude 3.5 Sonnet / Haiku)</option>
                  <option value="gemini">Google Gemini (1.5 Pro / Flash & 2.0)</option>
                  <option value="openai">OpenAI (Direct BYOK)</option>
                  <option value="omniroute">OmniRoute (Local Gateway)</option>
                </select>
              </div>

              <div>
                <label className="text-slate-300 font-medium block mb-1">Display Label</label>
                <input
                  type="text"
                  placeholder="e.g. Production Anthropic Key"
                  value={credDisplayName}
                  onChange={(e) => setCredDisplayName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-300 font-medium block mb-1">API Key / Token</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="sk-..."
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    required
                    className="w-full px-3 py-2 pr-10 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 font-mono text-xs focus:border-blue-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="text-slate-300 font-medium block mb-1">
                  Custom Base URL <span className="text-slate-500 font-normal">(Optional override)</span>
                </label>
                <input
                  type="url"
                  placeholder="https://api.provider.com/v1"
                  value={baseUrlInput}
                  onChange={(e) => setBaseUrlInput(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 font-mono text-xs focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="defaultCredCheck"
                  checked={isDefaultCred}
                  onChange={(e) => setIsDefaultCred(e.target.checked)}
                  className="rounded bg-slate-950 border-slate-800 text-blue-600 focus:ring-0 cursor-pointer"
                />
                <label htmlFor="defaultCredCheck" className="text-slate-300 cursor-pointer text-xs">
                  Set as default credential for {selectedProvider}
                </label>
              </div>

              <div className="p-3 rounded-xl bg-blue-950/20 border border-blue-900/40 text-[11px] text-blue-300 flex items-start gap-2">
                <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-blue-400" />
                <span>
                  Keys are encrypted at rest with Fernet. Plaintext is decrypted strictly in memory at runtime and never returned to the frontend.
                </span>
              </div>

              {addError && (
                <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
                  {addError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-2 rounded-xl border border-slate-800 hover:border-slate-700 bg-slate-900 text-slate-300 text-xs font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingCred}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-600/20 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {savingCred ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                  <span>Save Credential</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rotate Key Modal */}
      {rotatingCred && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <RotateCcw className="w-4 h-4 text-blue-400" />
                <h3 className="font-semibold text-sm text-slate-100">Rotate Credential: {rotatingCred.display_name}</h3>
              </div>
              <button
                type="button"
                onClick={() => setRotatingCred(null)}
                className="text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRotateKey} className="space-y-4 text-xs">
              <p className="text-slate-400 text-xs leading-normal">
                Enter a new API key. The key will be re-encrypted and active assistants will immediately use the updated secret without disruption.
              </p>

              <div>
                <label className="text-slate-300 font-medium block mb-1">New API Key</label>
                <div className="relative">
                  <input
                    type={showRotatePassword ? "text" : "password"}
                    placeholder="sk-..."
                    value={newKeyInput}
                    onChange={(e) => setNewKeyInput(e.target.value)}
                    required
                    className="w-full px-3 py-2 pr-10 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 font-mono text-xs focus:border-blue-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowRotatePassword(!showRotatePassword)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 cursor-pointer"
                  >
                    {showRotatePassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              {rotateError && (
                <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
                  {rotateError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setRotatingCred(null)}
                  className="px-3.5 py-2 rounded-xl border border-slate-800 hover:border-slate-700 bg-slate-900 text-slate-300 text-xs font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rotating}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-600/20 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {rotating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                  <span>Rotate Secret</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
