"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  LayoutDashboard,
  Building2,
  Users,
  Briefcase,
  Layers,
  Bot,
  Database,
  History,
  Key,
  Settings,
  ChevronDown,
  PlusCircle,
  LogOut,
  Shield,
  Sparkles,
  ExternalLink,
} from "lucide-react";
import { api } from "@/lib/api";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, activeWorkspace, workspaces, switchWorkspace, refreshWorkspaces, logout, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const [showCreateWorkspaceModal, setShowCreateWorkspaceModal] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [newWsType, setNewWsType] = useState<"INDIVIDUAL" | "ORGANIZATION">("ORGANIZATION");
  const [creatingWs, setCreatingWs] = useState(false);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-slate-400 text-sm">Loading workspace...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    router.push("/login");
    return null;
  }

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreatingWs(true);
    try {
      const created = await api.createWorkspace({
        name: newWsName.trim(),
        type: newWsType,
      });
      await refreshWorkspaces();
      await switchWorkspace(created.id);
      setShowCreateWorkspaceModal(false);
      setNewWsName("");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create workspace");
    } finally {
      setCreatingWs(false);
    }
  };

  const navItems = [
    { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
    {
      category: "Workspace",
      items: [
        { label: "Organization", href: "/dashboard/workspace", icon: Building2 },
        { label: "Employees", href: "/dashboard/employees", icon: Users },
        { label: "Departments", href: "/dashboard/departments", icon: Briefcase },
        { label: "Groups", href: "/dashboard/groups", icon: Layers },
      ],
    },
    {
      category: "AI Platform",
      items: [
        { label: "Assistants", href: "/dashboard/assistants", icon: Bot },
        { label: "Knowledge Bases", href: "/dashboard/knowledge", icon: Database },
        { label: "Providers & Keys", href: "/dashboard/providers", icon: Key },
      ],
    },
    {
      category: "Administration",
      items: [
        { label: "Audit Logs", href: "/dashboard/audit", icon: History },
        { label: "Settings", href: "/dashboard/settings", icon: Settings },
      ],
    },
  ];

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 bg-slate-900/60 backdrop-blur-xl flex flex-col justify-between shrink-0">
        <div>
          {/* Brand */}
          <div className="h-16 px-5 border-b border-slate-800 flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20 ring-1 ring-white/20">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-sm tracking-tight text-white block">Multi-Tenant AI Platform-CaaS</span>
              <span className="text-[10px] text-blue-400 font-medium block">Enterprise Multi-Tenant</span>
            </div>
          </div>

          {/* Workspace Switcher */}
          <div className="p-3 border-b border-slate-800/80 relative">
            <button
              type="button"
              onClick={() => setWorkspaceMenuOpen(!workspaceMenuOpen)}
              className="w-full p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-slate-700 transition flex items-center justify-between text-left cursor-pointer group"
            >
              <div className="min-w-0 pr-2">
                <span className="text-[10px] uppercase font-semibold text-slate-400 block tracking-wider">
                  Active Workspace
                </span>
                <span className="text-xs font-semibold text-slate-100 truncate block">
                  {activeWorkspace?.tenant_name || "Select Workspace"}
                </span>
                <span className="text-[10px] text-blue-400 block font-mono">
                  {activeWorkspace?.tenant_type || "ORGANIZATION"}
                </span>
              </div>
              <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 group-hover:text-slate-200 transition" />
            </button>

            {/* Switcher Dropdown */}
            {workspaceMenuOpen && (
              <div className="absolute top-full left-3 right-3 mt-1.5 p-1.5 rounded-xl bg-slate-900 border border-slate-800 shadow-2xl z-50 animate-fadeIn">
                <div className="text-[10px] font-semibold text-slate-400 px-2 py-1 uppercase tracking-wider">
                  Available Workspaces
                </div>
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {workspaces.map((ws) => (
                    <button
                      key={ws.tenant_id}
                      type="button"
                      onClick={() => {
                        switchWorkspace(ws.tenant_id);
                        setWorkspaceMenuOpen(false);
                      }}
                      className={`w-full p-2 rounded-lg text-left text-xs transition flex items-center justify-between cursor-pointer ${
                        ws.tenant_id === activeWorkspace?.tenant_id
                          ? "bg-blue-600/20 text-blue-300 font-semibold border border-blue-500/30"
                          : "text-slate-300 hover:bg-slate-800/70"
                      }`}
                    >
                      <div className="truncate">
                        <span className="block truncate">{ws.tenant_name}</span>
                        <span className="text-[10px] text-slate-400 block font-mono">{ws.tenant_type}</span>
                      </div>
                      {ws.tenant_id === activeWorkspace?.tenant_id && (
                        <span className="w-2 h-2 rounded-full bg-blue-400 shrink-0"></span>
                      )}
                    </button>
                  ))}
                </div>

                <div className="pt-1.5 mt-1 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => {
                      setWorkspaceMenuOpen(false);
                      setShowCreateWorkspaceModal(true);
                    }}
                    className="w-full p-2 rounded-lg text-xs text-blue-400 hover:bg-blue-950/40 flex items-center gap-2 transition cursor-pointer font-medium"
                  >
                    <PlusCircle className="w-3.5 h-3.5" />
                    <span>Create New Workspace</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-5 overflow-y-auto max-h-[calc(100vh-250px)]">
            <Link
              href="/dashboard"
              className={`flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium transition ${
                pathname === "/dashboard"
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              <span>Overview</span>
            </Link>

            {navItems.slice(1).map((group, idx) => (
              <div key={idx} className="space-y-1">
                <span className="text-[10px] uppercase font-bold text-slate-400 px-3 tracking-wider block">
                  {group.category}
                </span>
                {group.items?.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium transition ${
                        active
                          ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30"
                          : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>

        {/* User Account Footer */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/40">
          <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
            <div className="min-w-0 pr-2">
              <span className="text-xs font-semibold text-slate-200 truncate block">
                {user.full_name}
              </span>
              <span className="text-[11px] text-slate-400 truncate block">
                {user.email}
              </span>
              <span className="inline-block mt-0.5 text-[9px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800">
                {activeWorkspace?.role || "Member"}
              </span>
            </div>
            <button
              type="button"
              onClick={logout}
              title="Sign Out"
              className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800 transition cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-16 border-b border-slate-800 bg-slate-900/40 backdrop-blur-xl px-8 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-slate-200">
              {activeWorkspace?.tenant_name || "Workspace"}
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              {activeWorkspace?.tenant_slug}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Tenant Isolated
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs text-slate-400">
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 hover:text-slate-200 transition"
            >
              <span>API Reference</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <div className="w-px h-4 bg-slate-800"></div>
            <div className="flex items-center gap-1.5 text-blue-400">
              <Sparkles className="w-3.5 h-3.5" />
              <span>OmniRoute AI Gateway Ready</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-8 overflow-y-auto">{children}</main>
      </div>

      {/* Create Workspace Modal */}
      {showCreateWorkspaceModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-blue-600/20 text-blue-400 flex items-center justify-center">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-100">Create New Workspace</h3>
                <p className="text-xs text-slate-400">Add an individual sandbox or organization</p>
              </div>
            </div>

            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Workspace Name
                </label>
                <input
                  type="text"
                  required
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  placeholder="e.g. Apex AI Research or Marketing Team"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Workspace Type
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setNewWsType("ORGANIZATION")}
                    className={`p-2.5 rounded-xl border text-xs text-left transition cursor-pointer ${
                      newWsType === "ORGANIZATION"
                        ? "border-blue-500 bg-blue-950/40 text-blue-200"
                        : "border-slate-800 bg-slate-950 text-slate-400"
                    }`}
                  >
                    <span className="font-bold block">Organization</span>
                    <span className="text-[10px] text-slate-400">Multi-department & team</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewWsType("INDIVIDUAL")}
                    className={`p-2.5 rounded-xl border text-xs text-left transition cursor-pointer ${
                      newWsType === "INDIVIDUAL"
                        ? "border-blue-500 bg-blue-950/40 text-blue-200"
                        : "border-slate-800 bg-slate-950 text-slate-400"
                    }`}
                  >
                    <span className="font-bold block">Individual</span>
                    <span className="text-[10px] text-slate-400">Solo workspace</span>
                  </button>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowCreateWorkspaceModal(false)}
                  className="px-3 py-2 rounded-xl text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingWs}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition cursor-pointer disabled:opacity-50"
                >
                  {creatingWs ? "Creating..." : "Create Workspace"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
