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
  Shield,
  Terminal,
  Clock,
  CheckCircle2,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Modal from "@/components/ui/Modal";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import Spinner from "@/components/ui/Spinner";

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
      loadKeys();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Key generation failed";
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

  const handleRevokeKey = async (keyId: string, name: string) => {
    if (
      !confirm(
        `Are you sure you want to revoke API key "${name}"? Any external services using this key will be disconnected immediately.`
      )
    ) {
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
    <div className="space-y-6">
      {/* Newly Created Secret Modal Alert */}
      {newlyCreatedKey && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-5 shadow-sm animate-fadeIn">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
              <AlertTriangle size={18} />
            </div>
            <div className="flex-1 space-y-2">
              <h3 className="text-sm font-semibold text-amber-900">
                Save Your Secret API Key Now
              </h3>
              <p className="text-xs leading-relaxed text-amber-800">
                This secret token will <strong className="font-semibold text-gray-900">never be displayed again</strong>.
                Store it in your environment variables or a secure secret manager.
              </p>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="text"
                  readOnly
                  value={newlyCreatedKey}
                  className="w-full rounded-lg border border-amber-300 bg-white px-3 py-1.5 font-mono text-xs text-gray-900 outline-none"
                />
                <Button
                  variant="primary"
                  size="xs"
                  onClick={copySecret}
                  className="shrink-0"
                >
                  {copiedRawKey ? (
                    <>
                      <Check size={14} className="mr-1" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy size={14} className="mr-1" />
                      <span>Copy</span>
                    </>
                  )}
                </Button>
                <Button
                  variant="secondary"
                  size="xs"
                  onClick={() => setNewlyCreatedKey(null)}
                  className="shrink-0"
                >
                  Done
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Header & Create Trigger */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <Key size={18} className="text-blue-600" />
            <span>Developer API Keys</span>
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Cryptographically signed bearer tokens for server-to-server and SDK integration.
          </p>
        </div>
        <Button
          variant="primary"
          size="sm"
          icon={Plus}
          onClick={() => setShowCreateModal(true)}
        >
          Create Key
        </Button>
      </div>

      {/* Keys Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-xs">
        {loading ? (
          <div className="p-12 flex items-center justify-center">
            <Spinner size="lg" />
          </div>
        ) : keys.length === 0 ? (
          <EmptyState
            icon={Key}
            title="No API keys configured"
            description="Generate a developer API key to programmatically query assistants via TypeScript or Python SDKs."
            action={{
              label: "Create First API Key",
              onClick: () => setShowCreateModal(true),
              icon: Plus,
            }}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Name</th>
                  <th className="py-3 px-4">Key Prefix</th>
                  <th className="py-3 px-4">Scopes</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4">Expires</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {keys.map((k) => (
                  <tr key={k.id} className="hover:bg-gray-50/60 transition-colors">
                    <td className="py-3 px-4 font-semibold text-gray-900">{k.name}</td>
                    <td className="py-3 px-4 font-mono text-gray-600 text-[11px]">
                      {k.key_prefix}...
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1">
                        {k.scopes.map((s) => (
                          <Badge key={s} variant="blue" size="xs">
                            {s}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-gray-500 font-mono text-[11px]">
                      {new Date(k.created_at).toLocaleDateString([], {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </td>
                    <td className="py-3 px-4 text-gray-500 font-mono text-[11px]">
                      {k.expires_at ? (
                        new Date(k.expires_at).toLocaleDateString([], {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })
                      ) : (
                        <span className="text-gray-400">Never</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleRevokeKey(k.id, k.name)}
                        className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-gray-100 transition-colors"
                        title="Revoke key"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create API Key Modal */}
      {showCreateModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowCreateModal(false)}
          title="Create Developer API Key"
          description="Generate a secure API key with fine-grained capability scopes."
          maxWidth="md"
        >
          <form onSubmit={handleCreateKey} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Key Identifier Name *
              </label>
              <Input
                type="text"
                required
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="e.g. Production Backend Service or Mobile Client"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Authorization Scopes
              </label>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  { scope: "assistant:read", label: "Read Assistants" },
                  { scope: "assistant:chat", label: "Execute Chat" },
                  { scope: "knowledge:read", label: "Read Knowledge" },
                  { scope: "knowledge:search", label: "Retrieval Search" },
                ].map(({ scope, label }) => {
                  const isChecked = selectedScopes.includes(scope);
                  return (
                    <button
                      key={scope}
                      type="button"
                      onClick={() => toggleScope(scope)}
                      className={`p-2 rounded-lg border text-left transition-colors cursor-pointer flex items-center justify-between ${
                        isChecked
                          ? "border-blue-600 bg-blue-50 text-blue-700 font-medium"
                          : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                      }`}
                    >
                      <span className="truncate">{label}</span>
                      {isChecked && <Check size={14} className="text-blue-600 shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Expiration Lifespan
              </label>
              <select
                value={expiresDays === null ? "null" : expiresDays}
                onChange={(e) =>
                  setExpiresDays(e.target.value === "null" ? null : parseInt(e.target.value, 10))
                }
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="30">30 Days</option>
                <option value="90">90 Days</option>
                <option value="365">1 Year</option>
                <option value="null">No Expiration</option>
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-gray-100">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setShowCreateModal(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={creating}
              >
                Generate Key
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
