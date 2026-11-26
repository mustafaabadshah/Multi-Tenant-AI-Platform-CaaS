"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  MCPConnectionItem,
  MCPDiscoveredTool,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import {
  AlertCircle,
  CheckCircle2,
  Cpu,
  ExternalLink,
  Eye,
  EyeOff,
  Globe,
  Info,
  Lock,
  Network,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserCheck,
  Wrench,
  X,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";
import Modal from "@/components/ui/Modal";
import ConfirmModal from "@/components/ui/ConfirmModal";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";

export default function IntegrationsPage() {
  const { user, activeWorkspace } = useAuth();

  const [connections, setConnections] = useState<MCPConnectionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Add Connection Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [serverUrl, setServerUrl] = useState("");
  const [authMode, setAuthMode] = useState<"NONE" | "BEARER_TOKEN" | "BASIC_AUTH">("BEARER_TOKEN");
  const [credential, setCredential] = useState("");
  const [isPersonal, setIsPersonal] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [savingConn, setSavingConn] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  // Discovery / Tool Inspector Modal
  const [activeConnForDiscovery, setActiveConnForDiscovery] = useState<MCPConnectionItem | null>(null);
  const [discoveredTools, setDiscoveredTools] = useState<MCPDiscoveredTool[]>([]);
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set());
  const [discovering, setDiscovering] = useState(false);
  const [savingApprovedTools, setSavingApprovedTools] = useState(false);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);

  // Delete Confirm Modal
  const [connToDelete, setConnToDelete] = useState<MCPConnectionItem | null>(null);
  const [deletingConn, setDeletingConn] = useState(false);

  const fetchConnections = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    else setRefreshing(true);
    setErrorMsg(null);
    try {
      const data = await api.listMcpConnections();
      setConnections(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load MCP server connections.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (activeWorkspace) {
      fetchConnections();
    }
  }, [activeWorkspace]);

  const handleAddConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName.trim() || !serverUrl.trim()) {
      setAddError("Display name and server endpoint URL are required.");
      return;
    }

    if (!serverUrl.startsWith("https://") && !serverUrl.startsWith("http://localhost")) {
      setAddError("Endpoint must be a secure HTTPS URL (or http://localhost in local test environments).");
      return;
    }

    setSavingConn(true);
    setAddError(null);
    try {
      await api.createMcpConnection({
        display_name: displayName.trim(),
        server_url: serverUrl.trim(),
        auth_mode: authMode,
        credential: credential.trim() ? credential.trim() : undefined,
        is_personal: isPersonal,
      });

      setShowAddModal(false);
      setDisplayName("");
      setServerUrl("");
      setCredential("");
      setIsPersonal(false);
      await fetchConnections(true);
    } catch (err: any) {
      setAddError(err.message || "Failed to register MCP server.");
    } finally {
      setSavingConn(false);
    }
  };

  const handleOpenDiscovery = async (conn: MCPConnectionItem) => {
    setActiveConnForDiscovery(conn);
    setDiscoveryError(null);
    setDiscovering(true);

    // Initialize selected tools with currently approved tools
    const alreadyApproved = new Set((conn.approved_tools || []).map((t) => t.name));
    setSelectedTools(alreadyApproved);

    try {
      const resp = await api.discoverMcpTools(conn.id);
      setDiscoveredTools(resp.tools || []);
    } catch (err: any) {
      setDiscoveryError(err.message || "Failed to discover tools from remote MCP server.");
      // Fallback to displaying already approved tools if discovery fails
      setDiscoveredTools((conn.approved_tools || []).map((t) => ({
        name: t.name,
        description: t.description,
        input_schema: t.input_schema,
        risk_level: t.risk_level || "READ_ONLY",
      })));
    } finally {
      setDiscovering(false);
    }
  };

  const toggleToolSelection = (toolName: string) => {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      if (next.has(toolName)) {
        next.delete(toolName);
      } else {
        next.add(toolName);
      }
      return next;
    });
  };

  const handleSaveApprovedTools = async () => {
    if (!activeConnForDiscovery) return;
    setSavingApprovedTools(true);
    try {
      const updated = await api.approveMcpTools(
        activeConnForDiscovery.id,
        Array.from(selectedTools)
      );
      setConnections((prev) =>
        prev.map((c) => (c.id === updated.id ? updated : c))
      );
      setActiveConnForDiscovery(null);
    } catch (err: any) {
      setDiscoveryError(err.message || "Failed to update approved tools.");
    } finally {
      setSavingApprovedTools(false);
    }
  };

  const handleDeleteConnection = async () => {
    if (!connToDelete) return;
    setDeletingConn(true);
    try {
      await api.deleteMcpConnection(connToDelete.id);
      setConnections((prev) => prev.filter((c) => c.id !== connToDelete.id));
      setConnToDelete(null);
    } catch (err: any) {
      alert(err.message || "Failed to delete connection.");
    } finally {
      setDeletingConn(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-gray-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 flex items-center gap-2.5">
            <Network className="text-blue-600" size={24} />
            Model Context Protocol (MCP) Connections
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Connect standard MCP tool servers over secure HTTPS/SSE. Discovered tools can be selectively approved for assistant execution.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchConnections(true)}
            disabled={refreshing || loading}
            className="flex items-center gap-2"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              setAddError(null);
              setShowAddModal(true);
            }}
            className="flex items-center gap-2"
          >
            <Plus size={16} />
            Add MCP Server
          </Button>
        </div>
      </div>

      {/* Security Architecture Notice */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-start gap-3">
        <ShieldCheck className="text-emerald-600 shrink-0 mt-0.5" size={18} />
        <div className="text-xs text-slate-700 space-y-1">
          <p className="font-semibold text-slate-900">Zero-Trust Integrations Security Boundary</p>
          <p>
            All remote MCP servers are validated through DNS resolution and private network egress defenses (RFC 1918, RFC 3927, loopback addresses blocked).
            Tokens are stored with AES-256-GCM encryption. Discovered tools require explicit approval before assistants can execute them.
          </p>
        </div>
      </div>

      {/* Error alert */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-center gap-3 text-sm text-rose-800">
          <AlertCircle size={18} className="shrink-0 text-rose-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3 text-gray-400">
          <Spinner size="lg" />
          <p className="text-sm">Querying workspace MCP connections...</p>
        </div>
      ) : connections.length === 0 ? (
        <EmptyState
          icon={Network}
          title="No MCP servers configured"
          description="Register a remote Model Context Protocol endpoint to enable external agentic tools, databases, or API integrations."
          action={{
            label: "Connect First Server",
            onClick: () => setShowAddModal(true),
          }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {connections.map((conn) => {
            const isPersonalConn = !!conn.user_id;
            const isUserOwner = conn.user_id === user?.id;
            const approvedCount = (conn.approved_tools || []).length;

            return (
              <div
                key={conn.id}
                className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:shadow transition-shadow flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <div className="h-9 w-9 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-sm">
                        <Cpu size={18} />
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900 text-sm leading-snug">
                          {conn.display_name}
                        </h3>
                        <p className="text-[11px] text-gray-400 truncate max-w-[200px]" title={conn.server_url}>
                          {conn.server_url}
                        </p>
                      </div>
                    </div>
                    <div>
                      {conn.connection_status === "CONNECTED" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 size={11} /> Connected
                        </span>
                      ) : conn.connection_status === "ERROR" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
                          <AlertCircle size={11} /> Error
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                          Disconnected
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-gray-100 space-y-2 text-xs text-gray-600">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Auth Mode:</span>
                      <span className="font-medium text-gray-800">{conn.auth_mode}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Access Scope:</span>
                      <span>
                        {isPersonalConn ? (
                          <span className="inline-flex items-center gap-1 text-purple-700 font-medium">
                            <Lock size={12} /> Personal Credential
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-slate-700 font-medium">
                            <Globe size={12} /> Workspace-wide
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Approved Tools:</span>
                      <span className="font-medium text-blue-600">{approvedCount} available</span>
                    </div>
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-gray-100 flex items-center justify-between gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 text-xs flex items-center justify-center gap-1.5"
                    onClick={() => handleOpenDiscovery(conn)}
                  >
                    <Wrench size={13} />
                    Manage Tools ({approvedCount})
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-gray-400 hover:text-rose-600 px-2"
                    onClick={() => setConnToDelete(conn)}
                    title="Remove connection"
                  >
                    <Trash2 size={15} />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add MCP Connection Modal */}
      <Modal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="Add MCP Server Connection"
      >
        <form onSubmit={handleAddConnection} className="space-y-4">
          {addError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-start gap-2">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              <span>{addError}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
              Display Name *
            </label>
            <input
              type="text"
              placeholder="e.g., GitHub Workspace MCP, Postgres Tools"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
              Server URL (HTTPS / SSE Endpoint) *
            </label>
            <input
              type="url"
              placeholder="https://mcp.internal.acme.com/sse"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
              required
            />
            <p className="mt-1 text-[11px] text-gray-400">
              Must be accessible over HTTPS. Private RFC 1918 and loopback addresses are blocked by default.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Authentication Mode
              </label>
              <select
                value={authMode}
                onChange={(e) => setAuthMode(e.target.value as any)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="NONE">None / Open</option>
                <option value="BEARER_TOKEN">Bearer Token</option>
                <option value="BASIC_AUTH">Basic Auth</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                OAuth 2.0 (Delegated)
              </label>
              <div className="px-3 py-2 text-xs text-gray-400 border border-dashed border-gray-300 rounded-lg bg-gray-50 flex items-center justify-between">
                <span>RFC Spec Flow</span>
                <span className="text-[10px] bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded font-mono">Coming Soon</span>
              </div>
            </div>
          </div>

          {authMode !== "NONE" && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Credential / Secret Token
                </label>
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
                >
                  {showSecret ? <EyeOff size={12} /> : <Eye size={12} />}
                  <span>{showSecret ? "Hide" : "Show"}</span>
                </button>
              </div>
              <input
                type={showSecret ? "text" : "password"}
                placeholder={authMode === "BASIC_AUTH" ? "username:password" : "mcp_pat_..."}
                value={credential}
                onChange={(e) => setCredential(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
              />
              <p className="mt-1 text-[11px] text-gray-400">
                Write-only: Encrypted using AES-256-GCM. Raw credentials will never be returned to the client.
              </p>
            </div>
          )}

          <div className="pt-2">
            <label className="flex items-start gap-2.5 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 cursor-pointer">
              <input
                type="checkbox"
                checked={isPersonal}
                onChange={(e) => setIsPersonal(e.target.checked)}
                className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
              />
              <div>
                <span className="text-xs font-semibold text-gray-900 block">Personal Credential Scope</span>
                <span className="text-[11px] text-gray-500">
                  If checked, only you can attach this MCP connection to assistants. Workspace-wide tools can be shared across tenant assistants.
                </span>
              </div>
            </label>
          </div>

          <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowAddModal(false)}
              disabled={savingConn}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={savingConn}
              className="flex items-center gap-2"
            >
              {savingConn && <Spinner size="sm" />}
              {savingConn ? "Connecting..." : "Register Server"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Discovery & Tool Approval Drawer / Modal */}
      <Modal
        isOpen={!!activeConnForDiscovery}
        onClose={() => setActiveConnForDiscovery(null)}
        title={`MCP Tools: ${activeConnForDiscovery?.display_name}`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="text-xs text-gray-500">
            Select the tools you authorize for execution by workspace assistants. Unchecked tools will remain disabled.
          </div>

          {discoveryError && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
              <AlertCircle size={14} className="shrink-0 mt-0.5 text-amber-600" />
              <span>{discoveryError}</span>
            </div>
          )}

          {discovering ? (
            <div className="py-12 flex flex-col items-center justify-center gap-2 text-gray-400">
              <Spinner size="md" />
              <p className="text-xs">Querying remote server tools/list endpoint...</p>
            </div>
          ) : discoveredTools.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500">
              No tools returned by this MCP server.
            </div>
          ) : (
            <div className="max-h-96 overflow-y-auto space-y-3 pr-1">
              {discoveredTools.map((tool) => {
                const isChecked = selectedTools.has(tool.name);
                const risk = tool.risk_level || "READ_ONLY";

                return (
                  <div
                    key={tool.name}
                    onClick={() => toggleToolSelection(tool.name)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                      isChecked
                        ? "border-blue-300 bg-blue-50/50"
                        : "border-gray-200 bg-white hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}} // handled by parent div
                          className="mt-1 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
                        />
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-xs text-gray-900 font-mono">
                              {tool.name}
                            </span>
                            {risk === "READ_ONLY" ? (
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-100 text-emerald-800 font-medium">
                                Read Only
                              </span>
                            ) : risk === "WRITE" ? (
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 font-medium">
                                Write Action
                              </span>
                            ) : (
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-rose-100 text-rose-800 font-medium">
                                High Risk
                              </span>
                            )}
                          </div>
                          <p className="mt-1 text-xs text-gray-600">
                            {tool.description || "No description provided by remote server."}
                          </p>

                          {tool.input_schema && (
                            <details className="mt-2 text-[11px] text-gray-500" onClick={(e) => e.stopPropagation()}>
                              <summary className="cursor-pointer hover:text-gray-700 font-mono">
                                View Parameters Schema
                              </summary>
                              <pre className="mt-1 p-2 bg-slate-900 text-slate-100 rounded text-[10px] overflow-x-auto">
                                {JSON.stringify(tool.input_schema, null, 2)}
                              </pre>
                            </details>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
            <span className="text-xs text-gray-500 font-medium">
              {selectedTools.size} of {discoveredTools.length} tools approved
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setActiveConnForDiscovery(null)}
                disabled={savingApprovedTools}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveApprovedTools}
                disabled={savingApprovedTools || discovering}
                className="flex items-center gap-2"
              >
                {savingApprovedTools && <Spinner size="sm" />}
                Save Approvals
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* Delete Confirm Modal */}
      <ConfirmModal
        isOpen={!!connToDelete}
        onClose={() => setConnToDelete(null)}
        onConfirm={handleDeleteConnection}
        title="Remove MCP Connection"
        message={`Are you sure you want to disconnect "${connToDelete?.display_name}"? Assistants currently configured with its tools will no longer be able to execute them.`}
        confirmText="Disconnect Server"
        variant="danger"
        isLoading={deletingConn}
      />
    </div>
  );
}
