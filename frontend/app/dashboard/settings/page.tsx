"use client";

import React from "react";
import { useAuth } from "@/lib/auth-context";
import { API_BASE } from "@/lib/api";
import { Server, Cpu, HardDrive } from "lucide-react";

export default function SettingsPage() {
  const { activeWorkspace } = useAuth();

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-white tracking-tight">Workspace Settings & Quotas</h1>
        <p className="text-xs text-slate-400 mt-1">
          Infrastructure parameters, active limits, and AI Gateway configurations.
        </p>
      </div>

      {/* Quotas & Capacity */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-xl space-y-5">
        <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-blue-400" />
          <span>Tenant Quotas & Usage Capacity</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-400">User Seats</span>
            <div className="text-lg font-bold text-white">
              {activeWorkspace?.tenant_type === "ORGANIZATION" ? "50 Seats" : "1 Seat"}
            </div>
            <span className="text-[10px] text-slate-500">Maximum members in active workspace</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-400">Assistant Capacity</span>
            <div className="text-lg font-bold text-white">
              {activeWorkspace?.tenant_type === "ORGANIZATION" ? "10 Assistants" : "3 Assistants"}
            </div>
            <span className="text-[10px] text-slate-500">Concurrent active AI personas</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-400">Storage Budget</span>
            <div className="text-lg font-bold text-white">10.0 GB</div>
            <span className="text-[10px] text-slate-500">Document chunk & OCR raw file allocation</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
            <span className="text-slate-400">Monthly Token Quota</span>
            <div className="text-lg font-bold text-white">10,000,000 Tokens</div>
            <span className="text-[10px] text-slate-500">OmniRoute LLM inference budget</span>
          </div>
        </div>
      </div>

      {/* AI Gateway Connection (OmniRoute) */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-xl space-y-4">
        <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Cpu className="w-4 h-4 text-purple-400" />
          <span>OmniRoute AI Gateway Integration</span>
        </h2>

        <div className="space-y-3 text-xs">
          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800">
            <div>
              <span className="font-semibold text-slate-200 block">Gateway Base URL</span>
              <span className="text-[11px] text-slate-400 font-mono">http://localhost:20128/v1</span>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
              Active / Local
            </span>
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800">
            <div>
              <span className="font-semibold text-slate-200 block">Default Model Routing</span>
              <span className="text-[11px] text-slate-400 font-mono">model="auto" (Dynamic Fallback)</span>
            </div>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-950 text-blue-400 border border-blue-800">
              Configured
            </span>
          </div>
        </div>
      </div>

      {/* Backend Transport Details */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-xl space-y-4">
        <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Server className="w-4 h-4 text-emerald-400" />
          <span>System Transport Configuration</span>
        </h2>

        <div className="space-y-3 text-xs">
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
            <span className="text-slate-400">Backend API URL</span>
            <span className="font-mono text-slate-200">{API_BASE}</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
            <span className="text-slate-400">Interactive OpenAPI Docs</span>
            <a
              href={`${API_BASE}/docs`}
              target="_blank"
              rel="noreferrer"
              className="text-blue-400 hover:text-blue-300 font-mono"
            >
              {API_BASE}/docs &rarr;
            </a>
          </div>
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
            <span className="text-slate-400">Health Endpoint</span>
            <a
              href={`${API_BASE}/health`}
              target="_blank"
              rel="noreferrer"
              className="text-emerald-400 hover:text-emerald-300 font-mono"
            >
              {API_BASE}/health
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
