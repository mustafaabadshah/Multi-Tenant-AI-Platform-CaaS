"use client";

import React, { useState, useEffect } from "react";
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
  ExternalLink,
  Activity,
  MessageSquare,
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, activeWorkspace, workspaces, switchWorkspace, refreshWorkspaces, logout, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const [showCreateWorkspaceModal, setShowCreateWorkspaceModal] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [newWsType, setNewWsType] = useState<"INDIVIDUAL" | "ORGANIZATION">("ORGANIZATION");
  const [creatingWs, setCreatingWs] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <Spinner size="lg" />
          <p className="text-gray-500 text-sm">{isLoading ? "Loading workspace..." : "Redirecting to sign in..."}</p>
        </div>
      </div>
    );
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

  const navGroups = [
    {
      group: "Workspace",
      items: [
        { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
        { label: "Assistants", href: "/dashboard/assistants", icon: Bot },
        { label: "Knowledge", href: "/dashboard/knowledge", icon: Database },
        { label: "Conversations", href: "/dashboard/conversations", icon: MessageSquare },
      ],
    },
    {
      group: "Operate",
      items: [
        { label: "Observability", href: "/dashboard/observability", icon: Activity },
      ],
    },
    {
      group: "Organization",
      items: [
        { label: "Employees", href: "/dashboard/employees", icon: Users },
        { label: "Departments", href: "/dashboard/departments", icon: Briefcase },
        { label: "Groups", href: "/dashboard/groups", icon: Layers },
        { label: "Organization", href: "/dashboard/workspace", icon: Building2 },
      ],
    },
    {
      group: "Settings",
      items: [
        { label: "Providers & Keys", href: "/dashboard/providers", icon: Key },
        { label: "Audit Logs", href: "/dashboard/audit", icon: History },
        { label: "Settings", href: "/dashboard/settings", icon: Settings },
      ],
    },
  ];

  const renderNavItems = (collapsed = false) => {
    return (
      <nav className="space-y-4 px-2">
        {navGroups.map((group) => (
          <div key={group.group} className="space-y-1">
            {!collapsed && (
              <div className="px-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                {group.group}
              </div>
            )}
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === "/dashboard"
                  ? pathname === "/dashboard"
                  : pathname.startsWith(item.href);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  title={collapsed ? item.label : undefined}
                  className={`flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                    collapsed ? "justify-center" : ""
                  } ${
                    isActive
                      ? "bg-blue-50 text-blue-600 font-semibold"
                      : "text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                  }`}
                >
                  <Icon size={18} className={`shrink-0 ${isActive ? "text-blue-600" : "text-gray-500"}`} />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Mobile Drawer Backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-900/40 backdrop-blur-xs lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile Drawer */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 ease-in-out lg:hidden flex flex-col justify-between ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div>
          {/* Mobile Header */}
          <div className="h-16 px-4 border-b border-gray-200 flex items-center justify-between">
            <Link
              href="/dashboard"
              className="flex items-center gap-2.5"
              onClick={() => setMobileMenuOpen(false)}
            >
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm">
                M
              </div>
              <div className="truncate">
                <span className="font-semibold text-gray-900 text-sm tracking-tight block">Multi-Tenant AI Platform</span>
                <span className="text-[10px] text-gray-500 block">Multi-Tenant CaaS</span>
              </div>
            </Link>
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              className="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            >
              <X size={20} />
            </button>
          </div>

          {/* Mobile Nav */}
          <div className="p-3 overflow-y-auto max-h-[calc(100vh-140px)]">
            {renderNavItems(false)}
          </div>
        </div>

        {/* Mobile User Footer */}
        <div className="p-3 border-t border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="min-w-0 pr-2">
              <span className="text-xs font-semibold text-gray-900 truncate block">{user.full_name}</span>
              <span className="text-[11px] text-gray-500 truncate block">{user.email}</span>
            </div>
            <button
              type="button"
              onClick={logout}
              className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-gray-100 transition-colors"
              title="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Desktop Persistent Sidebar */}
      <aside
        className={`hidden lg:flex flex-col justify-between shrink-0 bg-white border-r border-gray-200 transition-all duration-200 sticky top-0 h-screen ${
          isCollapsed ? "w-16" : "w-64"
        }`}
      >
        <div className="flex flex-col min-h-0">
          {/* Sidebar Header */}
          <div className="h-16 px-3 border-b border-gray-200 flex items-center justify-between">
            {!isCollapsed ? (
              <Link href="/dashboard" className="flex items-center gap-2.5 min-w-0 px-1">
                <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm shrink-0">
                  M
                </div>
                <div className="truncate">
                  <span className="font-semibold text-gray-900 text-sm block tracking-tight truncate">
                    Multi-Tenant AI Platform
                  </span>
                  <span className="text-[10px] text-gray-500 block truncate">Multi-Tenant CaaS</span>
                </div>
              </Link>
            ) : (
              <Link href="/dashboard" className="mx-auto" title="Multi-Tenant AI Platform">
                <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm">
                  M
                </div>
              </Link>
            )}

            <button
              type="button"
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
          </div>

          {/* Workspace Switcher */}
          {!isCollapsed ? (
            <div className="p-3 border-b border-gray-100 relative">
              <button
                type="button"
                onClick={() => setWorkspaceMenuOpen(!workspaceMenuOpen)}
                className="w-full p-2 rounded-lg bg-gray-50 border border-gray-200 hover:border-gray-300 transition-colors flex items-center justify-between text-left cursor-pointer group"
              >
                <div className="min-w-0 pr-2">
                  <span className="text-[10px] uppercase font-semibold text-gray-500 block tracking-wider">
                    Workspace
                  </span>
                  <span className="text-xs font-semibold text-gray-900 truncate block">
                    {activeWorkspace?.tenant_name || "Select Workspace"}
                  </span>
                  <span className="text-[10px] text-blue-600 font-mono block">
                    {activeWorkspace?.tenant_type || "ORGANIZATION"}
                  </span>
                </div>
                <ChevronDown size={14} className="text-gray-400 group-hover:text-gray-600 shrink-0" />
              </button>

              {/* Workspace Dropdown */}
              {workspaceMenuOpen && (
                <div className="absolute top-full left-3 right-3 mt-1.5 p-1.5 rounded-lg bg-white border border-gray-200 shadow-lg z-50 animate-fadeIn">
                  <div className="text-[10px] font-semibold text-gray-500 px-2 py-1 uppercase tracking-wider">
                    Available Workspaces
                  </div>
                  <div className="max-h-48 overflow-y-auto space-y-0.5">
                    {workspaces.map((ws) => (
                      <button
                        key={ws.tenant_id}
                        type="button"
                        onClick={() => {
                          switchWorkspace(ws.tenant_id);
                          setWorkspaceMenuOpen(false);
                        }}
                        className={`w-full p-2 rounded-md text-left text-xs transition-colors flex items-center justify-between cursor-pointer ${
                          ws.tenant_id === activeWorkspace?.tenant_id
                            ? "bg-blue-50 text-blue-700 font-semibold"
                            : "text-gray-700 hover:bg-gray-100"
                        }`}
                      >
                        <div className="truncate">
                          <span className="block truncate">{ws.tenant_name}</span>
                          <span className="text-[10px] text-gray-400 block font-mono">{ws.tenant_type}</span>
                        </div>
                        {ws.tenant_id === activeWorkspace?.tenant_id && (
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-600 shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>

                  <div className="pt-1.5 mt-1 border-t border-gray-100">
                    <button
                      type="button"
                      onClick={() => {
                        setWorkspaceMenuOpen(false);
                        setShowCreateWorkspaceModal(true);
                      }}
                      className="w-full p-1.5 rounded-md text-xs text-blue-600 hover:bg-blue-50 flex items-center gap-1.5 font-medium cursor-pointer"
                    >
                      <PlusCircle size={14} />
                      <span>New Workspace</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="py-2 flex justify-center border-b border-gray-100">
              <button
                type="button"
                onClick={() => setIsCollapsed(false)}
                title={`Active: ${activeWorkspace?.tenant_name || "Workspace"}`}
                className="w-10 h-10 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-center text-gray-700 hover:bg-gray-100"
              >
                <Building2 size={18} />
              </button>
            </div>
          )}

          {/* Nav List */}
          <div className="py-3 overflow-y-auto flex-1">{renderNavItems(isCollapsed)}</div>
        </div>

        {/* Desktop Footer */}
        <div className="p-3 border-t border-gray-200 bg-white">
          {!isCollapsed ? (
            <div className="flex items-center justify-between">
              <div className="min-w-0 pr-2">
                <span className="text-xs font-semibold text-gray-900 truncate block">{user.full_name}</span>
                <span className="text-[11px] text-gray-500 truncate block">{user.email}</span>
                <span className="inline-block mt-0.5 text-[9px] uppercase tracking-wider font-semibold px-1.5 py-0.2 rounded bg-gray-100 text-gray-600 border border-gray-200">
                  {activeWorkspace?.role || "Member"}
                </span>
              </div>
              <button
                type="button"
                onClick={logout}
                title="Logout"
                className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-gray-100 transition-colors"
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={logout}
                title="Logout"
                className="p-2 rounded-lg text-gray-400 hover:text-red-600 hover:bg-gray-100 transition-colors"
              >
                <LogOut size={18} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Viewport */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Sticky Topbar */}
        <header className="sticky top-0 z-30 h-16 bg-white border-b border-gray-200 px-4 sm:px-6 lg:px-8 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 lg:hidden"
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-gray-900">
                {activeWorkspace?.tenant_name || "Workspace"}
              </h2>
              <span className="hidden sm:inline-flex text-[10px] font-mono px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 border border-gray-200">
                {activeWorkspace?.tenant_slug}
              </span>
              <span className="inline-flex items-center gap-1.5 text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Tenant Isolated</span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs text-gray-600">
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="hidden sm:flex items-center gap-1 hover:text-blue-600 transition-colors"
            >
              <span>API Reference</span>
              <ExternalLink size={12} />
            </a>
            <div className="hidden sm:block w-px h-4 bg-gray-200" />
            <div className="flex items-center gap-1.5 text-blue-600 font-medium">
              <ShieldCheck size={14} />
              <span className="hidden md:inline">RBAC & BYOK Active</span>
            </div>
          </div>
        </header>

        {/* Page Main Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">{children}</main>
      </div>

      {/* Create Workspace Modal */}
      {showCreateWorkspaceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/40 backdrop-blur-xs animate-fadeIn">
          <div className="bg-white border border-gray-200 rounded-xl p-6 max-w-md w-full shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                <Building2 size={20} />
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">Create New Workspace</h3>
                <p className="text-xs text-gray-500">Add an individual sandbox or organizational tenant</p>
              </div>
            </div>

            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Workspace Name
                </label>
                <input
                  type="text"
                  required
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  placeholder="e.g. Apex AI Research or Marketing Team"
                  className="w-full px-3 py-2 rounded-lg bg-white border border-gray-300 text-sm text-gray-900 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Workspace Type
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setNewWsType("ORGANIZATION")}
                    className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                      newWsType === "ORGANIZATION"
                        ? "border-blue-600 bg-blue-50/50 text-blue-700"
                        : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                    }`}
                  >
                    <span className="font-semibold text-xs block">Organization</span>
                    <span className="text-[10px] text-gray-500">Multi-department & team</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewWsType("INDIVIDUAL")}
                    className={`p-3 rounded-lg border text-left transition-colors cursor-pointer ${
                      newWsType === "INDIVIDUAL"
                        ? "border-blue-600 bg-blue-50/50 text-blue-700"
                        : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                    }`}
                  >
                    <span className="font-semibold text-xs block">Individual</span>
                    <span className="text-[10px] text-gray-500">Solo workspace</span>
                  </button>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowCreateWorkspaceModal(false)}
                  className="px-3 py-2 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingWs}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs transition-colors disabled:opacity-50"
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
