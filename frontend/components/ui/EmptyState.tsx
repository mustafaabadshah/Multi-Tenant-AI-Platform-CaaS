"use client";

import React from "react";
import Button, { ButtonProps } from "./Button";

export interface EmptyStateProps {
  icon?: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: React.ComponentType<{ size?: number; className?: string }>;
    variant?: ButtonProps["variant"];
  };
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  action,
  className = "",
}) => {
  return (
    <div
      className={`text-center py-12 px-4 bg-white border border-gray-200 rounded-lg ${className}`}
    >
      {Icon && (
        <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-50 flex items-center justify-center text-gray-400">
          <Icon size={24} />
        </div>
      )}
      <h3 className="text-sm font-semibold text-gray-900 mb-1">{title}</h3>
      {description && <p className="text-xs text-gray-500 max-w-sm mx-auto mb-4">{description}</p>}
      {action && (
        <Button
          variant={action.variant || "primary"}
          size="sm"
          onClick={action.onClick}
          icon={action.icon}
        >
          {action.label}
        </Button>
      )}
    </div>
  );
};

export default EmptyState;
