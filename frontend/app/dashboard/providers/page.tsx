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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 border border-blue-200 flex items-center justify-center shadow-xs">
              <Key className="w-5 h-5" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-gray-900">Providers & BYOK Vault</h1>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Connect high-throughput inference engines, encrypt your own keys with authenticated Fernet storage, and monitor real token quotas.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg border border-gray-200 hover:border-gray-300 bg-white text-gray-700 text-xs font-medium transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shadow-xs"
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
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-xs transition flex items-center gap-2 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Provider Key</span>
          </button>
        </div>
      </div>

      {/* Quota & Usage Overview Cards */}
      {usageSummary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-2">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>Monthly Token Budget</span>
              <span className="font-mono text-blue-600 font-semibold">{usageSummary.percentage_used.toFixed(1)}%</span>
            </div>
            <div className="text-xl font-bold font-mono text-gray-900">
              {usageSummary.monthly_tokens_used.toLocaleString()}
              <span className="text-xs text-gray-500 font-normal ml-1">/ {usageSummary.monthly_tokens_limit.toLocaleString()}</span>
            </div>
            <div className="w-full bg-gray-100 h-1.5 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  usageSummary.percentage_used > 90 ? "bg-red-500" : usageSummary.percentage_used > 75 ? "bg-amber-500" : "bg-blue-600"
                }`}
                style={{ width: `${Math.min(usageSummary.percentage_used, 100)}%` }}
              />
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-2">
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>Today&apos;s Requests</span>
              <span className="text-gray-400 text-[11px]">Resets 00:00 UTC</span>
            </div>
            <div className="text-xl font-bold font-mono text-gray-900">
              {usageSummary.today_requests.toLocaleString()}
              <span className="text-xs text-gray-500 font-normal ml-1">/ {usageSummary.daily_request_limit.toLocaleString()} reqs</span>
            </div>
            <div className="w-full bg-gray-100 h-1.5 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${Math.min((usageSummary.today_requests / (usageSummary.daily_request_limit || 1)) * 100, 100)}%` }}
              />
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-1">
            <span className="text-xs text-gray-500 block">Prompt (Input) Tokens</span>
            <div className="text-xl font-bold font-mono text-gray-900">
              {usageSummary.monthly_prompt_tokens.toLocaleString()}
            </div>
            <span className="text-[11px] text-gray-400 block">System prompts & RAG context</span>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-gray-200 shadow-xs space-y-1">
            <span className="text-xs text-gray-500 block">Completion (Output) Tokens</span>
            <div className="text-xl font-bold font-mono text-gray-900">
              {usageSummary.monthly_completion_tokens.toLocaleString()}
            </div>
            <span className="text-[11px] text-gray-400 block">Generated assistant answers</span>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-gray-200 gap-8 text-xs font-semibold">
        <button
          type="button"
          onClick={() => setActiveTab("vault")}
          className={`pb-3 border-b-2 transition cursor-pointer flex items-center gap-2 ${
            activeTab === "vault"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-900"
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
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-900"
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
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-900"
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Usage Breakdown</span>
        </button>
      </div>

      {/* Error Alert */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tab 1: BYOK Vault Table */}
      {activeTab === "vault" && (
        <div className="space-y-4">
          {credentials.length === 0 ? (
            <div className="p-12 text-center rounded-2xl border border-dashed border-gray-200 bg-white shadow-xs space-y-3">
              <Key className="w-8 h-8 text-gray-400 mx-auto" />
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-gray-900">No BYOK credentials configured</h3>
                <p className="text-xs text-gray-500 max-w-md mx-auto">
                  By default, local requests route via OmniRoute gateway. Add your own Groq, Anthropic, Gemini, or OpenAI API key to execute direct provider inferences.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowAddModal(true)}
                className="mt-2 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Your First Key</span>
              </button>
            </div>
          ) : (
            <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-xs">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50 text-gray-600 font-medium">
                    <th className="py-3 px-4">Provider</th>
                    <th className="py-3 px-4">Display Name</th>
                    <th className="py-3 px-4">Masked Secret</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Last Tested</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {credentials.map((cred) => {
                    const isTesting = testingId === cred.id;

                    return (
                      <tr key={cred.id} className="hover:bg-gray-50/60 transition">
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="capitalize font-semibold text-gray-900">{cred.provider_name}</span>
                            {cred.is_default && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                                Default
                              </span>
                            )}
                          </div>
                          {cred.base_url && (
                            <span className="text-[10px] text-gray-500 font-mono block truncate max-w-xs">{cred.base_url}</span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-gray-800 font-medium">{cred.display_name}</td>

                        <td className="py-3.5 px-4 font-mono text-gray-700 text-[11px]">
                          <span className="px-2 py-0.5 rounded bg-gray-100 border border-gray-200 text-gray-800">
                            {cred.api_key_masked}
                          </span>
                        </td>

                        <td className="py-3.5 px-4">
                          {cred.status === "HEALTHY" && (
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              Healthy
                            </span>
                          )}
                          {cred.status === "UNHEALTHY" && (
                            <span
                              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-700 border border-red-200 cursor-help"
                              title={cred.error_message || "Endpoint error"}
                            >
                              <AlertCircle className="w-3 h-3 text-red-600" />
                              Unhealthy
                            </span>
                          )}
                          {cred.status === "REVOKED" && (
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 text-gray-600 border border-gray-200">
                              Revoked
                            </span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-gray-500 font-mono text-[11px]">
                          {cred.last_tested_at ? new Date(cred.last_tested_at).toLocaleString() : "Not tested yet"}
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {cred.is_active && (
                              <button
                                type="button"
                                onClick={() => handleTestCredential(cred)}
                                disabled={isTesting}
                                className="px-2.5 py-1 rounded-lg border border-gray-200 hover:border-gray-300 bg-white text-gray-700 hover:text-gray-900 transition text-[11px] font-medium flex items-center gap-1 cursor-pointer disabled:opacity-50 shadow-xs"
                              >
                                <Zap className={`w-3 h-3 text-amber-500 ${isTesting ? "animate-spin" : ""}`} />
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
                                className="px-2.5 py-1 rounded-lg border border-gray-200 hover:border-gray-300 bg-white text-gray-700 hover:text-gray-900 transition text-[11px] font-medium flex items-center gap-1 cursor-pointer shadow-xs"
                              >
                                <RotateCcw className="w-3 h-3 text-blue-600" />
                                <span>Rotate</span>
                              </button>
                            )}

                            {cred.is_active && (
                              <button
                                type="button"
                                onClick={() => handleRevokeCredential(cred.id)}
                                className="px-2.5 py-1 rounded-lg border border-gray-200 hover:border-gray-300 bg-white text-gray-600 hover:text-amber-700 transition text-[11px] font-medium cursor-pointer shadow-xs"
                              >
                                Revoke
                              </button>
                            )}

                            <button
                              type="button"
                              onClick={() => handleDeleteCredential(cred.id)}
                              className="p-1 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition cursor-pointer"
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
              className="p-5 rounded-2xl bg-white border border-gray-200 hover:border-gray-300 shadow-xs transition space-y-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-sm text-gray-900 flex items-center gap-2">
                    <span>{prov.display_name}</span>
                    {prov.name === "groq" && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-50 text-amber-700 border border-amber-200 font-semibold flex items-center gap-1">
                        <Flame className="w-2.5 h-2.5" /> Ultra-Fast LPU
                      </span>
                    )}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1">{prov.description}</p>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 border border-gray-200 font-mono">
                  {prov.name}
                </span>
              </div>

              {/* Verified Models Catalog */}
              <div className="space-y-2 border-t border-gray-100 pt-3">
                <span className="text-[11px] text-gray-500 uppercase tracking-wider font-semibold block">
                  Verified Production Models ({prov.models.length})
                </span>
                <div className="space-y-2">
                  {prov.models.map((m) => (
                    <div
                      key={m.model_id}
                      className="p-3 rounded-xl bg-gray-50 border border-gray-200 space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold text-gray-900">{m.display_name}</span>
                        <span className="text-[10px] font-mono text-gray-500">{m.context_window.toLocaleString()} ctx</span>
                      </div>
                      <p className="text-[11px] text-gray-600 leading-normal">{m.description}</p>
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        {m.supports_streaming && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-white text-gray-700 border border-gray-200 shadow-2xs font-medium">
                            Streaming
                          </span>
                        )}
                        {m.supports_tools && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                            Tool Calling
                          </span>
                        )}
                        {m.supports_vision && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-purple-50 text-purple-700 border border-purple-200 font-medium">
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
          <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-xs">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 text-gray-600 font-medium">
                  <th className="py-3 px-4">Provider</th>
                  <th className="py-3 px-4">Requests</th>
                  <th className="py-3 px-4">Prompt Tokens</th>
                  <th className="py-3 px-4">Completion Tokens</th>
                  <th className="py-3 px-4 text-right">Total Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {!usageSummary?.by_provider || usageSummary.by_provider.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-gray-500">
                      No provider usage recorded in the current monthly period yet.
                    </td>
                  </tr>
                ) : (
                  usageSummary.by_provider.map((p) => (
                    <tr key={p.provider} className="hover:bg-gray-50/60 transition">
                      <td className="py-3.5 px-4 font-semibold text-gray-900 capitalize">{p.provider}</td>
                      <td className="py-3.5 px-4 font-mono text-gray-700">{p.requests.toLocaleString()}</td>
                      <td className="py-3.5 px-4 font-mono text-gray-600">{p.prompt_tokens.toLocaleString()}</td>
                      <td className="py-3.5 px-4 font-mono text-gray-600">{p.completion_tokens.toLocaleString()}</td>
                      <td className="py-3.5 px-4 text-right font-mono font-bold text-blue-600">
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
        <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-blue-600" />
                <h3 className="font-semibold text-sm text-gray-900">Add Provider Credential</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-gray-400 hover:text-gray-600 cursor-pointer text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddCredential} className="space-y-4 text-xs">
              <div>
                <label className="text-gray-700 font-medium block mb-1">Provider Engine</label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none cursor-pointer shadow-xs"
                >
                  <option value="groq">Groq (Ultra-Fast LPUs)</option>
                  <option value="anthropic">Anthropic (Claude 3.5 Sonnet / Haiku)</option>
                  <option value="gemini">Google Gemini (1.5 Pro / Flash & 2.0)</option>
                  <option value="openai">OpenAI (Direct BYOK)</option>
                  <option value="omniroute">OmniRoute (Local Gateway)</option>
                </select>
              </div>

              <div>
                <label className="text-gray-700 font-medium block mb-1">Display Label</label>
                <input
                  type="text"
                  placeholder="e.g. Production Anthropic Key"
                  value={credDisplayName}
                  onChange={(e) => setCredDisplayName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none shadow-xs"
                />
              </div>

              <div>
                <label className="text-gray-700 font-medium block mb-1">API Key / Token</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="sk-..."
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    required
                    className="w-full px-3 py-2 pr-10 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono text-xs placeholder:text-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none shadow-xs"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="text-gray-700 font-medium block mb-1">
                  Custom Base URL <span className="text-gray-400 font-normal">(Optional override)</span>
                </label>
                <input
                  type="url"
                  placeholder="Leave empty for standard endpoint"
                  value={baseUrlInput}
                  onChange={(e) => setBaseUrlInput(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono text-xs placeholder:text-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none shadow-xs"
                />
                <p className="text-[11px] text-gray-400 mt-1">
                  Leave blank to use the official endpoint (e.g. https://api.groq.com/openai/v1 for Groq).
                </p>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="defaultCredCheck"
                  checked={isDefaultCred}
                  onChange={(e) => setIsDefaultCred(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <label htmlFor="defaultCredCheck" className="text-gray-700 cursor-pointer text-xs">
                  Set as default credential for {selectedProvider}
                </label>
              </div>

              <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-[11px] text-blue-800 flex items-start gap-2">
                <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-blue-600" />
                <span>
                  Keys are encrypted at rest with Fernet. Plaintext is decrypted strictly in memory at runtime and never returned to the frontend.
                </span>
              </div>

              {addError && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
                  {addError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-2 rounded-xl border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-medium cursor-pointer shadow-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingCred}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-xs transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
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
        <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <RotateCcw className="w-4 h-4 text-blue-600" />
                <h3 className="font-semibold text-sm text-gray-900">Rotate Credential: {rotatingCred.display_name}</h3>
              </div>
              <button
                type="button"
                onClick={() => setRotatingCred(null)}
                className="text-gray-400 hover:text-gray-600 cursor-pointer text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRotateKey} className="space-y-4 text-xs">
              <p className="text-gray-600 text-xs leading-normal">
                Enter a new API key. The key will be re-encrypted and active assistants will immediately use the updated secret without disruption.
              </p>

              <div>
                <label className="text-gray-700 font-medium block mb-1">New API Key</label>
                <div className="relative">
                  <input
                    type={showRotatePassword ? "text" : "password"}
                    placeholder="sk-..."
                    value={newKeyInput}
                    onChange={(e) => setNewKeyInput(e.target.value)}
                    required
                    className="w-full px-3 py-2 pr-10 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono text-xs placeholder:text-gray-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none shadow-xs"
                  />
                  <button
                    type="button"
                    onClick={() => setShowRotatePassword(!showRotatePassword)}
                    className="absolute right-3 top-2.5 text-gray-400 hover:text-gray-600 cursor-pointer"
                  >
                    {showRotatePassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              {rotateError && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
                  {rotateError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setRotatingCred(null)}
                  className="px-3.5 py-2 rounded-xl border border-gray-200 hover:bg-gray-50 text-gray-700 text-xs font-medium cursor-pointer shadow-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rotating}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-xs transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
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
