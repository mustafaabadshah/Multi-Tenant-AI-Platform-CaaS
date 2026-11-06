"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, AuditLogItem } from "@/lib/api";
import { History, Shield, Terminal, Clock, User, Filter } from "lucide-react";

export default function AuditLogsPage() {
  const { activeWorkspace } = useAuth();
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);

  useEffect(() => {
    async function loadLogs() {
      if (!activeWorkspace) return;
      setLoading(true);
      try {
        const data = await api.listAuditLogs();
        setLogs(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadLogs();
  }, [activeWorkspace]);

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-xl font-bold text-white tracking-tight">Audit Trail & Compliance Ledger</h1>
        <p className="text-xs text-slate-400 mt-1">
          Immutable event log tracking administrative actions, role assignments, and workspace mutations.
        </p>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden backdrop-blur-xl">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400">Loading audit events...</div>
        ) : logs.length === 0 ? (
          <div className="p-16 text-center">
            <History className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-slate-200">No audit events recorded</h3>
            <p className="text-xs text-slate-400 mt-1">Actions performed in this workspace will be recorded here.</p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/40 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Resource</th>
                <th className="py-3 px-4">IP Address</th>
                <th className="py-3 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-800/30 transition">
                  <td className="py-3 px-4 text-slate-400">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="py-3 px-4">
                    <span className="font-semibold text-blue-400 bg-blue-950/60 border border-blue-800/60 px-2 py-0.5 rounded">
                      {log.action}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-300 font-sans">
                    {log.actor_name || "System"}
                  </td>
                  <td className="py-3 px-4 text-slate-400 font-sans">
                    {log.resource_type}
                  </td>
                  <td className="py-3 px-4 text-slate-500">
                    {log.ip_address || "127.0.0.1"}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      type="button"
                      onClick={() => setSelectedLog(log)}
                      className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-sans text-xs transition cursor-pointer"
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Inspect Modal */}
      {selectedLog && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-lg w-full shadow-2xl animate-fadeIn">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-bold text-slate-100">Audit Event Payload</h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedLog(null)}
                className="text-xs text-slate-400 hover:text-white"
              >
                Close
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Event ID:</span>
                <span className="font-mono text-slate-200 select-all">{selectedLog.id}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Action:</span>
                <span className="font-mono text-blue-400 font-semibold">{selectedLog.action}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Actor:</span>
                <span className="text-slate-200">{selectedLog.actor_name || "System"}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Timestamp:</span>
                <span className="font-mono text-slate-300">{new Date(selectedLog.created_at).toISOString()}</span>
              </div>

              <div>
                <span className="block text-slate-400 font-medium mb-1">Payload JSON:</span>
                <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] text-emerald-400 overflow-x-auto max-h-48">
                  {JSON.stringify(selectedLog.details, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
