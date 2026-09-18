import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, tokens } from "../api/client";
import type { AuthResponse, User } from "../api/types";
import { AuthContext, type AuthContextValue } from "./useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(tokens.access));
  const queryClient = useQueryClient();

  const logout = useCallback(() => {
    tokens.clear();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    if (!tokens.access) return;
    api
      .get<User>("/auth/me")
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    window.addEventListener("asc:logout", logout);
    return () => window.removeEventListener("asc:logout", logout);
  }, [logout]);

  const value = useMemo<AuthContextValue>(() => {
    const signIn = (res: AuthResponse) => {
      tokens.set(res.access, res.refresh);
      setUser(res.user);
    };
    return {
      user,
      loading,
      login: async (email, password) => signIn(await api.post<AuthResponse>("/auth/token", { email, password })),
      register: async (name, email, password) =>
        signIn(await api.post<AuthResponse>("/auth/register", { name, email, password })),
      logout,
    };
  }, [user, loading, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
