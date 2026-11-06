"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { api, KnowledgeBaseItem } from "@/lib/api";
import { Database, Plus, FileText, FileSpreadsheet, FileCode, Image, UploadCloud, Info } from "lucide-react";

export default function KnowledgePage() {
  const { activeWorkspace } = useAuth();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal State
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadKBs = async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    try {
      const data = await api.listKnowledgeBases();
      setKnowledgeBases(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKBs();
  }, [activeWorkspace]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.createKnowledgeBase({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setShowModal(false);
      setName("");
      setDescription("");
      await loadKBs();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to create knowledge base");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const supportedFormats = [
    { ext: "PDF", label: "PDF Documents & Research Papers", icon: FileText },
    { ext: "DOCX", label: "Word & Office Documents", icon: FileText },
    { ext: "CSV / XLSX", label: "Spreadsheets & Tables", icon: FileSpreadsheet },
    { ext: "PPTX", label: "Presentations & Slides", icon: FileText },
    { ext: "JSON / SQL", label: "Structured Data & Database Dumps", icon: FileCode },
    { ext: "OCR / Images", label: "Scanned Papers & Images (Badho OCR / Local)", icon: Image },
  ];

  return (
    <div className="space-y-8 max-w-6xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Knowledge Bases</h1>
          <p className="text-xs text-slate-400 mt-1">
            Segment, curate, and index institutional documents for grounded RAG answers.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium text-xs shadow-lg shadow-amber-600/25 flex items-center gap-2 transition cursor-pointer self-start"
        >
          <Plus className="w-4 h-4" />
          <span>New Knowledge Base</span>
        </button>
      </div>

      {/* Active Knowledge Bases Grid */}
      {loading ? (
        <div className="p-12 text-center text-xs text-slate-400">Loading knowledge collections...</div>
      ) : knowledgeBases.length === 0 ? (
        <div className="p-16 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/30">
          <Database className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-200">No Knowledge Bases created yet</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            Create your first container to organize documents by department or subject matter.
          </p>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="mt-4 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer inline-flex items-center gap-2"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create Container</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {knowledgeBases.map((kb) => (
            <div
              key={kb.id}
              className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl flex flex-col justify-between hover:border-slate-700 transition"
            >
              <div>
                <div className="w-9 h-9 rounded-xl bg-amber-600/20 text-amber-400 flex items-center justify-center font-bold mb-3">
                  <Database className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-white tracking-tight">{kb.name}</h3>
                <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                  {kb.description || "No description provided."}
                </p>
              </div>

              <div className="pt-4 mt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5 text-slate-300">
                  <FileText className="w-3.5 h-3.5 text-amber-400" />
                  <span>{kb.document_count} Documents</span>
                </span>
                <span className="text-[11px] text-slate-500 font-mono">
                  {new Date(kb.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Extensibility & Phase 2 Ingestion Roadmap Preview */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl space-y-4">
        <div className="flex items-center gap-2 text-xs font-bold text-slate-200 uppercase tracking-wider">
          <UploadCloud className="w-4 h-4 text-blue-400" />
          <span>Multi-Format Ingestion Pipeline Architecture (Phase 2 Roadmap)</span>
        </div>
        <p className="text-xs text-slate-400">
          The database schema and foundation are built to support direct chunking, OCR, and vector indexing for the following formats:
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {supportedFormats.map((fmt, idx) => {
            const Icon = fmt.icon;
            return (
              <div
                key={idx}
                className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 flex items-center gap-3 text-xs"
              >
                <div className="w-8 h-8 rounded-lg bg-slate-900 text-slate-400 flex items-center justify-center shrink-0">
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <span className="font-semibold text-slate-200 block">{fmt.ext}</span>
                  <span className="text-[11px] text-slate-500 block truncate">{fmt.label}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-amber-600/20 text-amber-400 flex items-center justify-center">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-100">Create Knowledge Base</h3>
                <p className="text-xs text-slate-400">Container for indexed documents</p>
              </div>
            </div>

            {error && (
              <div className="mb-4 p-2.5 rounded-xl bg-red-950/60 border border-red-800 text-red-300 text-xs">
                {error}
              </div>
            )}

            <form onSubmit={handleCreate} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-300 font-medium mb-1">Knowledge Base Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Employee Handbook 2026, Q3 Financials, Course Notes"
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-amber-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">Description (Optional)</label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the scope and documents in this collection..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:border-amber-500 outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-2 rounded-xl text-slate-400 hover:text-slate-200 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium transition cursor-pointer disabled:opacity-50"
                >
                  {submitting ? "Creating..." : "Save Container"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
