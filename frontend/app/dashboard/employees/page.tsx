"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, Department, Member, RoleItem } from "@/lib/api";
import { Users, UserPlus, Trash2, Search, Mail, Briefcase } from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Modal from "@/components/ui/Modal";
import Badge from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import Spinner from "@/components/ui/Spinner";

export default function EmployeesPage() {
  const { activeWorkspace, user } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Modal State
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("employee");
  const [inviteDept, setInviteDept] = useState<string>("");
  const [inviteTitle, setInviteTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    try {
      const [membersData, deptsData, rolesData] = await Promise.all([
        api.listMembers(),
        api.listDepartments().catch(() => []),
        api.listRoles().catch(() => []),
      ]);
      setMembers(membersData);
      setDepartments(deptsData);
      setRoles(rolesData);
    } catch (err) {
      console.error("Failed to load employees data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeWorkspace]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.inviteMember({
        email: inviteEmail.trim(),
        role: inviteRole,
        department_id: inviteDept || undefined,
        title: inviteTitle.trim() || undefined,
      });
      setShowInviteModal(false);
      setInviteEmail("");
      setInviteTitle("");
      await loadData();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to invite member");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemove = async (memberId: string, memberEmail: string) => {
    if (!confirm(`Are you sure you want to remove ${memberEmail} from this workspace?`)) return;
    try {
      await api.removeMember(memberId);
      await loadData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to remove member");
    }
  };

  const filteredMembers = members.filter(
    (m) =>
      m.full_name.toLowerCase().includes(search.toLowerCase()) ||
      m.email.toLowerCase().includes(search.toLowerCase()) ||
      m.role.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">
            Employees & Team Members
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Manage authorized employees, roles, and department assignments in this workspace.
          </p>
        </div>
        <Button
          onClick={() => setShowInviteModal(true)}
          icon={UserPlus}
          iconPosition="left"
          variant="primary"
          size="sm"
        >
          Invite Member
        </Button>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-md">
        <Search size={16} className="text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, email, or role..."
          className="w-full pl-10 pr-3.5 py-2 rounded-lg bg-white border border-gray-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20 text-sm text-gray-900 placeholder:text-gray-400 outline-none"
        />
      </div>

      {/* Members Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-xs">
        {loading ? (
          <div className="p-12 flex items-center justify-center">
            <Spinner size="lg" />
          </div>
        ) : filteredMembers.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No members found"
            description="Invite colleagues to begin collaborating in this workspace."
            action={{
              label: "Invite First Member",
              onClick: () => setShowInviteModal(true),
              icon: UserPlus,
            }}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Employee</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Department</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Joined</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredMembers.map((m) => {
                  const isCurrentUser = m.email === user?.email;
                  return (
                    <tr key={m.id} className="hover:bg-gray-50/60 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-xs uppercase">
                            {m.full_name?.charAt(0) || m.email.charAt(0)}
                          </div>
                          <div>
                            <div className="font-semibold text-gray-900 flex items-center gap-1.5">
                              <span>{m.full_name}</span>
                              {isCurrentUser && (
                                <Badge variant="blue" size="xs">
                                  You
                                </Badge>
                              )}
                            </div>
                            <span className="text-gray-500 text-[11px]">{m.email}</span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge
                          variant={
                            m.role === "org_admin" || m.role === "tenant_owner"
                              ? "purple"
                              : m.role === "dept_admin" ||
                                  m.role === "assistant_manager" ||
                                  m.role === "knowledge_editor"
                                ? "blue"
                                : "gray"
                          }
                          size="xs"
                        >
                          {m.role}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-gray-600">
                        {m.department_name ? (
                          <span className="inline-flex items-center gap-1">
                            <Briefcase size={12} className="text-gray-400" />
                            <span>{m.department_name}</span>
                          </span>
                        ) : (
                          <span className="text-gray-400 italic">None</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <Badge
                          variant={m.status === "ACTIVE" ? "green" : "amber"}
                          size="xs"
                        >
                          {m.status || "ACTIVE"}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-gray-500 font-mono text-[11px]">
                        {new Date(m.created_at).toLocaleDateString([], {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {!isCurrentUser && (
                          <button
                            type="button"
                            onClick={() => handleRemove(m.id, m.email)}
                            className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-gray-100 transition-colors"
                            title="Remove from workspace"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Invite Member Modal */}
      {showInviteModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowInviteModal(false)}
          title="Invite Team Member"
          description="Grant an employee access to this workspace and its authorized assistants."
          maxWidth="md"
        >
          <form onSubmit={handleInvite} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Email Address *
              </label>
              <Input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@company.com"
                icon={Mail}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Workspace Role
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="employee">Employee (Standard Access)</option>
                  <option value="org_admin">Organization Admin</option>
                  <option value="dept_admin">Department Admin</option>
                  <option value="assistant_manager">Assistant Manager</option>
                  <option value="knowledge_editor">Knowledge Editor</option>
                  <option value="viewer">Viewer (Read Only)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Department
                </label>
                <select
                  value={inviteDept}
                  onChange={(e) => setInviteDept(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="">No Department</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Job Title (Optional)
              </label>
              <Input
                type="text"
                value={inviteTitle}
                onChange={(e) => setInviteTitle(e.target.value)}
                placeholder="e.g. Senior Research Analyst"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-gray-100">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setShowInviteModal(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={submitting}
              >
                Send Invitation
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
