"use client";

import React, { useEffect, useState } from "react";
import {
  api,
  ToolItem,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Code2,
  Cpu,
  ExternalLink,
  Flame,
  Globe,
  Layers,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Trash2,
  Wrench,
  X,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";
import Modal from "@/components/ui/Modal";
import ConfirmModal from "@/components/ui/ConfirmModal";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";

export default function ToolsWorkspacePage() {
  const { user, activeWorkspace } = useAuth();

  const [tools, setTools] = useState<ToolItem[]>([]);
  const [activeTab, setActiveTab] = useState<"ALL" | "BUILTIN" | "CUSTOM_HTTP" | "MCP">("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Create Tool Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [toolName, setToolName] = useState("");
  const [toolDisplayName, setToolDisplayName] = useState("");
  const [toolDescription, setToolDescription] = useState("");
  const [toolEndpointUrl, setToolEndpointUrl] = useState("");
  const [toolMethod, setToolMethod] = useState<"GET" | "POST" | "PUT" | "DELETE">("POST");
  const [toolHeadersStr, setToolHeadersStr] = useState("{\n  \"Content-Type\": \"application/json\"\n}");
  const [toolInputSchemaStr, setToolInputSchemaStr] = useState(
    "{\n  \"type\": \"object\",\n  \"properties\": {\n    \"query\": { \"type\": \"string\" }\n  },\n  \"required\": [\"query\"]\n}"
  );
  const [toolRiskLevel, setToolRiskLevel] = useState<"READ_ONLY" | "WRITE" | "HIGH_RISK">("READ_ONLY");
  const [toolRequiresApproval, setToolRequiresApproval] = useState(false);
  const [toolTimeout, setToolTimeout] = useState(10);
  const [savingTool, setSavingTool] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Test Tool Dialog
  const [activeToolForTest, setActiveToolForTest] = useState<ToolItem | null>(null);
  const [testArgsStr, setTestArgsStr] = useState("{\n  \"query\": \"example test\"\n}");
  const [testingTool, setTestingTool] = useState(false);
  const [testResult, setTestResult] = useState<{ status_code: number; is_success: boolean; data: any; duration_ms?: number } | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  // Delete Confirm Modal
  const [toolToDelete, setToolToDelete] = useState<ToolItem | null>(null);
  const [deletingTool, setDeletingTool] = useState(false);

  const fetchTools = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    else setRefreshing(true);
    setErrorMsg(null);
    try {
      const data = await api.listTools();
      setTools(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load tool registry.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (activeWorkspace) {
      fetchTools();
    }
  }, [activeWorkspace]);

  const handleCreateTool = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    // Validate technical name format
    if (!/^[a-zA-Z0-9_-]{1,64}$/.test(toolName.trim())) {
      setCreateError("Tool name must be alphanumeric with underscores or dashes (1-64 characters).");
      return;
    }

    if (!toolEndpointUrl.startsWith("https://") && !toolEndpointUrl.startsWith("http://localhost")) {
      setCreateError("Endpoint URL must be a valid HTTPS address.");
      return;
    }

    let parsedHeaders = {};
    if (toolHeadersStr.trim()) {
      try {
        parsedHeaders = JSON.parse(toolHeadersStr);
      } catch {
        setCreateError("Headers must be a valid JSON object.");
        return;
      }
    }

    let parsedSchema = {};
    if (toolInputSchemaStr.trim()) {
      try {
        parsedSchema = JSON.parse(toolInputSchemaStr);
      } catch {
        setCreateError("Input schema must be a valid JSON Schema object.");
        return;
      }
    }

    setSavingTool(true);
    try {
      await api.createTool({
        name: toolName.trim(),
        display_name: toolDisplayName.trim() || toolName.trim(),
        description: toolDescription.trim() || undefined,
        endpoint_url: toolEndpointUrl.trim(),
        method: toolMethod,
        headers: parsedHeaders,
        input_schema: parsedSchema,
        risk_level: toolRiskLevel,
        requires_approval: toolRequiresApproval,
        timeout_seconds: toolTimeout,
      });

      setShowCreateModal(false);
      setToolName("");
      setToolDisplayName("");
      setToolDescription("");
      setToolEndpointUrl("");
      setToolMethod("POST");
      setToolHeadersStr("{\n  \"Content-Type\": \"application/json\"\n}");
      setToolInputSchemaStr("{\n  \"type\": \"object\",\n  \"properties\": {\n    \"query\": { \"type\": \"string\" }\n  },\n  \"required\": [\"query\"]\n}");
      setToolRiskLevel("READ_ONLY");
      setToolRequiresApproval(false);
      setToolTimeout(10);
      await fetchTools(true);
    } catch (err: any) {
      setCreateError(err.message || "Failed to create tool.");
    } finally {
      setSavingTool(false);
    }
  };

  const handleOpenTestModal = (tool: ToolItem) => {
    setActiveToolForTest(tool);
    setTestResult(null);
    setTestError(null);

    // Populate sample payload based on input_schema
    if (tool.input_schema && tool.input_schema.properties) {
      const sample: Record<string, any> = {};
      for (const [key, prop] of Object.entries<any>(tool.input_schema.properties)) {
        if (prop.type === "string") sample[key] = "test_value";
        else if (prop.type === "number" || prop.type === "integer") sample[key] = 1;
        else if (prop.type === "boolean") sample[key] = true;
        else sample[key] = null;
      }
      setTestArgsStr(JSON.stringify(sample, null, 2));
    } else {
      setTestArgsStr("{\n  \"query\": \"test\"\n}");
    }
  };

  const handleExecuteTest = async () => {
    if (!activeToolForTest) return;
    setTestingTool(true);
    setTestError(null);
    setTestResult(null);

    let parsedArgs = {};
    try {
      parsedArgs = JSON.parse(testArgsStr);
    } catch {
      setTestError("Arguments must be valid JSON.");
      setTestingTool(false);
      return;
    }

    const t0 = performance.now();
    try {
      const res = await api.executeTool(activeToolForTest.id, parsedArgs);
      const durationMs = Math.round(performance.now() - t0);
      setTestResult({
        ...res,
        duration_ms: durationMs,
      });
    } catch (err: any) {
      setTestError(err.message || "Tool execution failed.");
    } finally {
      setTestingTool(false);
    }
  };

  const handleDeleteTool = async () => {
    if (!toolToDelete) return;
    setDeletingTool(true);
    try {
      await api.deleteTool(toolToDelete.id);
      setTools((prev) => prev.filter((t) => t.id !== toolToDelete.id));
      setToolToDelete(null);
    } catch (err: any) {
      alert(err.message || "Failed to delete tool.");
    } finally {
      setDeletingTool(false);
    }
  };

  const filteredTools = tools.filter((t) => {
    if (activeTab === "BUILTIN" && t.tool_type !== "BUILTIN") return false;
    if (activeTab === "CUSTOM_HTTP" && t.tool_type !== "CUSTOM_HTTP") return false;
    if (activeTab === "MCP" && t.tool_type !== "MCP") return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = t.name.toLowerCase().includes(q);
      const matchDisplay = (t.display_name || "").toLowerCase().includes(q);
      const matchDesc = (t.description || "").toLowerCase().includes(q);
      return matchName || matchDisplay || matchDesc;
    }
    return true;
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-gray-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 flex items-center gap-2.5">
            <Wrench className="text-blue-600" size={24} />
            Tool Registry & Capabilities
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Configure agentic tools for assistants: Built-in capabilities, custom outbound HTTP webhooks, and Model Context Protocol actions.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchTools(true)}
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
              setCreateError(null);
              setShowCreateModal(true);
            }}
            className="flex items-center gap-2"
          >
            <Plus size={16} />
            New Custom Tool
          </Button>
        </div>
      </div>

      {/* Tabs & Search Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab("ALL")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "ALL"
                ? "bg-white text-gray-900 shadow-sm font-semibold"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            All Tools ({tools.length})
          </button>
          <button
            onClick={() => setActiveTab("BUILTIN")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "BUILTIN"
                ? "bg-white text-gray-900 shadow-sm font-semibold"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Built-in ({tools.filter((t) => t.tool_type === "BUILTIN").length})
          </button>
          <button
            onClick={() => setActiveTab("CUSTOM_HTTP")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "CUSTOM_HTTP"
                ? "bg-white text-gray-900 shadow-sm font-semibold"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Custom HTTP ({tools.filter((t) => t.tool_type === "CUSTOM_HTTP").length})
          </button>
          <button
            onClick={() => setActiveTab("MCP")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === "MCP"
                ? "bg-white text-gray-900 shadow-sm font-semibold"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            MCP Protocol ({tools.filter((t) => t.tool_type === "MCP").length})
          </button>
        </div>

        <div className="relative w-full sm:w-64">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search tools by name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Error Banner */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-center gap-3 text-sm text-rose-800">
          <AlertCircle size={18} className="shrink-0 text-rose-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tools List */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center gap-3 text-gray-400">
          <Spinner size="lg" />
          <p className="text-sm">Loading tools and capabilities...</p>
        </div>
      ) : filteredTools.length === 0 ? (
        <EmptyState
          icon={Wrench}
          title="No tools match this filter"
          description="Create a custom outbound HTTP tool or connect an MCP server to equip your AI assistants with actionable tools."
          action={{
            label: "Create Tool",
            onClick: () => setShowCreateModal(true),
          }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTools.map((tool) => {
            const isBuiltin = tool.tool_type === "BUILTIN";
            const isMcp = tool.tool_type === "MCP";
            const risk = tool.risk_level || "READ_ONLY";

            return (
              <div
                key={tool.id}
                className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:shadow transition-shadow flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <div className={`h-9 w-9 rounded-lg flex items-center justify-center font-bold text-sm ${
                        isBuiltin
                          ? "bg-purple-50 text-purple-600"
                          : isMcp
                          ? "bg-blue-50 text-blue-600"
                          : "bg-emerald-50 text-emerald-600"
                      }`}>
                        {isBuiltin ? <Terminal size={18} /> : isMcp ? <Cpu size={18} /> : <Globe size={18} />}
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900 text-sm leading-snug">
                          {tool.display_name || tool.name}
                        </h3>
                        <p className="text-[11px] font-mono text-gray-400">
                          {tool.name}
                        </p>
                      </div>
                    </div>

                    <div>
                      {tool.tool_type === "BUILTIN" ? (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 font-medium border border-purple-200">
                          Built-in
                        </span>
                      ) : tool.tool_type === "MCP" ? (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium border border-blue-200">
                          MCP Tool
                        </span>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium border border-emerald-200">
                          Custom HTTP
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="mt-3 text-xs text-gray-600 line-clamp-2">
                    {tool.description || "No description provided."}
                  </p>

                  <div className="mt-4 pt-3 border-t border-gray-100 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Risk Profile:</span>
                      {risk === "READ_ONLY" ? (
                        <span className="text-[11px] font-medium text-emerald-700 flex items-center gap-1">
                          <ShieldCheck size={12} /> Read-only
                        </span>
                      ) : risk === "WRITE" ? (
                        <span className="text-[11px] font-medium text-amber-700 flex items-center gap-1">
                          <Flame size={12} /> Mutating Action
                        </span>
                      ) : (
                        <span className="text-[11px] font-medium text-rose-700 flex items-center gap-1">
                          <ShieldAlert size={12} /> High Risk
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Human Approval:</span>
                      <span className={`text-[11px] font-medium ${tool.requires_approval ? "text-purple-700" : "text-gray-500"}`}>
                        {tool.requires_approval ? "Mandatory" : "Automatic"}
                      </span>
                    </div>

                    {tool.http_config?.endpoint_url && (
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-gray-400">Endpoint:</span>
                        <span className="font-mono text-gray-600 truncate max-w-[170px]" title={tool.http_config.endpoint_url}>
                          {tool.http_config.method} {tool.http_config.endpoint_url}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-gray-100 flex items-center justify-between gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 text-xs flex items-center justify-center gap-1.5"
                    onClick={() => handleOpenTestModal(tool)}
                  >
                    <Play size={12} />
                    Test Execution
                  </Button>
                  {!isBuiltin && !isMcp && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-gray-400 hover:text-rose-600 px-2"
                      onClick={() => setToolToDelete(tool)}
                      title="Delete tool"
                    >
                      <Trash2 size={15} />
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* New Custom Tool Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create Custom HTTP Tool"
        maxWidth="lg"
      >
        <form onSubmit={handleCreateTool} className="space-y-4">
          {createError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-start gap-2">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              <span>{createError}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Technical Name (snake_case) *
              </label>
              <input
                type="text"
                placeholder="e.g. order_lookup"
                value={toolName}
                onChange={(e) => setToolName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Display Name *
              </label>
              <input
                type="text"
                placeholder="e.g. Order Status Lookup"
                value={toolDisplayName}
                onChange={(e) => setToolDisplayName(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
              Description (LLM Context Prompt) *
            </label>
            <textarea
              rows={2}
              placeholder="Explain what this tool does and when the assistant should invoke it..."
              value={toolDescription}
              onChange={(e) => setToolDescription(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1">
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                HTTP Method
              </label>
              <select
                value={toolMethod}
                onChange={(e) => setToolMethod(e.target.value as any)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="DELETE">DELETE</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Endpoint URL (HTTPS) *
              </label>
              <input
                type="url"
                placeholder="https://api.acme.com/orders"
                value={toolEndpointUrl}
                onChange={(e) => setToolEndpointUrl(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
              Headers (JSON object)
            </label>
            <textarea
              rows={3}
              value={toolHeadersStr}
              onChange={(e) => setToolHeadersStr(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
              Input Schema (JSON Schema format) *
            </label>
            <textarea
              rows={5}
              value={toolInputSchemaStr}
              onChange={(e) => setToolInputSchemaStr(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4 pt-1">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Risk Classification
              </label>
              <select
                value={toolRiskLevel}
                onChange={(e) => setToolRiskLevel(e.target.value as any)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="READ_ONLY">Read-Only (Safe queries)</option>
                <option value="WRITE">Write / Mutating Action</option>
                <option value="HIGH_RISK">High Risk (Financial/Destructive)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Timeout (Seconds)
              </label>
              <input
                type="number"
                min={1}
                max={60}
                value={toolTimeout}
                onChange={(e) => setToolTimeout(parseInt(e.target.value) || 10)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="pt-2">
            <label className="flex items-start gap-2.5 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 cursor-pointer">
              <input
                type="checkbox"
                checked={toolRequiresApproval}
                onChange={(e) => setToolRequiresApproval(e.target.checked)}
                className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
              />
              <div>
                <span className="text-xs font-semibold text-gray-900 block">Require Human-in-the-Loop Approval</span>
                <span className="text-[11px] text-gray-500">
                  When enabled, assistant runs pause execution and present an inline approval prompt in the conversation chat before executing this tool.
                </span>
              </div>
            </label>
          </div>

          <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowCreateModal(false)}
              disabled={savingTool}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={savingTool}
              className="flex items-center gap-2"
            >
              {savingTool && <Spinner size="sm" />}
              {savingTool ? "Registering..." : "Create Tool"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Test Execution Dialog */}
      <Modal
        isOpen={!!activeToolForTest}
        onClose={() => setActiveToolForTest(null)}
        title={`Test Tool: ${activeToolForTest?.display_name || activeToolForTest?.name}`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="text-xs text-gray-500 flex items-center justify-between">
            <span>Execute this tool with bounded parameters to test connectivity and output schema.</span>
            {activeToolForTest?.risk_level && (
              <span className="font-mono text-[10px] uppercase font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                {activeToolForTest.risk_level}
              </span>
            )}
          </div>

          {testError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-start gap-2">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              <span>{testError}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
              Invocation Arguments (JSON)
            </label>
            <textarea
              rows={4}
              value={testArgsStr}
              onChange={(e) => setTestArgsStr(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            />
          </div>

          {testResult && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-gray-700">Execution Response</span>
                <div className="flex items-center gap-2">
                  <span className="text-gray-400 font-mono text-[11px]">
                    Latency: {testResult.duration_ms}ms
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    testResult.is_success
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-rose-100 text-rose-800"
                  }`}>
                    HTTP {testResult.status_code}
                  </span>
                </div>
              </div>
              <pre className="p-3 bg-slate-900 text-slate-100 rounded-lg text-xs overflow-x-auto max-h-56">
                {JSON.stringify(testResult.data, null, 2)}
              </pre>
            </div>
          )}

          <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setActiveToolForTest(null)}
              disabled={testingTool}
            >
              Close
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleExecuteTest}
              disabled={testingTool}
              className="flex items-center gap-2"
            >
              {testingTool && <Spinner size="sm" />}
              {testingTool ? "Executing..." : "Run Test"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirm Modal */}
      <ConfirmModal
        isOpen={!!toolToDelete}
        onClose={() => setToolToDelete(null)}
        onConfirm={handleDeleteTool}
        title="Delete Custom Tool"
        message={`Are you sure you want to remove "${toolToDelete?.display_name || toolToDelete?.name}"? Assistants configured with this tool will fail to execute it.`}
        confirmText="Delete Tool"
        variant="danger"
        isLoading={deletingTool}
      />
    </div>
  );
}
