"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, API_V1 } from "@/lib/api";
import { Building2, Globe, CheckCircle2 } from "lucide-react";

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
            Authorization: `Bearer ${localStorage.getItem("mmaip_token")}`,
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
        <h1 className="text-xl font-bold text-white tracking-tight">Organization Profile</h1>
        <p className="text-xs text-slate-400 mt-1">
          Review configuration and isolation credentials for the active workspace.
        </p>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-xl space-y-6">
        <div className="flex items-center gap-4 pb-6 border-b border-slate-800">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-xl">
            <Building2 className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">{activeWorkspace?.tenant_name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                slug: {activeWorkspace?.tenant_slug}
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800">
                {activeWorkspace?.tenant_type}
              </span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
          <div>
            <label className="block text-slate-400 font-medium mb-1">Tenant ID (UUID)</label>
            <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-slate-300 select-all">
              {activeWorkspace?.tenant_id}
            </div>
          </div>

          <div>
            <label className="block text-slate-400 font-medium mb-1">Your Role in Workspace</label>
            <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 font-semibold text-blue-400 capitalize">
              {activeWorkspace?.role}
            </div>
          </div>

          {activeWorkspace?.tenant_type === "ORGANIZATION" && (
            <>
              <div>
                <label className="block text-slate-400 font-medium mb-1">Legal Entity Name</label>
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200">
                  {orgData?.legal_name || activeWorkspace?.tenant_name}
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Corporate Domain</label>
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 flex items-center gap-2">
                  <Globe className="w-3.5 h-3.5 text-slate-500" />
                  <span>{orgData?.domain || "Not configured"}</span>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-800/40 text-xs text-emerald-400 flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <div>
            <span className="font-semibold block">Tenant Boundaries Active</span>
            <span className="text-[11px] text-emerald-500/90 block">
              All queries and documents in this workspace are strictly partitioned by composite database keys and authenticated session headers.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
