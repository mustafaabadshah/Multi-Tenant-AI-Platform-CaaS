"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  BetaCohortResponseItem,
  FeedbackListItem,
} from "@/lib/api";
import {
  Users,
  Mail,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Filter,
  CheckCircle2,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";
import Badge from "@/components/ui/Badge";

export default function BetaOperationsPage() {
  const { activeWorkspace } = useAuth();

  const [cohortData, setCohortData] = useState<BetaCohortResponseItem | null>(null);
  const [feedbackStream, setFeedbackStream] = useState<FeedbackListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters for feedback stream
  const [ratingFilter, setRatingFilter] = useState<string>("ALL");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [updatingStatusId, setUpdatingStatusId] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setErrorMessage(null);
      const [cohort, stream] = await Promise.all([
        api.getBetaCohort(),
        api.listFeedbackStream({ limit: 100 }),
      ]);
      setCohortData(cohort);
      setFeedbackStream(stream);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load beta cohort operations data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [activeWorkspace?.tenant_id]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleUpdateStatus = async (feedbackId: string, newStatus: string) => {
    try {
      setUpdatingStatusId(feedbackId);
      const updated = await api.updateFeedbackStatus(feedbackId, { status: newStatus });
      setFeedbackStream((prev) =>
        prev.map((f) => (f.id === feedbackId ? { ...f, status: updated.status } : f))
      );
    } catch (err: any) {
      alert(err.message || "Failed to update feedback review status.");
    } finally {
      setUpdatingStatusId(null);
    }
  };

  // Filtered feedback stream
  const filteredFeedback = useMemo(() => {
    return feedbackStream.filter((item) => {
      if (ratingFilter !== "ALL" && item.rating !== ratingFilter) return false;
      if (categoryFilter !== "ALL" && item.category !== categoryFilter) return false;
      if (statusFilter !== "ALL" && item.status !== statusFilter) return false;
      return true;
    });
  }, [feedbackStream, ratingFilter, categoryFilter, statusFilter]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  const summary = cohortData?.summary;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-gray-900">Private Beta Operations</h1>
            <Badge variant="blue">M28 Quality Telemetry</Badge>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Monitor the 5-user controlled beta cohort, track invitation lifecycles, and audit user feedback in real time.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            icon={RefreshCw}
            disabled={refreshing}
            onClick={handleRefresh}
          >
            {refreshing ? "Refreshing..." : "Refresh Telemetry"}
          </Button>
        </div>
      </div>

      {errorMessage && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-center justify-between">
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage(null)} className="text-rose-500 hover:text-rose-700 font-bold">✕</button>
        </div>
      )}

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="p-4 bg-white border border-gray-200 rounded-2xl shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-400">Total Invited</span>
            <div className="text-xl font-bold text-gray-900 mt-1">{summary.total_invited}</div>
          </div>
          <div className="p-4 bg-white border border-gray-200 rounded-2xl shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-400">Pending Invites</span>
            <div className="text-xl font-bold text-amber-600 mt-1">{summary.pending_invitations}</div>
          </div>
          <div className="p-4 bg-white border border-gray-200 rounded-2xl shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-400">Active Testers</span>
            <div className="text-xl font-bold text-blue-600 mt-1">{summary.active_beta_members}</div>
          </div>
          <div className="p-4 bg-white border border-gray-200 rounded-2xl shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-400">Message Turns</span>
            <div className="text-xl font-bold text-gray-900 mt-1">{summary.total_conversation_turns}</div>
          </div>
          <div className="p-4 bg-white border border-gray-200 rounded-2xl shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-400">Total Feedback</span>
            <div className="text-xl font-bold text-gray-900 mt-1 flex items-center gap-1.5">
              <span>{summary.total_feedback_count}</span>
              <span className="text-xs font-normal text-gray-400">
                ({summary.positive_feedback_count}👍 / {summary.negative_feedback_count}👎)
              </span>
            </div>
          </div>
          <div className="p-4 bg-white border border-gray-200 rounded-2xl shadow-xs">
            <span className="text-[10px] uppercase font-bold text-gray-400">Satisfaction %</span>
            <div className="text-xl font-bold text-emerald-600 mt-1">
              {summary.satisfaction_rate !== null ? `${summary.satisfaction_rate}%` : "—"}
            </div>
            {summary.is_sparse_sample && (
              <span className="text-[9px] text-amber-600 font-medium block mt-0.5">Low sample size (&lt;5)</span>
            )}
          </div>
        </div>
      )}

      {/* Grid: Invited cohort & Active testers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Invitations Table */}
        <div className="bg-white border border-gray-200 rounded-2xl shadow-xs p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm text-gray-900 flex items-center gap-1.5">
              <Mail size={15} className="text-blue-600" />
              Invited Cohort ({cohortData?.invitations?.length || 0})
            </h3>
          </div>

          <div className="border border-gray-100 rounded-xl overflow-hidden text-xs max-h-56 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-gray-50 text-[11px] text-gray-500 border-b border-gray-100">
                <tr>
                  <th className="py-2 px-3">Email</th>
                  <th className="py-2 px-3">Role</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3 text-right">Expires</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-700">
                {cohortData?.invitations?.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50/50">
                    <td className="py-2 px-3 font-medium text-gray-900">{inv.email}</td>
                    <td className="py-2 px-3 text-gray-500">{inv.role_name}</td>
                    <td className="py-2 px-3">
                      {inv.is_accepted ? (
                        <Badge variant="green">Accepted</Badge>
                      ) : inv.is_expired ? (
                        <Badge variant="gray">Expired</Badge>
                      ) : inv.is_cancelled ? (
                        <Badge variant="red">Cancelled</Badge>
                      ) : (
                        <Badge variant="amber">Pending</Badge>
                      )}
                    </td>
                    <td className="py-2 px-3 text-right text-gray-400">
                      {new Date(inv.expires_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
                {(!cohortData?.invitations || cohortData.invitations.length === 0) && (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-gray-400">
                      No invitations found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Active Testers Table */}
        <div className="bg-white border border-gray-200 rounded-2xl shadow-xs p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm text-gray-900 flex items-center gap-1.5">
              <Users size={15} className="text-emerald-600" />
              Active Workspace Members ({cohortData?.members?.length || 0})
            </h3>
          </div>

          <div className="border border-gray-100 rounded-xl overflow-hidden text-xs max-h-56 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-gray-50 text-[11px] text-gray-500 border-b border-gray-100">
                <tr>
                  <th className="py-2 px-3">Name / Email</th>
                  <th className="py-2 px-3">Role</th>
                  <th className="py-2 px-3 text-center">Turns</th>
                  <th className="py-2 px-3 text-right">Ratings</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-700">
                {cohortData?.members?.map((m) => (
                  <tr key={m.user_id} className="hover:bg-gray-50/50">
                    <td className="py-2 px-3">
                      <div className="font-medium text-gray-900 truncate max-w-[140px]">{m.full_name}</div>
                      <div className="text-[10px] text-gray-400 truncate max-w-[140px]">{m.email}</div>
                    </td>
                    <td className="py-2 px-3 text-gray-500">{m.role_name}</td>
                    <td className="py-2 px-3 text-center font-semibold text-gray-800">{m.message_count}</td>
                    <td className="py-2 px-3 text-right font-semibold text-gray-800">{m.feedback_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Filterable Feedback Review Stream */}
      <div className="bg-white border border-gray-200 rounded-2xl shadow-xs p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-100 pb-4">
          <div>
            <h3 className="font-semibold text-base text-gray-900">User Message Feedback Stream</h3>
            <p className="text-xs text-gray-500">Live stream of qualitative ratings and category flags submitted by beta testers.</p>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <select
              value={ratingFilter}
              onChange={(e) => setRatingFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-gray-700 text-xs"
            >
              <option value="ALL">All Ratings</option>
              <option value="THUMBS_UP">Thumbs Up 👍</option>
              <option value="THUMBS_DOWN">Thumbs Down 👎</option>
            </select>

            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-gray-700 text-xs"
            >
              <option value="ALL">All Categories</option>
              <option value="ACCURACY">Accuracy</option>
              <option value="HALLUCINATION">Hallucination</option>
              <option value="HELPFULNESS">Helpfulness</option>
              <option value="INCOMPLETE">Incomplete</option>
              <option value="TONE">Tone</option>
              <option value="OTHER">Other</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-gray-700 text-xs"
            >
              <option value="ALL">All Review States</option>
              <option value="NEW">New</option>
              <option value="REVIEWED">Reviewed</option>
              <option value="ACTIONED">Actioned</option>
              <option value="CLOSED">Closed</option>
            </select>
          </div>
        </div>

        {/* Feedback Items Table */}
        <div className="border border-gray-100 rounded-xl overflow-hidden text-xs">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-50 text-[11px] text-gray-500 border-b border-gray-100">
              <tr>
                <th className="py-2.5 px-3">Rating</th>
                <th className="py-2.5 px-3">Category</th>
                <th className="py-2.5 px-3">Assistant</th>
                <th className="py-2.5 px-3">Message Snippet / Comment</th>
                <th className="py-2.5 px-3">Review Status</th>
                <th className="py-2.5 px-3 text-right">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-gray-700">
              {filteredFeedback.map((fb) => (
                <tr key={fb.id} className="hover:bg-gray-50/50">
                  <td className="py-2.5 px-3">
                    {fb.rating === "THUMBS_UP" ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200/60">
                        <ThumbsUp size={11} className="fill-current" /> Positive
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-rose-50 text-rose-700 font-semibold border border-rose-200/60">
                        <ThumbsDown size={11} className="fill-current" /> Negative
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-3 font-medium text-gray-800">
                    {fb.category || "—"}
                  </td>
                  <td className="py-2.5 px-3 text-gray-600 truncate max-w-[120px]">
                    {fb.assistant_name || "Assistant"}
                  </td>
                  <td className="py-2.5 px-3 max-w-sm">
                    {fb.comment && (
                      <div className="font-semibold text-gray-900 mb-0.5">
                        &quot;{fb.comment}&quot;
                      </div>
                    )}
                    <div className="text-gray-400 text-[11px] truncate">
                      {fb.message_content_snippet || "Message content"}
                    </div>
                  </td>
                  <td className="py-2.5 px-3">
                    <select
                      value={fb.status}
                      disabled={updatingStatusId === fb.id}
                      onChange={(e) => handleUpdateStatus(fb.id, e.target.value)}
                      className="px-2 py-1 bg-gray-50 border border-gray-200 rounded-md text-[11px] font-medium text-gray-700 cursor-pointer"
                    >
                      <option value="NEW">NEW</option>
                      <option value="REVIEWED">REVIEWED</option>
                      <option value="ACTIONED">ACTIONED</option>
                      <option value="CLOSED">CLOSED</option>
                    </select>
                  </td>
                  <td className="py-2.5 px-3 text-right text-gray-400">
                    {new Date(fb.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {filteredFeedback.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-gray-400">
                    No message feedback matching the selected filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
