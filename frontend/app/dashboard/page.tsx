"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api, AuditLogItem } from "@/lib/api";
import {
  Users,
  Bot,
  Database,
  ShieldCheck,
  History,
  ArrowRight,
  Plus,
  MessageSquare,
  Key,
  ChevronRight,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Spinner from "@/components/ui/Spinner";

export default function DashboardOverviewPage() {
  const { activeWorkspace } = useAuth();
  const [employeeCount, setEmployeeCount] = useState<number | null>(null);
  const [assistantCount, setAssistantCount] = useState<number | null>(null);
  const [knowledgeCount, setKnowledgeCount] = useState<number | null>(null);
  const [conversationCount, setConversationCount] = useState<number | null>(null);
  const [recentAudit, setRecentAudit] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      if (!activeWorkspace) return;
      setLoading(true);
      try {
        const [members, assistants, knowledge, conversations, auditLogs] =
          await Promise.allSettled([
            api.listMembers(),
            api.listAssistants(),
            api.listKnowledgeBases(),
            api.listConversations(),
            api.listAuditLogs(),
          ]);

        if (members.status === "fulfilled") setEmployeeCount(members.value.length);
        if (assistants.status === "fulfilled") setAssistantCount(assistants.value.length);
        if (knowledge.status === "fulfilled") setKnowledgeCount(knowledge.value.length);
        if (conversations.status === "fulfilled") setConversationCount(conversations.value.length);
        if (auditLogs.status === "fulfilled") setRecentAudit(auditLogs.value.slice(0, 5));
      } catch (err) {
        console.error("Error loading dashboard metrics", err);
      } finally {
        setLoading(false);
      }
    }

    loadStats();
  }, [activeWorkspace]);

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Workspace Header Banner */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Dashboard</h1>
        <p className="text-sm text-gray-600 mt-1">
          Welcome to your{" "}
          <span className="font-semibold text-gray-900">
            {activeWorkspace?.tenant_name || "Enterprise"}
          </span>{" "}
          workspace. Manage your knowledge bases, AI assistants, conversations, and organization.
        </p>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Knowledge Bases Metric */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 hover:border-gray-300 transition-colors">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
              <Database size={22} />
            </div>
            <span className="text-2xl font-bold text-gray-900">
              {loading ? <Spinner size="sm" /> : knowledgeCount ?? 0}
            </span>
          </div>
          <h3 className="text-sm font-semibold text-gray-900">Knowledge Bases</h3>
          <p className="text-xs text-gray-500 mb-3">Indexed document collections</p>
          <Link href="/dashboard/knowledge">
            <Button variant="secondary" size="xs" className="w-full">
              View All
            </Button>
          </Link>
        </div>

        {/* AI Assistants Metric */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 hover:border-gray-300 transition-colors">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2.5 rounded-lg bg-purple-50 text-purple-600">
              <Bot size={22} />
            </div>
            <span className="text-2xl font-bold text-gray-900">
              {loading ? <Spinner size="sm" /> : assistantCount ?? 0}
            </span>
          </div>
          <h3 className="text-sm font-semibold text-gray-900">AI Assistants</h3>
          <p className="text-xs text-gray-500 mb-3">Configured AI personas</p>
          <Link href="/dashboard/assistants">
            <Button variant="secondary" size="xs" className="w-full">
              Manage Assistants
            </Button>
          </Link>
        </div>

        {/* Conversations Metric */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 hover:border-gray-300 transition-colors">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-600">
              <MessageSquare size={22} />
            </div>
            <span className="text-2xl font-bold text-gray-900">
              {loading ? <Spinner size="sm" /> : conversationCount ?? 0}
            </span>
          </div>
          <h3 className="text-sm font-semibold text-gray-900">Conversations</h3>
          <p className="text-xs text-gray-500 mb-3">Active chat threads</p>
          <Link href="/dashboard/conversations">
            <Button variant="secondary" size="xs" className="w-full">
              Open Chat
            </Button>
          </Link>
        </div>

        {/* Members Metric */}
        <div className="bg-white border border-gray-200 rounded-lg p-5 hover:border-gray-300 transition-colors">
          <div className="flex items-center justify-between mb-3">
            <div className="p-2.5 rounded-lg bg-amber-50 text-amber-600">
              <Users size={22} />
            </div>
            <span className="text-2xl font-bold text-gray-900">
              {loading ? <Spinner size="sm" /> : employeeCount ?? 0}
            </span>
          </div>
          <h3 className="text-sm font-semibold text-gray-900">Team Members</h3>
          <p className="text-xs text-gray-500 mb-3">Enrolled workspace users</p>
          <Link href="/dashboard/employees">
            <Button variant="secondary" size="xs" className="w-full">
              Manage Team
            </Button>
          </Link>
        </div>
      </div>

      {/* Main Sections: Quick Actions & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Launch Panel */}
        <div className="lg:col-span-1 bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">
            Quick Actions
          </h2>
          <div className="space-y-2">
            <Link
              href="/dashboard/conversations"
              className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors flex items-center justify-between text-xs text-gray-800 group"
            >
              <div className="flex items-center gap-3">
                <MessageSquare size={16} className="text-emerald-600" />
                <span className="font-medium">Start New Conversation</span>
              </div>
              <ChevronRight size={14} className="text-gray-400 group-hover:translate-x-0.5 transition-transform" />
            </Link>

            <Link
              href="/dashboard/knowledge"
              className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors flex items-center justify-between text-xs text-gray-800 group"
            >
              <div className="flex items-center gap-3">
                <Database size={16} className="text-blue-600" />
                <span className="font-medium">Upload Knowledge Base</span>
              </div>
              <ChevronRight size={14} className="text-gray-400 group-hover:translate-x-0.5 transition-transform" />
            </Link>

            <Link
              href="/dashboard/assistants"
              className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors flex items-center justify-between text-xs text-gray-800 group"
            >
              <div className="flex items-center gap-3">
                <Bot size={16} className="text-purple-600" />
                <span className="font-medium">Create AI Assistant</span>
              </div>
              <ChevronRight size={14} className="text-gray-400 group-hover:translate-x-0.5 transition-transform" />
            </Link>

            <Link
              href="/dashboard/providers"
              className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-colors flex items-center justify-between text-xs text-gray-800 group"
            >
              <div className="flex items-center gap-3">
                <Key size={16} className="text-amber-600" />
                <span className="font-medium">Manage BYOK API Keys</span>
              </div>
              <ChevronRight size={14} className="text-gray-400 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>

          <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2.5">
            <ShieldCheck size={16} className="shrink-0 mt-0.5 text-emerald-600" />
            <span>
              Zero-Trust Isolation: Role permissions and tenant boundaries are cryptographically scoped on every backend request.
            </span>
          </div>
        </div>

        {/* Recent Activity Audit Ledger */}
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <History size={16} className="text-gray-500" />
              <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">
                Recent Activity
              </h2>
            </div>
            <Link
              href="/dashboard/audit"
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              View Full Audit Trail &rarr;
            </Link>
          </div>

          {recentAudit.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-gray-200 rounded-lg">
              <History size={24} className="text-gray-300 mx-auto mb-2" />
              <p className="text-xs text-gray-600 font-medium">No recent activity to display.</p>
              <p className="text-[11px] text-gray-400 mt-0.5">
                Actions like creating assistants, uploading documents, and managing credentials will appear here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {recentAudit.map((log) => (
                <div key={log.id} className="py-3 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-mono text-blue-600 font-semibold block">
                      {log.action}
                    </span>
                    <span className="text-gray-500 text-[11px]">
                      By {log.actor_name || "System"} on {log.resource_type}
                    </span>
                  </div>
                  <span className="text-[11px] text-gray-400 font-mono">
                    {new Date(log.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
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
