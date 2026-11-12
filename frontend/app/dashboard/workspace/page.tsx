"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { API_V1 } from "@/lib/api";
import { Building2, Globe, ShieldCheck } from "lucide-react";
import Badge from "@/components/ui/Badge";
import Spinner from "@/components/ui/Spinner";

export default function WorkspaceProfilePage() {
  const { activeWorkspace } = useAuth();
  const [orgData, setOrgData] = useState<{
    legal_name?: string;
    domain?: string;
    tax_id?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadOrg() {
      if (!activeWorkspace) return;
      try {
        const res = await fetch(`${API_V1}/organizations/${activeWorkspace.tenant_id}`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("mmaip_token") || localStorage.getItem("token") || ""}`,
            "X-Tenant-ID": activeWorkspace.tenant_id,
          },
        });
        if (res.ok) {
          const data = await res.json();
          setOrgData(data);
        }
      } catch {
        // May be individual workspace
      } finally {
        setLoading(false);
      }
    }

    loadOrg();
  }, [activeWorkspace]);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Organization Profile</h1>
        <p className="text-sm text-gray-600 mt-1">
          Review configuration and isolation credentials for the active workspace.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-xs space-y-6">
        <div className="flex items-center gap-4 pb-6 border-b border-gray-100">
          <div className="w-12 h-12 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <Building2 size={24} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-gray-900">{activeWorkspace?.tenant_name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                slug: {activeWorkspace?.tenant_slug}
              </span>
              <Badge variant="blue" size="xs">
                {activeWorkspace?.tenant_type || "ORGANIZATION"}
              </Badge>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="py-8 flex items-center justify-center">
            <Spinner size="md" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1">
                Legal Entity Name
              </span>
              <span className="text-sm font-medium text-gray-900">
                {orgData?.legal_name || activeWorkspace?.tenant_name || "N/A"}
              </span>
            </div>

            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1">
                Primary Domain
              </span>
              <div className="flex items-center gap-2 text-sm font-medium text-gray-900">
                <Globe size={14} className="text-gray-400" />
                <span>{orgData?.domain || "Local Development Sandbox"}</span>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1">
                Tax / Registration ID
              </span>
              <span className="text-sm font-mono text-gray-900">
                {orgData?.tax_id || "Not configured"}
              </span>
            </div>

            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-1">
                Your Workspace Role
              </span>
              <span className="text-sm font-medium text-blue-600 capitalize">
                {activeWorkspace?.role || "Member"}
              </span>
            </div>
          </div>
        )}

        <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200 flex items-start gap-3 text-xs text-emerald-800">
          <ShieldCheck size={18} className="text-emerald-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block mb-0.5">Strict Tenant Boundary Enforcement</span>
            <span>
              All relational queries, vector searches, and conversation contexts are partitioned by your tenant identifier:{" "}
              <code className="font-mono bg-emerald-100/80 px-1 py-0.5 rounded text-emerald-900">
                {activeWorkspace?.tenant_id}
              </code>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
