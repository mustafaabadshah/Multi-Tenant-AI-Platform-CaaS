"use client";

import React from "react";

export interface StatusIndicatorProps {
  status: "active" | "inactive" | "pending" | "error" | "processing";
  label?: string;
  pulse?: boolean;
  className?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  label,
  pulse = false,
  className = "",
}) => {
  const statusStyles = {
    active: {
      dot: "bg-emerald-500",
      text: "text-emerald-700",
      pill: "bg-emerald-50 border-emerald-200",
      defaultLabel: "Active",
    },
    inactive: {
      dot: "bg-gray-400",
      text: "text-gray-600",
      pill: "bg-gray-50 border-gray-200",
      defaultLabel: "Inactive",
    },
    pending: {
      dot: "bg-amber-500",
      text: "text-amber-700",
      pill: "bg-amber-50 border-amber-200",
      defaultLabel: "Pending",
    },
    error: {
      dot: "bg-red-500",
      text: "text-red-700",
      pill: "bg-red-50 border-red-200",
      defaultLabel: "Error",
    },
    processing: {
      dot: "bg-blue-500",
      text: "text-blue-700",
      pill: "bg-blue-50 border-blue-200",
      defaultLabel: "Processing",
    },
  };

  const current = statusStyles[status] || statusStyles.inactive;
  const displayLabel = label || current.defaultLabel;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${current.pill} ${current.text} ${className}`}
    >
      <span className="relative flex h-2 w-2">
        {pulse && (
          <span
            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${current.dot}`}
          />
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${current.dot}`} />
      </span>
      <span>{displayLabel}</span>
    </span>
  );
};

export default StatusIndicator;
