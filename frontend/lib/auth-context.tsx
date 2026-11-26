"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { api, UserProfile, WorkspaceSummary } from "./api";
import { useRouter } from "next/navigation";

interface AuthContextType {
  user: UserProfile | null;
  activeWorkspace: WorkspaceSummary | null;
  workspaces: WorkspaceSummary[];
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: { email: string; password: string; full_name: string; organization_name?: string }) => Promise<void>;
  logout: () => void;
  switchWorkspace: (tenantId: string) => Promise<void>;
  refreshWorkspaces: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const loadUserData = async () => {
    try {
      const profile = await api.getMe();
      setUser(profile);
      setWorkspaces(profile.workspaces || []);

      const savedActiveId = localStorage.getItem("mmaip_active_tenant_id");
      const matched = profile.workspaces.find((w) => w.tenant_id === savedActiveId);

      if (matched) {
        setActiveWorkspace(matched);
      } else if (profile.workspaces.length > 0) {
        setActiveWorkspace(profile.workspaces[0]);
        localStorage.setItem("mmaip_active_tenant_id", profile.workspaces[0].tenant_id);
      }
    } catch {
      setUser(null);
      setActiveWorkspace(null);
      setWorkspaces([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUserData();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      await api.login({ email, password });
      await loadUserData();
      router.push("/dashboard");
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: { email: string; password: string; full_name: string; organization_name?: string }) => {
    setIsLoading(true);
    try {
      await api.register(payload);
      await loadUserData();
      router.push("/dashboard");
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    api.logout();
    setUser(null);
    setActiveWorkspace(null);
    setWorkspaces([]);
    router.push("/login");
  };

  const switchWorkspace = async (tenantId: string) => {
    setIsLoading(true);
    try {
      await api.switchWorkspace(tenantId);
      const target = workspaces.find((w) => w.tenant_id === tenantId);
      if (target) {
        setActiveWorkspace(target);
      }
      await loadUserData();
    } finally {
      setIsLoading(false);
    }
  };

  const refreshWorkspaces = async () => {
    await loadUserData();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        activeWorkspace,
        workspaces,
        isLoading,
        login,
        register,
        logout,
        switchWorkspace,
        refreshWorkspaces,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
