"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, Department } from "@/lib/api";
import { Briefcase, Plus, Trash2, Users, Calendar } from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Modal from "@/components/ui/Modal";
import EmptyState from "@/components/ui/EmptyState";
import Spinner from "@/components/ui/Spinner";

export default function DepartmentsPage() {
  const { activeWorkspace } = useAuth();
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDepartments = async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    try {
      const data = await api.listDepartments();
      setDepartments(data);
    } catch (err) {
      console.error("Failed to load departments", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDepartments();
  }, [activeWorkspace]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.createDepartment({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setShowCreateModal(false);
      setName("");
      setDescription("");
      await loadDepartments();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to create department");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, deptName: string) => {
    if (!confirm(`Are you sure you want to delete department "${deptName}"?`)) return;
    try {
      await api.deleteDepartment(id);
      await loadDepartments();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete department");
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight">Departments</h1>
          <p className="text-sm text-gray-600 mt-1">
            Segment your organization into departments (HR, Finance, Legal, Engineering) for scoped knowledge bases.
          </p>
        </div>
        <Button
          onClick={() => setShowCreateModal(true)}
          icon={Plus}
          iconPosition="left"
          variant="primary"
          size="sm"
        >
          Create Department
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[300px]">
          <Spinner size="lg" />
        </div>
      ) : departments.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No departments configured"
          description="Departments allow you to assign specific document collections and AI assistants to particular business units."
          action={{
            label: "Create First Department",
            onClick: () => setShowCreateModal(true),
            icon: Plus,
          }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {departments.map((dept) => (
            <div
              key={dept.id}
              className="bg-white border border-gray-200 rounded-lg p-5 flex flex-col justify-between hover:border-gray-300 hover:shadow-xs transition-all"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="w-9 h-9 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
                    <Briefcase size={18} />
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(dept.id, dept.name)}
                    className="p-1.5 rounded-md text-gray-400 hover:text-red-600 hover:bg-gray-100 transition-colors"
                    title="Delete department"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
                <h3 className="text-sm font-semibold text-gray-900 tracking-tight">{dept.name}</h3>
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                  {dept.description || "No description provided."}
                </p>
              </div>

              <div className="pt-4 mt-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                <span className="flex items-center gap-1.5">
                  <Users size={14} className="text-gray-400" />
                  <span>
                    {dept.member_count} {dept.member_count === 1 ? "Member" : "Members"}
                  </span>
                </span>
                <span className="text-[11px] text-gray-400 font-mono">
                  {new Date(dept.created_at).toLocaleDateString([], {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowCreateModal(false)}
          title="Create Department"
          description="Add a new business unit for knowledge scoping and team organization."
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
                Department Name *
              </label>
              <Input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Legal & Compliance or Engineering"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Description (Optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Briefly describe the responsibilities of this unit..."
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
                Create Department
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
