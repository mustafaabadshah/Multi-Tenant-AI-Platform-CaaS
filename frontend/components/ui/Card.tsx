"use client";

import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = "",
  hoverable = false,
  ...props
}) => {
  return (
    <div
      className={`bg-white border border-gray-200 rounded-lg p-6 ${
        hoverable ? "hover:border-gray-300 hover:shadow-sm transition-all" : ""
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export default Card;
