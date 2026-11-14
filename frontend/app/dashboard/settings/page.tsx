"use client";

import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { API_BASE } from "@/lib/api";
import { Server, Cpu, HardDrive, Key, Sliders, ExternalLink } from "lucide-react";
import DeveloperApiKeysSection from "./DeveloperApiKeysSection";
import Badge from "@/components/ui/Badge";

export default function SettingsPage() {
  const { activeWorkspace } = useAuth();
  const [activeTab, setActiveTab] = useState<"infrastructure" | "developer">("infrastructure");

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
              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="text-gray-500 font-medium">User Seats</span>
                <div className="text-lg font-bold text-gray-900">
                  {activeWorkspace?.tenant_type === "ORGANIZATION" ? "50 Seats" : "1 Seat"}
                </div>
                <span className="text-[11px] text-gray-400">Maximum members in active workspace</span>
              </div>

              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="text-gray-500 font-medium">Assistant Capacity</span>
                <div className="text-lg font-bold text-gray-900">
                  {activeWorkspace?.tenant_type === "ORGANIZATION" ? "10 Assistants" : "3 Assistants"}
                </div>
                <span className="text-[11px] text-gray-400">Concurrent active AI personas</span>
              </div>

              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="text-gray-500 font-medium">Storage Budget</span>
                <div className="text-lg font-bold text-gray-900">10.0 GB</div>
                <span className="text-[11px] text-gray-400">Document chunk & OCR raw file allocation</span>
              </div>

              <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-1">
                <span className="text-gray-500 font-medium">Monthly Token Quota</span>
                <div className="text-lg font-bold text-gray-900">10,000,000 Tokens</div>
                <span className="text-[11px] text-gray-400">OmniRoute LLM inference budget</span>
              </div>
            </div>
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
