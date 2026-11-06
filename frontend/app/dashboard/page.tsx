"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api, AuditLogItem } from "@/lib/api";
import {
  Users,
  Briefcase,
  Bot,
  Database,
  ShieldCheck,
  History,
  ArrowRight,
  PlusCircle,
  Building2,
  Sparkles,
} from "lucide-react";

export default function DashboardOverviewPage() {
  const { activeWorkspace } = useAuth();
  const [employeeCount, setEmployeeCount] = useState<number | null>(null);
  const [departmentCount, setDepartmentCount] = useState<number | null>(null);
  const [assistantCount, setAssistantCount] = useState<number | null>(null);
  const [knowledgeCount, setKnowledgeCount] = useState<number | null>(null);
  const [recentAudit, setRecentAudit] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      if (!activeWorkspace) return;
      setLoading(true);
      try {
        const [members, depts, assistants, knowledge, auditLogs] = await Promise.allSettled([
          api.listMembers(),
          api.listDepartments(),
          api.listAssistants(),
          api.listKnowledgeBases(),
          api.listAuditLogs(),
        ]);

        if (members.status === "fulfilled") setEmployeeCount(members.value.length);
        if (depts.status === "fulfilled") setDepartmentCount(depts.value.length);
        if (assistants.status === "fulfilled") setAssistantCount(assistants.value.length);
        if (knowledge.status === "fulfilled") setKnowledgeCount(knowledge.value.length);
        if (auditLogs.status === "fulfilled") setRecentAudit(auditLogs.value.slice(0, 5));
      } catch {
        // Handled via allSettled
      } finally {
        setLoading(false);
      }
    }

    loadStats();
  }, [activeWorkspace]);

  return (
    <div className="space-y-8 max-w-6xl">
      {/* Welcome & Workspace Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-blue-900/40 via-indigo-900/20 to-slate-900 border border-slate-800 shadow-xl relative overflow-hidden">
        <div className="relative z-10">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-blue-400 mb-1">
            <Sparkles className="w-4 h-4" />
            <span>Workspace Overview</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            {activeWorkspace?.tenant_name || "Enterprise Workspace"}
          </h1>
          <p className="text-xs text-slate-300 mt-1 max-w-2xl">
            Type: <span className="font-semibold text-slate-100">{activeWorkspace?.tenant_type}</span>. All resources, departments, AI assistants, and knowledge collections within this workspace are isolated through cryptographic tenant boundaries.
          </p>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Employees Metric */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium">Active Members</span>
            <div className="w-8 h-8 rounded-xl bg-blue-600/20 text-blue-400 flex items-center justify-center">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">
            {loading ? "..." : employeeCount ?? 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Users enrolled in workspace</p>
        </div>

        {/* Departments Metric */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium">Departments</span>
            <div className="w-8 h-8 rounded-xl bg-purple-600/20 text-purple-400 flex items-center justify-center">
              <Briefcase className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">
            {loading ? "..." : departmentCount ?? 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Organizational business units</p>
        </div>

        {/* AI Assistants Metric */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium">AI Assistants</span>
            <div className="w-8 h-8 rounded-xl bg-emerald-600/20 text-emerald-400 flex items-center justify-center">
              <Bot className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">
            {loading ? "..." : assistantCount ?? 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Configured AI personas</p>
        </div>

        {/* Knowledge Bases Metric */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl">
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-medium">Knowledge Bases</span>
            <div className="w-8 h-8 rounded-xl bg-amber-600/20 text-amber-400 flex items-center justify-center">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">
            {loading ? "..." : knowledgeCount ?? 0}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Indexed document containers</p>
        </div>
      </div>

      {/* Main Sections: Quick Actions & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Launch Panel */}
        <div className="lg:col-span-1 p-6 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl space-y-4">
          <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
            Workspace Actions
          </h2>
          <div className="space-y-2">
            <Link
              href="/dashboard/employees"
              className="p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition flex items-center justify-between text-xs text-slate-300 hover:text-white group"
            >
              <div className="flex items-center gap-3">
                <Users className="w-4 h-4 text-blue-400" />
                <span>Manage Employees & Roles</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:translate-x-1 transition" />
            </Link>

            <Link
              href="/dashboard/departments"
              className="p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition flex items-center justify-between text-xs text-slate-300 hover:text-white group"
            >
              <div className="flex items-center gap-3">
                <Briefcase className="w-4 h-4 text-purple-400" />
                <span>Configure Departments</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:translate-x-1 transition" />
            </Link>

            <Link
              href="/dashboard/assistants"
              className="p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition flex items-center justify-between text-xs text-slate-300 hover:text-white group"
            >
              <div className="flex items-center gap-3">
                <Bot className="w-4 h-4 text-emerald-400" />
                <span>Configure AI Assistants</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:translate-x-1 transition" />
            </Link>

            <Link
              href="/dashboard/knowledge"
              className="p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition flex items-center justify-between text-xs text-slate-300 hover:text-white group"
            >
              <div className="flex items-center gap-3">
                <Database className="w-4 h-4 text-amber-400" />
                <span>Upload Knowledge Sources</span>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:translate-x-1 transition" />
            </Link>
          </div>

          <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-800/40 text-emerald-400 text-xs flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Zero-Trust Architecture: Role permissions and tenant boundaries are validated on every backend request.
            </span>
          </div>
        </div>

        {/* Recent Activity Audit Ledger */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-slate-400" />
              <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                Recent Audit Trail
              </h2>
            </div>
            <Link
              href="/dashboard/audit"
              className="text-xs text-blue-400 hover:text-blue-300 font-medium"
            >
              View Full Ledger &rarr;
            </Link>
          </div>

          {recentAudit.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-slate-800 rounded-xl">
              <History className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-xs text-slate-400">No audit activity recorded yet in this workspace.</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Actions like creating departments, inviting members, and managing assistants will appear here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/80">
              {recentAudit.map((log) => (
                <div key={log.id} className="py-3 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-mono text-blue-400 font-medium block">
                      {log.action}
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      By {log.actor_name || "System"} on {log.resource_type}
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
