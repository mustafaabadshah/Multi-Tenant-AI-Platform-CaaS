"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Bot, Lock, Mail, User, Building2, ArrowRight, ShieldCheck, UserCheck } from "lucide-react";

export default function RegisterPage() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isOrg, setIsOrg] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register({
        email,
        password,
        full_name: fullName,
        organization_name: isOrg && orgName.trim() ? orgName.trim() : undefined,
      });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to create account. Please verify your details.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-gray-50 text-gray-900 items-center justify-center p-4 selection:bg-blue-100 selection:text-blue-900">
      <div className="w-full max-w-md">
        {/* Brand Header */}
        <div className="flex flex-col items-center mb-8 text-center">
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 text-white shadow-sm mb-4">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Multi-Tenant AI Platform-CaaS
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Create an Enterprise or Individual AI Workspace
          </p>
        </div>

        {/* Register Card */}
        <div className="bg-white border border-gray-200 rounded-2xl p-7 shadow-sm">
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900">Get started in minutes</h2>
            <p className="text-xs text-gray-500 mt-1">
              Select your workspace type and configure your primary AI tenant.
            </p>
          </div>

          {error && (
            <div className="mb-5 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Full Name
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Alex Rivera"
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-white border border-gray-300 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 text-sm text-gray-900 placeholder:text-gray-400 transition outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Work Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@enterprise.com"
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-white border border-gray-300 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 text-sm text-gray-900 placeholder:text-gray-400 transition outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Password (min 8 characters)
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-white border border-gray-300 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 text-sm text-gray-900 placeholder:text-gray-400 transition outline-none"
                />
              </div>
            </div>

            {/* Workspace Type Selector */}
            <div className="pt-2">
              <label className="block text-xs font-medium text-gray-700 mb-2">
                Workspace Type
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setIsOrg(false)}
                  className={`p-3 rounded-xl border text-left transition flex flex-col gap-1 cursor-pointer ${
                    !isOrg
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 ring-1 ring-blue-600/20"
                      : "border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  <UserCheck className="w-4 h-4 text-blue-600" />
                  <span className="text-xs font-semibold">Individual</span>
                  <span className="text-[10px] text-gray-500">Personal AI sandbox</span>
                </button>

                <button
                  type="button"
                  onClick={() => setIsOrg(true)}
                  className={`p-3 rounded-xl border text-left transition flex flex-col gap-1 cursor-pointer ${
                    isOrg
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 ring-1 ring-blue-600/20"
                      : "border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  <Building2 className="w-4 h-4 text-blue-600" />
                  <span className="text-xs font-semibold">Organization</span>
                  <span className="text-[10px] text-gray-500">Team with departments</span>
                </button>
              </div>
            </div>

            {/* Organization Name Field (conditional) */}
            {isOrg && (
              <div className="pt-1 animate-fadeIn">
                <label className="block text-xs font-medium text-gray-700 mb-1.5">
                  Company / Organization Name
                </label>
                <div className="relative">
                  <Building2 className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required={isOrg}
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="Acme Global Inc"
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-white border border-gray-300 focus:border-blue-600 focus:ring-1 focus:ring-blue-600 text-sm text-gray-900 placeholder:text-gray-400 transition outline-none"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full mt-4 py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm shadow-sm flex items-center justify-center gap-2 transition disabled:opacity-50 cursor-pointer"
            >
              {submitting ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              ) : (
                <>
                  <span>Create Workspace</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Footer link */}
          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500">
              Already have an account?{" "}
              <Link href="/login" className="text-blue-600 hover:text-blue-700 font-medium">
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Security badge */}
        <div className="flex items-center justify-center gap-2 mt-6 text-xs text-gray-500">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>Zero-Trust Multi-Tenant Isolation & Argon2id Encrypted</span>
        </div>
      </div>
    </div>
  );
}
