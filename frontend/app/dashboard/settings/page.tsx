"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, TenantUsageSummaryItem } from "@/lib/api";
import { Server, Cpu, HardDrive, Key, Sliders, ExternalLink, AlertTriangle, RefreshCw } from "lucide-react";
import DeveloperApiKeysSection from "./DeveloperApiKeysSection";
import Badge from "@/components/ui/Badge";
import Spinner from "@/components/ui/Spinner";

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://mmaip-backend.onrender.com";

export default function SettingsPage() {
  const { activeWorkspace } = useAuth();
  const [activeTab, setActiveTab] = useState<"infrastructure" | "developer">("infrastructure");
  const [usage, setUsage] = useState<TenantUsageSummaryItem | null>(null);
  const [loadingUsage, setLoadingUsage] = useState<boolean>(true);

  useEffect(() => {
    async function loadUsage() {
      try {
        setLoadingUsage(true);
        const data = await api.getTenantUsageSummary();
        setUsage(data);
      } catch (err) {
        console.error("Failed to load quota usage", err);
      } finally {
        setLoadingUsage(false);
      }
    }
    loadUsage();
  }, [activeWorkspace?.tenant_id]);

  const tokenPct = usage && usage.monthly_tokens_limit > 0
    ? Math.min(100, Math.max(0, (usage.monthly_tokens_used / usage.monthly_tokens_limit) * 100))
    : 0;

  const requestPct = usage && usage.daily_request_limit > 0
    ? Math.min(100, Math.max(0, (usage.today_requests / usage.daily_request_limit) * 100))
    : 0;

  const storagePct = usage && usage.storage_bytes_limit > 0
    ? Math.min(100, Math.max(0, (usage.storage_bytes_used / usage.storage_bytes_limit) * 100))
    : 0;

  const docPct = usage && usage.document_limit > 0
    ? Math.min(100, Math.max(0, (usage.document_count / usage.document_limit) * 100))
    : 0;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Workspace Settings</h1>
        <p className="text-sm text-gray-600 mt-1">
          Infrastructure parameters, active limits, developer keys, and AI Gateway configurations.
        </p>
      </div>

      {/* Settings Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-gray-200 text-xs">
        <button
          type="button"
          onClick={() => setActiveTab("infrastructure")}
          className={`py-2.5 px-3 font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === "infrastructure"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-900"
          }`}
        >
          <Sliders size={14} />
          <span>Infrastructure & Quotas</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("developer")}
          className={`py-2.5 px-3 font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === "developer"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-900"
          }`}
        >
          <Key size={14} />
          <span>Developer API Keys</span>
        </button>
      </div>

      {activeTab === "developer" ? (
        <DeveloperApiKeysSection />
      ) : (
        <div className="space-y-6">
          {/* Quotas & Capacity */}
          <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-xs space-y-5">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider flex items-center gap-2">
              <HardDrive size={16} className="text-blue-600" />
              <span>Tenant Quotas & Usage Capacity</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 font-medium">Monthly Tokens</span>
                  <span className="font-mono text-gray-700 font-semibold">{tokenPct.toFixed(1)}%</span>
                </div>
                <div className="text-base font-bold text-gray-900">
                  {loadingUsage ? "Loading..." : `${usage ? usage.monthly_tokens_used.toLocaleString() : 0} / ${usage && usage.monthly_tokens_limit > 0 ? usage.monthly_tokens_limit.toLocaleString() : "Unlimited"}`}
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-1.5 rounded-full ${tokenPct > 90 ? "bg-red-500" : tokenPct > 70 ? "bg-amber-500" : "bg-blue-600"}`}
                    style={{ width: `${tokenPct}%` }}
                  />
                </div>
                <span className="text-[11px] text-gray-400 block">OmniRoute LLM inference budget</span>
              </div>

              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 font-medium">Daily Requests</span>
                  <span className="font-mono text-gray-700 font-semibold">{requestPct.toFixed(1)}%</span>
                </div>
                <div className="text-base font-bold text-gray-900">
                  {loadingUsage ? "Loading..." : `${usage ? usage.today_requests.toLocaleString() : 0} / ${usage && usage.daily_request_limit > 0 ? usage.daily_request_limit.toLocaleString() : "Unlimited"}`}
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-1.5 rounded-full ${requestPct > 90 ? "bg-red-500" : requestPct > 70 ? "bg-amber-500" : "bg-emerald-600"}`}
                    style={{ width: `${requestPct}%` }}
                  />
                </div>
                <span className="text-[11px] text-gray-400 block">Daily API call consumption</span>
              </div>

              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 font-medium">Storage Budget</span>
                  <span className="font-mono text-gray-700 font-semibold">{storagePct.toFixed(1)}%</span>
                </div>
                <div className="text-base font-bold text-gray-900">
                  {loadingUsage ? "Loading..." : `${usage ? formatBytes(usage.storage_bytes_used) : "0 B"} / ${usage && usage.storage_bytes_limit > 0 ? formatBytes(usage.storage_bytes_limit) : "Unlimited"}`}
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-1.5 rounded-full ${storagePct > 90 ? "bg-red-500" : storagePct > 70 ? "bg-amber-500" : "bg-purple-600"}`}
                    style={{ width: `${storagePct}%` }}
                  />
                </div>
                <span className="text-[11px] text-gray-400 block">Document chunk & OCR raw file allocation</span>
              </div>

              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 font-medium">Knowledge Base Documents</span>
                  <span className="font-mono text-gray-700 font-semibold">{docPct.toFixed(1)}%</span>
                </div>
                <div className="text-base font-bold text-gray-900">
                  {loadingUsage ? "Loading..." : `${usage ? usage.document_count.toLocaleString() : 0} / ${usage && usage.document_limit > 0 ? usage.document_limit.toLocaleString() : "Unlimited"}`}
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-1.5 rounded-full ${docPct > 90 ? "bg-red-500" : docPct > 70 ? "bg-amber-500" : "bg-indigo-600"}`}
                    style={{ width: `${docPct}%` }}
                  />
                </div>
                <span className="text-[11px] text-gray-400 block">Processed corpus files in workspace</span>
              </div>
            </div>

            {usage?.reset_date && (
              <div className="text-xs text-gray-500 flex items-center justify-between pt-2 border-t border-gray-100">
                <span>Billing Cycle Renewal:</span>
                <span className="font-mono text-gray-700 font-medium">{new Date(usage.reset_date).toLocaleDateString()}</span>
              </div>
            )}
          </div>

          {/* AI Gateway Connection (OmniRoute) */}
          <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-xs space-y-4">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider flex items-center gap-2">
              <Cpu size={16} className="text-purple-600" />
              <span>OmniRoute AI Gateway Integration</span>
            </h2>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-200">
                <div>
                  <span className="font-semibold text-gray-900 block">Gateway Base URL</span>
                  <span className="text-[11px] text-gray-500 font-mono">http://localhost:20128/v1</span>
                </div>
                <Badge variant="green" size="xs">
                  Active / Local
                </Badge>
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-200">
                <div>
                  <span className="font-semibold text-gray-900 block">Default Model Routing</span>
                  <span className="text-[11px] text-gray-500 font-mono">model="auto" (Dynamic Fallback)</span>
                </div>
                <Badge variant="blue" size="xs">
                  Configured
                </Badge>
              </div>
            </div>
          </div>

          {/* Backend Transport Details */}
          <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-xs space-y-4">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider flex items-center gap-2">
              <Server size={16} className="text-emerald-600" />
              <span>System Transport Configuration</span>
            </h2>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 flex justify-between items-center">
                <span className="text-gray-600">Backend API URL</span>
                <span className="font-mono text-gray-900">{API_BASE}</span>
              </div>
              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 flex justify-between items-center">
                <span className="text-gray-600">Interactive OpenAPI Docs</span>
                <a
                  href={`${API_BASE}/docs`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 hover:text-blue-700 font-mono flex items-center gap-1"
                >
                  <span>{API_BASE}/docs</span>
                  <ExternalLink size={12} />
                </a>
              </div>
              <div className="p-3 rounded-lg bg-gray-50 border border-gray-200 flex justify-between items-center">
                <span className="text-gray-600">Health Endpoint</span>
                <a
                  href={`${API_BASE}/health`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-emerald-600 hover:text-emerald-700 font-mono flex items-center gap-1"
                >
                  <span>{API_BASE}/health</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
