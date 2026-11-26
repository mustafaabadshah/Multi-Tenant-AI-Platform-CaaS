"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, AuditLogItem } from "@/lib/api";
import { History, Shield, Terminal, Clock, User, Eye } from "lucide-react";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import Spinner from "@/components/ui/Spinner";

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
        console.error("Failed to load audit logs", err);
      } finally {
        setLoading(false);
      }
    }

    loadLogs();
  }, [activeWorkspace]);

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Audit Trail</h1>
        <p className="text-sm text-gray-600 mt-1">
          Immutable event log tracking administrative actions, role assignments, and workspace mutations.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-xs">
        {loading ? (
          <div className="p-12 flex items-center justify-center">
            <Spinner size="lg" />
          </div>
        ) : logs.length === 0 ? (
          <EmptyState
            icon={History}
            title="No audit events recorded"
            description="Actions performed in this workspace (creating assistants, uploading documents, role changes) will be recorded here."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Resource</th>
                  <th className="py-3 px-4">IP Address</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50/60 transition-colors">
                    <td className="py-3 px-4 text-gray-500 font-mono text-[11px]">
                      {new Date(log.created_at).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">
                        {log.action}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-medium text-gray-900">{log.actor_name || "System"}</span>
                    </td>
                    <td className="py-3 px-4 text-gray-600 font-mono">
                      {log.resource_type}
                    </td>
                    <td className="py-3 px-4 text-gray-400 font-mono text-[11px]">
                      {log.ip_address || "127.0.0.1"}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedLog(log)}
                        className="p-1.5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors inline-flex items-center gap-1"
                        title="View payload"
                      >
                        <Eye size={14} />
                        <span className="text-xs">Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Inspect Log Payload Modal */}
      {selectedLog && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedLog(null)}
          title={`Audit Event: ${selectedLog.action}`}
          description={`Logged at ${new Date(selectedLog.created_at).toLocaleString()} by ${selectedLog.actor_name || "System"}`}
          maxWidth="lg"
        >
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 text-xs bg-gray-50 p-3 rounded-lg border border-gray-200">
              <div>
                <span className="font-semibold block text-gray-700">Resource Type:</span>
                <span className="font-mono text-gray-900">{selectedLog.resource_type}</span>
              </div>
              <div>
                <span className="font-semibold block text-gray-700">Resource ID:</span>
                <span className="font-mono text-gray-900">{selectedLog.resource_id || "N/A"}</span>
              </div>
              <div>
                <span className="font-semibold block text-gray-700">Client IP:</span>
                <span className="font-mono text-gray-900">{selectedLog.ip_address || "127.0.0.1"}</span>
              </div>
              <div>
                <span className="font-semibold block text-gray-700">Tenant ID:</span>
                <span className="font-mono text-gray-900">{selectedLog.tenant_id}</span>
              </div>
            </div>

            <div>
              <span className="text-xs font-semibold text-gray-700 uppercase tracking-wider block mb-1">
                Event Payload & State
              </span>
              <pre className="p-3 rounded-lg bg-gray-900 text-gray-100 font-mono text-xs overflow-x-auto max-h-60">
                {JSON.stringify(selectedLog.details || {}, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2 border-t border-gray-100">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedLog(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
