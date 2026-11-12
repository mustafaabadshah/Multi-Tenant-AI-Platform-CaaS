"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, EmployeeGroup, Department } from "@/lib/api";
import { Layers, Plus, Trash2, Users } from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import Spinner from "@/components/ui/Spinner";

export default function GroupsPage() {
  const { activeWorkspace } = useAuth();
  const [groups, setGroups] = useState<EmployeeGroup[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadGroups = async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    try {
      const [gData, dData] = await Promise.all([
        api.listGroups(),
        api.listDepartments().catch(() => []),
      ]);
      setGroups(gData);
      setDepartments(dData);
    } catch (err) {
      console.error("Failed to load groups", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGroups();
  }, [activeWorkspace]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.createGroup({
        name: name.trim(),
        description: description.trim() || undefined,
        department_id: departmentId || undefined,
      });
      setShowCreateModal(false);
      setName("");
      setDescription("");
      setDepartmentId("");
      await loadGroups();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to create group");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, groupName: string) => {
    if (!confirm(`Are you sure you want to delete group "${groupName}"?`)) return;
    try {
      await api.deleteGroup(id);
      await loadGroups();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete group");
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Employee Groups</h1>
          <p className="text-sm text-gray-600 mt-1">
            Group team members across departments for collaborative projects, shared assistants, and access tiers.
          </p>
        </div>
        <Button
          onClick={() => setShowCreateModal(true)}
          icon={Plus}
          iconPosition="left"
          variant="primary"
          size="sm"
        >
          Create Group
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[300px]">
          <Spinner size="lg" />
        </div>
      ) : groups.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="No employee groups found"
          description="Create cross-functional groups to assign bulk assistant access and knowledge access."
          action={{
            label: "Create First Group",
            onClick: () => setShowCreateModal(true),
            icon: Plus,
          }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {groups.map((group) => {
            const dept = departments.find((d) => d.id === group.department_id);
            return (
              <div
                key={group.id}
                className="bg-white border border-gray-200 rounded-lg p-5 flex flex-col justify-between hover:border-gray-300 hover:shadow-xs transition-all"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-9 h-9 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                      <Layers size={18} />
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDelete(group.id, group.name)}
                      className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-gray-100 transition-colors"
                      title="Delete group"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900 tracking-tight">{group.name}</h3>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                    {group.description || "No description provided."}
                  </p>
                  {dept && (
                    <span className="inline-block mt-2 text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 border border-gray-200">
                      {dept.name}
                    </span>
                  )}
                </div>

                <div className="pt-4 mt-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                  <span className="flex items-center gap-1.5">
                    <Users size={14} className="text-gray-400" />
                    <span>
                      {group.member_count} {group.member_count === 1 ? "Member" : "Members"}
                    </span>
                  </span>
                  <span className="text-[11px] text-gray-400 font-mono">
                    {new Date(group.created_at).toLocaleDateString([], {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowCreateModal(false)}
          title="Create Employee Group"
          description="Group team members for collaborative assistant access and department workflows."
          maxWidth="md"
        >
          <form onSubmit={handleCreate} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Group Name *
              </label>
              <Input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. AI Prompt Engineers or Customer Success"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Associated Department (Optional)
              </label>
              <select
                value={departmentId}
                onChange={(e) => setDepartmentId(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="">No Department (Workspace-wide)</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Description (Optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of this group..."
                rows={3}
                className="w-full px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-gray-100">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setShowCreateModal(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                isLoading={submitting}
              >
                Create Group
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
