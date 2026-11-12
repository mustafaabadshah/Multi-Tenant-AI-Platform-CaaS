"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  DocumentChunkItem,
  DocumentContentItem,
  DocumentItem,
  IngestionConfigItem,
  IngestionEventItem,
  KnowledgeBaseItem,
} from "@/lib/api";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Copy,
  Database,
  Edit3,
  FileCode,
  FileSpreadsheet,
  FileText,
  Globe,
  History,
  Layers,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Sliders,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import RetrievalSettingsTab from "./RetrievalSettingsTab";
import RetrievalPreviewTab from "./RetrievalPreviewTab";
import IndexStatusTab from "./IndexStatusTab";

export default function KnowledgePage() {
  const { activeWorkspace } = useAuth();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKB, setSelectedKB] = useState<KnowledgeBaseItem | null>(null);
  const [kbTab, setKbTab] = useState<"documents" | "retrieval" | "preview" | "index">("documents");

  // Create KB Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [kbName, setKbName] = useState("");
  const [kbDescription, setKbDescription] = useState("");
  const [submittingKB, setSubmittingKB] = useState(false);
  const [kbError, setKbError] = useState<string | null>(null);

  // Edit KB Modal State
  const [showEditModal, setShowEditModal] = useState(false);
  const [editKbName, setEditKbName] = useState("");
  const [editKbDescription, setEditKbDescription] = useState("");
  const [savingEditKB, setSavingEditKB] = useState(false);
  const [editKbError, setEditKbError] = useState<string | null>(null);

  // KB Documents State
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [docSearch, setDocSearch] = useState("");

  // Upload State
  const [isDragging, setIsDragging] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // URL Ingestion State
  const [showUrlModal, setShowUrlModal] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [urlSubmitting, setUrlSubmitting] = useState(false);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [urlSuccess, setUrlSuccess] = useState<string | null>(null);

  // Document Details & Inspection Modal
  const [inspectedDoc, setInspectedDoc] = useState<DocumentItem | null>(null);
  const [docDetailTab, setDocDetailTab] = useState<"overview" | "content" | "chunks" | "history">("overview");
  const [docContent, setDocContent] = useState<DocumentContentItem | null>(null);
  const [docChunks, setDocChunks] = useState<DocumentChunkItem[]>([]);
  const [docHistory, setDocHistory] = useState<IngestionEventItem[]>([]);
  const [loadingDocDetails, setLoadingDocDetails] = useState(false);
  const [copiedText, setCopiedText] = useState(false);

  // Ingestion Config Modal
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [ingestionConfig, setIngestionConfig] = useState<IngestionConfigItem | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);
  const [configSuccess, setConfigSuccess] = useState(false);

  // Load KBs
  const loadKBs = useCallback(async () => {
    if (!activeWorkspace) return;
    setLoading(true);
    try {
      const data = await api.listKnowledgeBases();
      setKnowledgeBases(data);
      if (selectedKB) {
        const refreshed = data.find((k) => k.id === selectedKB.id);
        if (refreshed) setSelectedKB(refreshed);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [activeWorkspace, selectedKB]);

  // Load Documents for selected KB
  const loadDocuments = useCallback(async (kbId: string) => {
    setLoadingDocs(true);
    try {
      const docs = await api.listDocuments(kbId);
      setDocuments(docs);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    loadKBs();
  }, [activeWorkspace, loadKBs]);

  useEffect(() => {
    if (selectedKB) {
      loadDocuments(selectedKB.id);
    }
  }, [selectedKB, loadDocuments]);

  // Auto-poll if any documents are in QUEUED or PROCESSING state
  useEffect(() => {
    if (!selectedKB) return;
    const hasActiveJobs = documents.some((d) => d.status === "QUEUED" || d.status === "PROCESSING");
    if (!hasActiveJobs) return;

    const interval = setInterval(() => {
      api.listDocuments(selectedKB.id).then((docs) => {
        setDocuments(docs);
      }).catch(console.error);
    }, 2500);

    return () => clearInterval(interval);
  }, [selectedKB, documents]);

  // Handle Create KB
  const handleCreateKB = async (e: React.FormEvent) => {
    e.preventDefault();
    setKbError(null);
    setSubmittingKB(true);
    try {
      await api.createKnowledgeBase({
        name: kbName.trim(),
        description: kbDescription.trim() || undefined,
      });
      setShowCreateModal(false);
      setKbName("");
      setKbDescription("");
      await loadKBs();
    } catch (err: unknown) {
      setKbError(err instanceof Error ? err.message : "Failed to create knowledge base");
    } finally {
      setSubmittingKB(false);
    }
  };

  // Handle Edit KB
  const handleOpenEditKB = () => {
    if (!selectedKB) return;
    setEditKbName(selectedKB.name);
    setEditKbDescription(selectedKB.description || "");
    setEditKbError(null);
    setShowEditModal(true);
  };

  const handleSaveEditKB = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedKB || !editKbName.trim()) return;
    setSavingEditKB(true);
    setEditKbError(null);
    try {
      const updated = await api.updateKnowledgeBase(selectedKB.id, {
        name: editKbName.trim(),
        description: editKbDescription.trim() || undefined,
      });
      setSelectedKB(updated);
      setShowEditModal(false);
      await loadKBs();
    } catch (err: unknown) {
      setEditKbError(err instanceof Error ? err.message : "Failed to update knowledge base");
    } finally {
      setSavingEditKB(false);
    }
  };

  // Handle Delete KB
  const handleDeleteKB = async () => {
    if (!selectedKB) return;
    if (!confirm(`Are you sure you want to permanently delete knowledge base "${selectedKB.name}"? All associated documents and chunks will be removed.`)) return;
    try {
      await api.deleteKnowledgeBase(selectedKB.id);
      setSelectedKB(null);
      await loadKBs();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete knowledge base");
    }
  };

  // Handle File Selection
  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setUploadFiles(Array.from(e.dataTransfer.files));
      setUploadError(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setUploadFiles(Array.from(e.target.files));
      setUploadError(null);
    }
  };

  // Upload Documents
  const handleUpload = async () => {
    if (!selectedKB || uploadFiles.length === 0) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const results = await api.uploadDocuments(selectedKB.id, uploadFiles);
      setUploadSuccess(`Successfully queued ${results.length} document(s) for ingestion.`);
      setUploadFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadDocuments(selectedKB.id);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Failed to upload documents.");
    } finally {
      setUploading(false);
    }
  };

  // Inspect Document
  const handleInspectDoc = async (doc: DocumentItem) => {
    setInspectedDoc(doc);
    setDocDetailTab("overview");
    setLoadingDocDetails(true);

    try {
      const [content, chunks, history] = await Promise.all([
        api.getDocumentContent(doc.id).catch(() => null),
        api.getDocumentChunks(doc.id).catch(() => []),
        api.getDocumentHistory(doc.id).catch(() => []),
      ]);
      setDocContent(content);
      setDocChunks(chunks);
      setDocHistory(history);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingDocDetails(false);
    }
  };

  // Reprocess Document
  const handleReprocessDoc = async (docId: string) => {
    try {
      await api.reprocessDocument(docId);
      if (selectedKB) await loadDocuments(selectedKB.id);
      if (inspectedDoc && inspectedDoc.id === docId) {
        await handleInspectDoc(inspectedDoc);
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to trigger reprocessing.");
    }
  };

  // Delete Document
  const handleDeleteDoc = async (docId: string, filename: string) => {
    if (!confirm(`Are you sure you want to permanently delete '${filename}' and all its extracted chunks?`)) return;
    try {
      await api.deleteDocument(docId);
      if (selectedKB) await loadDocuments(selectedKB.id);
      if (inspectedDoc && inspectedDoc.id === docId) setInspectedDoc(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete document.");
    }
  };

  // Open Ingestion Config
  const handleOpenConfig = async () => {
    if (!selectedKB) return;
    try {
      const cfg = await api.getIngestionConfig(selectedKB.id);
      setIngestionConfig(cfg);
      setShowConfigModal(true);
      setConfigSuccess(false);
    } catch (err) {
      console.error(err);
    }
  };

  // Save Ingestion Config
  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedKB || !ingestionConfig) return;
    setSavingConfig(true);
    try {
      const updated = await api.updateIngestionConfig(selectedKB.id, ingestionConfig);
      setIngestionConfig(updated);
      setConfigSuccess(true);
      setTimeout(() => setShowConfigModal(false), 1200);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update configuration.");
    } finally {
      setSavingConfig(false);
    }
  };

  // Helper for status badge
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3" />
            COMPLETED
          </span>
        );
      case "PROCESSING":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
            <Loader2 className="w-3 h-3 animate-spin" />
            PROCESSING
          </span>
        );
      case "QUEUED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3" />
            QUEUED
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-red-50 text-red-700 border border-red-200">
            <AlertCircle className="w-3 h-3" />
            FAILED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-gray-100 text-gray-700">
            {status}
          </span>
        );
    }
  };

  const getFormatIcon = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase();
    if (ext === "pdf") return <FileText className="w-4 h-4 text-red-500" />;
    if (["docx", "doc"].includes(ext || "")) return <FileText className="w-4 h-4 text-blue-500" />;
    if (["xlsx", "xls", "csv", "tsv"].includes(ext || "")) return <FileSpreadsheet className="w-4 h-4 text-emerald-600" />;
    if (["sql", "ddl", "json", "jsonl"].includes(ext || "")) return <FileCode className="w-4 h-4 text-amber-600" />;
    return <FileText className="w-4 h-4 text-gray-500" />;
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const filteredDocs = documents.filter((d) =>
    d.filename.toLowerCase().includes(docSearch.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl pb-16">
      {/* View 1: Knowledge Bases Grid View (if no KB selected) */}
      {!selectedKB ? (
        <>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-gray-900 tracking-tight flex items-center gap-2.5">
                <Database className="w-6 h-6 text-amber-600" />
                <span>Knowledge Bases</span>
              </h1>
              <p className="text-xs text-gray-500 mt-1">
                Multi-tenant knowledge containers with automated document parsing, OCR, and chunking.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-medium text-xs shadow-xs flex items-center gap-2 transition cursor-pointer self-start"
            >
              <Plus className="w-4 h-4" />
              <span>New Knowledge Base</span>
            </button>
          </div>

          {loading ? (
            <div className="p-16 text-center text-xs text-gray-500">Loading knowledge collections...</div>
          ) : knowledgeBases.length === 0 ? (
            <div className="p-16 text-center border border-dashed border-gray-200 rounded-2xl bg-gray-50">
              <Database className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-gray-900">No Knowledge Bases created yet</h3>
              <p className="text-xs text-gray-500 mt-1 max-w-md mx-auto">
                Create your first knowledge container to ingest PDFs, Office docs, spreadsheets, slides, and SQL files.
              </p>
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="mt-4 px-4 py-2 rounded-xl bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 text-xs font-medium transition cursor-pointer inline-flex items-center gap-2 shadow-xs"
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
                  onClick={() => setSelectedKB(kb)}
                  className="p-5 rounded-2xl bg-white border border-gray-200 flex flex-col justify-between hover:border-amber-500/50 hover:shadow-md transition cursor-pointer group shadow-xs"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
                        <Database className="w-5 h-5" />
                      </div>
                      <span className="text-[11px] font-mono text-gray-500">
                        {new Date(kb.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <h3 className="text-sm font-bold text-gray-900 tracking-tight group-hover:text-amber-600 transition">
                      {kb.name}
                    </h3>
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                      {kb.description || "No description provided."}
                    </p>
                  </div>

                  <div className="pt-4 mt-4 border-t border-gray-100 flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-gray-600 font-medium">
                      <FileText className="w-3.5 h-3.5 text-amber-600" />
                      <span>{kb.document_count} Documents</span>
                    </span>
                    <span className="text-amber-600 text-xs font-semibold group-hover:translate-x-0.5 transition inline-flex items-center gap-1">
                      Manage &rarr;
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        /* View 2: Knowledge Base Detailed View with Documents & Uploader */
        <div className="space-y-6">
          {/* Top Breadcrumb & Actions Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setSelectedKB(null)}
                className="p-2 rounded-xl bg-white hover:bg-gray-50 text-gray-600 hover:text-gray-900 border border-gray-200 transition cursor-pointer shadow-xs"
                title="Back to all Knowledge Bases"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Knowledge Bases</span>
                  <span className="text-xs text-gray-400">/</span>
                  <h1 className="text-lg font-bold text-gray-900 tracking-tight">{selectedKB.name}</h1>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  {selectedKB.description || "Ingest and process documents for RAG answers."}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleOpenEditKB}
                className="px-3 py-2 rounded-xl bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer shadow-xs"
                title="Rename or update description"
              >
                <Edit3 className="w-3.5 h-3.5 text-amber-600" />
                <span>Rename / Edit</span>
              </button>
              <button
                type="button"
                onClick={handleOpenConfig}
                className="px-3.5 py-2 rounded-xl bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 text-xs font-medium flex items-center gap-2 transition cursor-pointer shadow-xs"
              >
                <Sliders className="w-3.5 h-3.5 text-amber-600" />
                <span>Pipeline Config</span>
              </button>
              <button
                type="button"
                onClick={() => loadDocuments(selectedKB.id)}
                className="p-2 rounded-xl bg-white hover:bg-gray-50 border border-gray-200 text-gray-600 hover:text-gray-900 transition cursor-pointer shadow-xs"
                title="Refresh Documents"
              >
                <RefreshCw className={`w-4 h-4 ${loadingDocs ? "animate-spin text-amber-600" : ""}`} />
              </button>
              <button
                type="button"
                onClick={handleDeleteKB}
                className="p-2 rounded-xl bg-white hover:bg-red-50 border border-gray-200 hover:border-red-200 text-gray-500 hover:text-red-600 transition cursor-pointer shadow-xs"
                title="Delete Knowledge Base"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Milestone 03 Segmented Tab Bar */}
          <div className="flex border-b border-gray-200 gap-6 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setKbTab("documents")}
              className={`py-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                kbTab === "documents"
                  ? "border-amber-600 text-amber-600"
                  : "border-transparent text-gray-500 hover:text-gray-800"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Documents ({documents.length})</span>
            </button>
            <button
              type="button"
              onClick={() => setKbTab("retrieval")}
              className={`py-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                kbTab === "retrieval"
                  ? "border-amber-600 text-amber-600"
                  : "border-transparent text-gray-500 hover:text-gray-800"
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Retrieval & Vectors</span>
            </button>
            <button
              type="button"
              onClick={() => setKbTab("preview")}
              className={`py-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                kbTab === "preview"
                  ? "border-amber-600 text-amber-600"
                  : "border-transparent text-gray-500 hover:text-gray-800"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Search Sandbox</span>
            </button>
            <button
              type="button"
              onClick={() => setKbTab("index")}
              className={`py-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                kbTab === "index"
                  ? "border-amber-600 text-amber-600"
                  : "border-transparent text-gray-500 hover:text-gray-800"
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              <span>Index Status</span>
            </button>
          </div>

          {kbTab === "documents" && (
            <>
              {/* Drag & Drop Upload Dropzone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleFileDrop}
                className={`p-8 rounded-2xl border-2 border-dashed transition text-center shadow-xs ${
                  isDragging
                    ? "border-amber-500 bg-amber-50/50 shadow-sm"
                    : "border-gray-200 bg-gray-50/80 hover:border-gray-300"
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  multiple
                  onChange={handleFileChange}
                  accept=".pdf,.docx,.xlsx,.xlsm,.pptx,.csv,.tsv,.json,.jsonl,.sql,.ddl,.txt,.md"
                  className="hidden"
                />
                <div className="w-12 h-12 rounded-2xl bg-amber-100/60 text-amber-600 flex items-center justify-center mx-auto mb-3 shadow-inner">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <h3 className="text-sm font-bold text-gray-900">
                  Drag & drop document files here, or{" "}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="text-amber-600 hover:underline cursor-pointer font-semibold"
                  >
                    browse files
                  </button>
                </h3>
                <p className="text-xs text-gray-500 mt-1">
                  Supports PDF, DOCX, XLSX, PPTX, CSV, JSON, SQL, TXT, and Markdown (max 50 MB per file)
                </p>

                {uploadFiles.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200 max-w-lg mx-auto space-y-2">
                    <div className="text-xs font-semibold text-gray-700 text-left">
                      {uploadFiles.length} file(s) selected for ingestion:
                    </div>
                    <div className="max-h-36 overflow-y-auto space-y-1.5 text-left">
                      {uploadFiles.map((f, i) => (
                        <div
                          key={i}
                          className="px-3 py-1.5 rounded-lg bg-white border border-gray-200 text-xs flex items-center justify-between"
                        >
                          <span className="text-gray-900 font-mono truncate max-w-xs">{f.name}</span>
                          <span className="text-gray-500 text-[11px] font-mono">{formatBytes(f.size)}</span>
                        </div>
                      ))}
                    </div>
                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setUploadFiles([])}
                        className="px-3 py-1.5 rounded-lg text-gray-500 hover:text-gray-700 text-xs transition cursor-pointer"
                      >
                        Clear
                      </button>
                      <button
                        type="button"
                        onClick={handleUpload}
                        disabled={uploading}
                        className="px-4 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-medium text-xs transition cursor-pointer disabled:opacity-50 inline-flex items-center gap-1.5 shadow-xs"
                      >
                        {uploading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                        <span>{uploading ? "Ingesting..." : "Upload & Ingest"}</span>
                      </button>
                    </div>
                  </div>
                )}

                {uploadError && (
                  <div className="mt-3 p-2.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs max-w-md mx-auto">
                    {uploadError}
                  </div>
                )}
                {uploadSuccess && (
                  <div className="mt-3 p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs max-w-md mx-auto">
                    {uploadSuccess}
                  </div>
                )}
              </div>

              {/* Documents Table View */}
              <div className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <h2 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-amber-600" />
                    <span>Documents ({documents.length})</span>
                  </h2>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setUrlInput("");
                        setUrlError(null);
                        setUrlSuccess(null);
                        setShowUrlModal(true);
                      }}
                      className="px-3 py-1.5 rounded-xl border border-gray-200 hover:border-gray-300 bg-white text-gray-700 text-xs font-medium transition flex items-center gap-1.5 cursor-pointer shrink-0 shadow-xs"
                    >
                      <Globe className="w-3.5 h-3.5 text-blue-600" />
                      <span>Ingest Web Page</span>
                    </button>
                    <div className="relative max-w-xs w-full">
                      <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                      <input
                        type="text"
                        placeholder="Filter documents..."
                        value={docSearch}
                        onChange={(e) => setDocSearch(e.target.value)}
                        className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-white border border-gray-300 text-gray-900 text-xs focus:border-amber-500 outline-none"
                      />
                    </div>
                  </div>
                </div>

                {loadingDocs ? (
                  <div className="p-12 text-center text-xs text-gray-500">Loading documents...</div>
                ) : filteredDocs.length === 0 ? (
                  <div className="p-12 text-center border border-dashed border-gray-200 rounded-2xl bg-gray-50 text-xs text-gray-500">
                    No documents found in this knowledge base. Upload your first document above.
                  </div>
                ) : (
                  <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-xs">
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-gray-50/80 border-b border-gray-200 text-gray-500 font-semibold uppercase tracking-wider text-[11px]">
                          <tr>
                            <th className="py-3 px-4">Document</th>
                            <th className="py-3 px-4">Size</th>
                            <th className="py-3 px-4">Status</th>
                            <th className="py-3 px-4 text-center">Pages</th>
                            <th className="py-3 px-4 text-center">Chunks</th>
                            <th className="py-3 px-4">Uploaded</th>
                            <th className="py-3 px-4 text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100 text-gray-700">
                          {filteredDocs.map((doc) => (
                            <tr key={doc.id} className="hover:bg-gray-50 transition">
                              <td className="py-3 px-4 font-medium text-gray-900 flex items-center gap-2.5">
                                {getFormatIcon(doc.filename)}
                                <span className="truncate max-w-sm" title={doc.filename}>
                                  {doc.filename}
                                </span>
                              </td>
                              <td className="py-3 px-4 font-mono text-gray-500 text-[11px]">
                                {formatBytes(doc.file_size)}
                              </td>
                              <td className="py-3 px-4">{getStatusBadge(doc.status)}</td>
                              <td className="py-3 px-4 text-center font-mono">{doc.total_pages || "—"}</td>
                              <td className="py-3 px-4 text-center font-mono font-semibold text-amber-600">
                                {doc.total_chunks || "—"}
                              </td>
                              <td className="py-3 px-4 text-gray-500 text-[11px] font-mono">
                                {new Date(doc.created_at).toLocaleDateString()}
                              </td>
                              <td className="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                                <button
                                  type="button"
                                  onClick={() => handleInspectDoc(doc)}
                                  className="px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-[11px] font-medium transition cursor-pointer"
                                >
                                  Inspect
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleReprocessDoc(doc.id)}
                                  className="p-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-900 transition cursor-pointer"
                                  title="Reprocess Document"
                                >
                                  <RefreshCw className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteDoc(doc.id, doc.filename)}
                                  className="p-1 rounded-lg bg-gray-100 hover:bg-red-50 hover:text-red-600 text-gray-400 transition cursor-pointer"
                                  title="Delete Document"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

      {kbTab === "retrieval" && (
        <RetrievalSettingsTab
          kbId={selectedKB.id}
          onConfigSaved={() => loadDocuments(selectedKB.id)}
        />
      )}

      {kbTab === "preview" && (
        <RetrievalPreviewTab
          kbId={selectedKB.id}
          kbName={selectedKB.name}
        />
      )}

      {kbTab === "index" && (
        <IndexStatusTab
          kbId={selectedKB.id}
          kbName={selectedKB.name}
        />
      )}
    </div>
  )}

      {/* Document Details & Inspection Modal */}
      {inspectedDoc && (
        <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-2xl max-w-4xl w-full max-h-[88vh] flex flex-col shadow-2xl animate-fadeIn">
            {/* Modal Header */}
            <div className="p-5 border-b border-gray-200 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                  {getFormatIcon(inspectedDoc.filename)}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-900 tracking-tight">{inspectedDoc.filename}</h3>
                  <div className="flex items-center gap-2 mt-0.5">
                    {getStatusBadge(inspectedDoc.status)}
                    <span className="text-[11px] text-gray-500 font-mono">
                      {formatBytes(inspectedDoc.file_size)} &bull; Version {inspectedDoc.current_version_num}
                    </span>
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setInspectedDoc(null)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex border-b border-gray-200 px-5 gap-6 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setDocDetailTab("overview")}
                className={`py-3 border-b-2 transition cursor-pointer ${
                  docDetailTab === "overview"
                    ? "border-amber-600 text-amber-600"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                Overview
              </button>
              <button
                type="button"
                onClick={() => setDocDetailTab("content")}
                className={`py-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                  docDetailTab === "content"
                    ? "border-amber-600 text-amber-600"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Extracted Text</span>
              </button>
              <button
                type="button"
                onClick={() => setDocDetailTab("chunks")}
                className={`py-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                  docDetailTab === "chunks"
                    ? "border-amber-600 text-amber-600"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Chunks ({docChunks.length})</span>
              </button>
              <button
                type="button"
                onClick={() => setDocDetailTab("history")}
                className={`py-3 border-b-2 transition cursor-pointer flex items-center gap-1.5 ${
                  docDetailTab === "history"
                    ? "border-amber-600 text-amber-600"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                <History className="w-3.5 h-3.5" />
                <span>Processing History ({docHistory.length})</span>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-1 text-xs">
              {loadingDocDetails ? (
                <div className="p-12 text-center text-gray-500 flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
                  <span>Loading document inspection details...</span>
                </div>
              ) : (
                <>
                  {/* Tab 1: Overview */}
                  {docDetailTab === "overview" && (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                          <span className="text-[11px] text-gray-500 block">MIME Type</span>
                          <span className="font-mono text-gray-900 text-xs font-semibold">{inspectedDoc.mime_type}</span>
                        </div>
                        <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                          <span className="text-[11px] text-gray-500 block">Pages / Sheets</span>
                          <span className="font-mono text-gray-900 text-xs font-semibold">{inspectedDoc.total_pages}</span>
                        </div>
                        <div className="p-3 rounded-xl bg-gray-50 border border-gray-200">
                          <span className="text-[11px] text-gray-500 block">Generated Chunks</span>
                          <span className="font-mono text-amber-600 text-xs font-bold">{inspectedDoc.total_chunks}</span>
                        </div>
                      </div>

                      <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-2">
                        <span className="text-gray-700 font-semibold block uppercase tracking-wider text-[11px]">
                          Cryptographic Checksum (SHA-256)
                        </span>
                        <code className="text-amber-800 font-mono text-[11px] break-all block bg-white p-2 rounded-lg border border-gray-200">
                          {inspectedDoc.file_hash || "No hash computed."}
                        </code>
                      </div>

                      <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-2">
                        <span className="text-gray-700 font-semibold block uppercase tracking-wider text-[11px]">
                          Internal Storage Path
                        </span>
                        <code className="text-gray-800 font-mono text-[11px] break-all block bg-white p-2 rounded-lg border border-gray-200">
                          {inspectedDoc.safe_filename} (Tenant-isolated storage volume)
                        </code>
                      </div>

                      <div className="flex justify-end gap-2 pt-2">
                        <button
                          type="button"
                          onClick={() => handleReprocessDoc(inspectedDoc.id)}
                          className="px-4 py-2 rounded-xl bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 font-medium transition cursor-pointer flex items-center gap-1.5 shadow-xs"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                          <span>Reprocess Document</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Tab 2: Extracted Content Preview */}
                  {docDetailTab === "content" && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500 text-xs">
                          {docContent?.extracted_text?.length || 0} characters extracted
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            if (docContent?.extracted_text) {
                              navigator.clipboard.writeText(docContent.extracted_text);
                              setCopiedText(true);
                              setTimeout(() => setCopiedText(false), 2000);
                            }
                          }}
                          className="px-2.5 py-1 rounded-lg bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 text-[11px] flex items-center gap-1 transition cursor-pointer shadow-xs"
                        >
                          <Copy className="w-3 h-3" />
                          <span>{copiedText ? "Copied!" : "Copy Full Text"}</span>
                        </button>
                      </div>

                      <pre className="p-4 rounded-xl bg-gray-900 border border-gray-800 text-gray-100 font-mono text-xs max-h-96 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                        {docContent?.extracted_text || "No extracted text available for this document."}
                      </pre>
                    </div>
                  )}

                  {/* Tab 3: Chunks Inspector */}
                  {docDetailTab === "chunks" && (
                    <div className="space-y-3">
                      {docChunks.length === 0 ? (
                        <div className="p-8 text-center text-gray-500">
                          No chunks generated yet. Trigger reprocessing if parsing failed.
                        </div>
                      ) : (
                        docChunks.map((chunk) => (
                          <div
                            key={chunk.id}
                            className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-2 hover:border-gray-300 transition"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-mono text-amber-600 font-bold text-xs">
                                Chunk #{chunk.chunk_index}
                              </span>
                              <div className="flex items-center gap-2">
                                {chunk.heading_path && (
                                  <span className="px-2 py-0.5 rounded-md bg-white border border-gray-200 text-[11px] text-gray-700 font-medium">
                                    {chunk.heading_path}
                                  </span>
                                )}
                                {chunk.page_number && (
                                  <span className="px-2 py-0.5 rounded-md bg-white border border-gray-200 text-[11px] text-gray-500 font-mono">
                                    Page {chunk.page_number}
                                  </span>
                                )}
                                <span className="text-[11px] text-gray-500 font-mono">
                                  {chunk.character_count} chars &bull; ~{chunk.token_count} tokens
                                </span>
                              </div>
                            </div>
                            <p className="text-xs text-gray-800 font-mono whitespace-pre-wrap leading-relaxed bg-white p-3 rounded-lg border border-gray-200">
                              {chunk.content}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {/* Tab 4: Processing History Timeline */}
                  {docHistoryTabContent(docHistory)}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Ingestion Configuration Modal */}
      {showConfigModal && ingestionConfig && (
        <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-6 max-w-lg w-full shadow-2xl animate-fadeIn space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-200">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
                  <Sliders className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-900">Ingestion Pipeline Configuration</h3>
                  <p className="text-xs text-gray-500">Knowledge base chunking and OCR preferences</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowConfigModal(false)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-700 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {configSuccess && (
              <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs">
                Configuration updated successfully!
              </div>
            )}

            <form onSubmit={handleSaveConfig} className="space-y-4 text-xs">
              <div>
                <label className="block text-gray-700 font-medium mb-1">Chunking Strategy</label>
                <select
                  value={ingestionConfig.chunking_strategy}
                  onChange={(e) =>
                    setIngestionConfig({ ...ingestionConfig, chunking_strategy: e.target.value })
                  }
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none"
                >
                  <option value="recursive">Recursive Character (Paragraphs & Sentences)</option>
                  <option value="markdown">Markdown Header-Aware (Heading Paths)</option>
                  <option value="token">Token-Bounded (Strict Token Budgets)</option>
                  <option value="structured">Structured (Table Headers & Slide Context)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Chunk Size (Characters)</label>
                  <input
                    type="number"
                    min={100}
                    max={5000}
                    value={ingestionConfig.chunk_size}
                    onChange={(e) =>
                      setIngestionConfig({ ...ingestionConfig, chunk_size: parseInt(e.target.value) || 1000 })
                    }
                    className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Chunk Overlap</label>
                  <input
                    type="number"
                    min={0}
                    max={1000}
                    value={ingestionConfig.chunk_overlap}
                    onChange={(e) =>
                      setIngestionConfig({ ...ingestionConfig, chunk_overlap: parseInt(e.target.value) || 200 })
                    }
                    className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none font-mono"
                  />
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-gray-50 border border-gray-200 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-gray-900 font-semibold block">Enable OCR for Scanned Pages</span>
                    <span className="text-[11px] text-gray-500 block">Extract text from scanned PDF images</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={ingestionConfig.ocr_enabled}
                    onChange={(e) =>
                      setIngestionConfig({ ...ingestionConfig, ocr_enabled: e.target.checked })
                    }
                    className="w-4 h-4 accent-amber-600 cursor-pointer"
                  />
                </div>

                {ingestionConfig.ocr_enabled && (
                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-200">
                    <div>
                      <label className="block text-gray-600 text-[11px] mb-1">OCR Provider</label>
                      <select
                        value={ingestionConfig.ocr_provider}
                        onChange={(e) =>
                          setIngestionConfig({ ...ingestionConfig, ocr_provider: e.target.value })
                        }
                        className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-900 outline-none text-xs"
                      >
                        <option value="tesseract">Tesseract (Local CPU Fallback)</option>
                        <option value="badho">Badho OCR (Cloud Integration)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-gray-600 text-[11px] mb-1">Language</label>
                      <input
                        type="text"
                        value={ingestionConfig.ocr_language}
                        onChange={(e) =>
                          setIngestionConfig({ ...ingestionConfig, ocr_language: e.target.value })
                        }
                        placeholder="e.g. eng, fra, deu"
                        className="w-full px-2.5 py-1.5 rounded-lg bg-white border border-gray-300 text-gray-900 outline-none text-xs font-mono"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowConfigModal(false)}
                  className="px-3 py-1.5 rounded-xl text-gray-600 hover:text-gray-900 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingConfig}
                  className="px-4 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-medium transition cursor-pointer disabled:opacity-50 shadow-xs"
                >
                  {savingConfig ? "Saving..." : "Save Preferences"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Knowledge Base Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-gray-900">Create Knowledge Base</h3>
                <p className="text-xs text-gray-500">Container for indexed documents</p>
              </div>
            </div>

            {kbError && (
              <div className="mb-4 p-2.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
                {kbError}
              </div>
            )}

            <form onSubmit={handleCreateKB} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-gray-700 font-medium mb-1">Knowledge Base Name</label>
                <input
                  type="text"
                  required
                  value={kbName}
                  onChange={(e) => setKbName(e.target.value)}
                  placeholder="e.g. Employee Handbook 2026, Technical Specs, Financials"
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Description (Optional)</label>
                <textarea
                  rows={3}
                  value={kbDescription}
                  onChange={(e) => setKbDescription(e.target.value)}
                  placeholder="Describe the scope and documents in this collection..."
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-2 rounded-xl text-gray-600 hover:text-gray-900 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingKB}
                  className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-medium transition cursor-pointer disabled:opacity-50 shadow-xs"
                >
                  {submittingKB ? "Creating..." : "Save Container"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit / Rename Knowledge Base Modal */}
      {showEditModal && selectedKB && (
        <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                <Edit3 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-gray-900">Rename / Edit Knowledge Base</h3>
                <p className="text-xs text-gray-500">Update collection name and metadata</p>
              </div>
            </div>

            {editKbError && (
              <div className="mb-4 p-2.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs">
                {editKbError}
              </div>
            )}

            <form onSubmit={handleSaveEditKB} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-gray-700 font-medium mb-1">Knowledge Base Name</label>
                <input
                  type="text"
                  required
                  value={editKbName}
                  onChange={(e) => setEditKbName(e.target.value)}
                  placeholder="e.g. Employee Handbook 2026, Technical Specs"
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Description (Optional)</label>
                <textarea
                  rows={3}
                  value={editKbDescription}
                  onChange={(e) => setEditKbDescription(e.target.value)}
                  placeholder="Describe the scope and documents in this collection..."
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 focus:border-amber-500 outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-3 py-2 rounded-xl text-gray-600 hover:text-gray-900 transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingEditKB}
                  className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-medium transition cursor-pointer disabled:opacity-50 shadow-xs"
                >
                  {savingEditKB ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Safe URL Ingestion Modal */}
      {showUrlModal && selectedKB && (
        <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fadeIn space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-200">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Globe className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-gray-900">Ingest Public Web Page</h3>
                  <p className="text-xs text-gray-500">Extracts documentation with strict SSRF defenses</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowUrlModal(false)}
                className="text-gray-400 hover:text-gray-700 transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {urlSuccess && (
              <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{urlSuccess}</span>
              </div>
            )}

            {urlError && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                <span>{urlError}</span>
              </div>
            )}

            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (!selectedKB || !urlInput.trim()) return;
                setUrlSubmitting(true);
                setUrlError(null);
                setUrlSuccess(null);
                try {
                  await api.ingestDocumentUrl(selectedKB.id, urlInput.trim());
                  setUrlSuccess("Web page fetched and scheduled for ingestion!");
                  setUrlInput("");
                  setTimeout(() => {
                    setShowUrlModal(false);
                    setUrlSuccess(null);
                  }, 1200);
                  await loadDocuments(selectedKB.id);
                } catch (err) {
                  setUrlError(err instanceof Error ? err.message : "Failed to ingest URL");
                } finally {
                  setUrlSubmitting(false);
                }
              }}
              className="space-y-3.5 text-xs"
            >
              <div>
                <label className="block text-gray-700 font-medium mb-1">Target URL</label>
                <input
                  type="url"
                  required
                  placeholder="https://docs.example.com/api/v1/overview"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white border border-gray-300 text-gray-900 font-mono text-xs focus:border-blue-500 outline-none"
                />
              </div>

              <div className="p-3 rounded-xl bg-gray-50 border border-gray-200 text-[11px] text-gray-600 space-y-1">
                <span className="font-semibold text-gray-800 block">Security Guardrails:</span>
                <p>Private IP ranges (RFC 1918), link-local addresses, and cloud metadata (169.254.169.254) are strictly blocked.</p>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUrlModal(false)}
                  className="px-3.5 py-2 rounded-xl border border-gray-200 hover:border-gray-300 bg-white text-gray-700 text-xs font-medium cursor-pointer shadow-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={urlSubmitting || !urlInput.trim()}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {urlSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{urlSubmitting ? "Fetching..." : "Fetch & Ingest"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function docHistoryTabContent(docHistory: IngestionEventItem[]) {
  return (
    <div className="space-y-3">
      {docHistory.length === 0 ? (
        <div className="p-8 text-center text-gray-500">No processing history recorded.</div>
      ) : (
        <div className="relative pl-6 space-y-4 border-l border-gray-200 ml-2">
          {docHistory.map((evt) => (
            <div key={evt.id} className="relative group">
              <div
                className={`absolute -left-[31px] top-0.5 w-3.5 h-3.5 rounded-full border-2 ${
                  evt.status === "COMPLETED"
                    ? "bg-emerald-500 border-white"
                    : evt.status === "FAILED"
                    ? "bg-red-500 border-white"
                    : "bg-blue-500 border-white"
                }`}
              />
              <div className="p-3 rounded-xl bg-gray-50 border border-gray-200 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-gray-900 text-xs">{evt.stage}</span>
                  <span className="text-[11px] text-gray-500 font-mono">
                    {new Date(evt.created_at).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-gray-700 text-xs">{evt.message}</p>
                {evt.details && Object.keys(evt.details).length > 0 && (
                  <pre className="text-[11px] text-gray-800 font-mono bg-white border border-gray-200 p-2 rounded-lg mt-1 overflow-x-auto">
                    {JSON.stringify(evt.details, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
