"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  APIKeyItem,
  APIKeyCreateRequest,
} from "@/lib/api";
import {
  Key,
  Plus,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
  Loader2,
  Shield,
  Terminal,
  Clock,
  CheckCircle2,
  Eye,
  AlertCircle,
} from "lucide-react";

export default function DeveloperApiKeysSection() {
  const [keys, setKeys] = useState<APIKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Creation Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([
    "assistant:read",
    "assistant:chat",
  ]);
  const [expiresDays, setExpiresDays] = useState<number | null>(30);

  // Revealed Secret State (Only shown once upon creation)
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [copiedRawKey, setCopiedRawKey] = useState(false);

  const loadKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listApiKeys();
      setKeys(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load API keys";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyName.trim()) return;

    setCreating(true);
    setError(null);
    try {
      const payload: APIKeyCreateRequest = {
        name: keyName.trim(),
        scopes: selectedScopes,
        expires_days: expiresDays,
      };
      const created = await api.createApiKey(payload);
      setNewlyCreatedKey(created.raw_key);
      setShowCreateModal(false);
      setKeyName("");
      // Reload keys list
      loadKeys();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Key generation failed";
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleRevokeKey = async (keyId: string, name: string) => {
    if (!confirm(`Are you sure you want to revoke API key "${name}"? Any external services using this key will be disconnected immediately.`)) {
      return;
    }

    try {
      await api.revokeApiKey(keyId);
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to revoke key";
      alert(msg);
    }
  };

  const toggleScope = (scope: string) => {
    if (selectedScopes.includes(scope)) {
      if (selectedScopes.length > 1) {
        setSelectedScopes(selectedScopes.filter((s) => s !== scope));
      }
    } else {
      setSelectedScopes([...selectedScopes, scope]);
    }
  };

  const copySecret = () => {
    if (!newlyCreatedKey) return;
    navigator.clipboard.writeText(newlyCreatedKey);
    setCopiedRawKey(true);
    setTimeout(() => setCopiedRawKey(false), 2000);
  };

  return (
    <div className="space-y-5 text-slate-100">
      {/* Newly Created Secret Modal Alert */}
      {newlyCreatedKey && (
        <div className="rounded-2xl border border-amber-500/40 bg-amber-950/30 p-5 shadow-2xl backdrop-blur-xl animate-fadeIn">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div className="flex-1 space-y-2">
              <h3 className="text-sm font-semibold text-amber-300">
                Save Your Secret API Key Now
              </h3>
              <p className="text-xs leading-relaxed text-slate-300">
                This secret token will <strong className="text-white">never be displayed again</strong>.
                Store it in your environment variables or a secure secret manager.
              </p>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="text"
                  readOnly
                  value={newlyCreatedKey}
                  className="flex-1 rounded-xl border border-amber-500/40 bg-slate-950 px-3.5 py-2.5 font-mono text-xs text-amber-300 select-all focus:outline-none"
                />
                <button
                  type="button"
                  onClick={copySecret}
                  className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-4 py-2.5 text-xs font-semibold text-slate-950 hover:bg-amber-400 transition cursor-pointer"
                >
                  {copiedRawKey ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                  <span>{copiedRawKey ? "Copied" : "Copy Key"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setNewlyCreatedKey(null)}
                  className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2.5 text-xs text-slate-300 hover:bg-slate-700 cursor-pointer"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Keys Container */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Key className="h-4 w-4 text-sky-400" />
              <span>Developer API Keys & Scopes</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Programmatic access tokens for the REST API and official Python / TypeScript SDKs.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 rounded-xl bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white shadow-lg shadow-sky-600/20 hover:bg-sky-500 transition cursor-pointer shrink-0"
          >
            <Plus className="h-4 w-4" />
            <span>Create New API Key</span>
          </button>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-800 bg-rose-950/40 p-3 text-xs text-rose-300 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Keys Table / List */}
        {loading ? (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-sky-500" />
          </div>
        ) : keys.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center">
            <Key className="mx-auto h-8 w-8 text-slate-600 mb-2" />
            <p className="text-xs text-slate-400 font-medium">No API keys created yet</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Generate a scoped key to integrate assistants into your backend or applications.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-3 font-medium">Name & Prefix</th>
                  <th className="pb-3 font-medium">Scopes</th>
                  <th className="pb-3 font-medium">Expires</th>
                  <th className="pb-3 font-medium">Last Used</th>
                  <th className="pb-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {keys.map((k) => (
                  <tr key={k.id} className="hover:bg-slate-800/20 transition-colors">
                    <td className="py-3.5 pr-4">
                      <div className="font-semibold text-slate-100">{k.name}</div>
                      <div className="font-mono text-[11px] text-slate-400 mt-0.5">
                        {k.key_prefix}...
                      </div>
                    </td>
                    <td className="py-3.5 pr-4">
                      <div className="flex flex-wrap gap-1">
                        {k.scopes.map((s) => (
                          <span
                            key={s}
                            className="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-sky-400 border border-slate-700"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3.5 pr-4 text-slate-400">
                      {k.expires_at ? (
                        <span className="flex items-center gap-1 font-mono text-[11px]">
                          <Clock className="h-3 w-3 text-slate-500" />
                          {new Date(k.expires_at).toLocaleDateString()}
                        </span>
                      ) : (
                        <span className="text-[11px] text-slate-400">Never</span>
                      )}
                    </td>
                    <td className="py-3.5 pr-4 text-slate-400 font-mono text-[11px]">
                      {k.last_used_at
                        ? new Date(k.last_used_at).toLocaleDateString()
                        : "Never used"}
                    </td>
                    <td className="py-3.5 text-right">
                      <button
                        type="button"
                        onClick={() => handleRevokeKey(k.id, k.name)}
                        className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/10 hover:text-rose-400 transition cursor-pointer"
                        title="Revoke Key"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* SDK & Quick Integration Samples */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-xl space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
          <Terminal className="h-4 w-4 text-emerald-400" />
          <span>Quick SDK Integration</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {/* TypeScript SDK */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex items-center justify-between text-slate-200 font-semibold">
              <span>TypeScript (@mmaip/client)</span>
              <span className="text-[10px] font-mono text-slate-500">Node / Web</span>
            </div>
            <pre className="rounded-lg bg-slate-900 p-2.5 font-mono text-[11px] text-slate-300 overflow-x-auto leading-relaxed">
{`import { MMAIPClient } from "@mmaip/client";

const client = new MMAIPClient({
  apiKey: "mmaip_live_...",
});

for await (const chunk of client.streamChat(
  "assistant-id",
  "Hello!"
)) {
  process.stdout.write(chunk.delta || "");
}`}
            </pre>
          </div>

          {/* Python SDK */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex items-center justify-between text-slate-200 font-semibold">
              <span>Python (mmaip)</span>
              <span className="text-[10px] font-mono text-slate-500">Python 3.10+</span>
            </div>
            <pre className="rounded-lg bg-slate-900 p-2.5 font-mono text-[11px] text-slate-300 overflow-x-auto leading-relaxed">
{`from mmaip import MMAIPClient

client = MMAIPClient(api_key="mmaip_live_...")

for event in client.chat.stream(
    assistant_id="assistant-id",
    message="Hello!",
):
    if event.get("delta"):
        print(event["delta"], end="", flush=True)`}
            </pre>
          </div>
        </div>
      </div>

      {/* Create Key Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Create Developer API Key</h3>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-white"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateKey} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Key Description / Name</label>
                <input
                  type="text"
                  required
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  placeholder="e.g., Production Next.js App"
                  className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-white placeholder-slate-500 focus:border-sky-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1.5">Scopes & Permissions</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedScopes.includes("assistant:read")}
                      onChange={() => toggleScope("assistant:read")}
                      className="rounded border-slate-700 text-sky-500 focus:ring-sky-500"
                    />
                    <div>
                      <span className="font-mono text-slate-200">assistant:read</span>
                      <span className="text-[11px] text-slate-400 block">List workspace assistants</span>
                    </div>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedScopes.includes("assistant:chat")}
                      onChange={() => toggleScope("assistant:chat")}
                      className="rounded border-slate-700 text-sky-500 focus:ring-sky-500"
                    />
                    <div>
                      <span className="font-mono text-slate-200">assistant:chat</span>
                      <span className="text-[11px] text-slate-400 block">Stream inference responses</span>
                    </div>
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Key Expiration</label>
                <select
                  value={expiresDays ?? "never"}
                  onChange={(e) =>
                    setExpiresDays(e.target.value === "never" ? null : Number(e.target.value))
                  }
                  className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-white focus:border-sky-500 focus:outline-none"
                >
                  <option value={30}>30 Days (Recommended)</option>
                  <option value={60}>60 Days</option>
                  <option value={90}>90 Days</option>
                  <option value="never">No Expiration</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-xl border border-slate-700 px-4 py-2 font-medium text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !keyName.trim()}
                  className="rounded-xl bg-sky-600 px-4 py-2 font-semibold text-white hover:bg-sky-500 disabled:opacity-50 cursor-pointer"
                >
                  {creating ? "Generating..." : "Generate Key"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
