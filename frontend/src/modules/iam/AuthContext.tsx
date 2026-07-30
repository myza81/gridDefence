import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, setAuthTokenProvider } from "../../api/client";
import { iamApi } from "./api";
import { authStorage } from "./authStorage";
import type { UserSummary } from "./types";

interface AuthContextValue {
  token: string | null;
  currentUser: UserSummary | undefined;
  isLoadingCurrentUser: boolean;
  /** UI-gating only (CLAUDE.md A12) — the backend re-checks every request. */
  permissions: Set<string>;
  /**
   * `remember` (default `true`) controls token persistence: `true` keeps the
   * session across a browser restart (localStorage), `false` drops it when the
   * tab closes (sessionStorage). Backs the login page's "Remember me" control.
   */
  login: (username: string, password: string, remember?: boolean) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [token, setToken] = useState<string | null>(() => authStorage.getToken());
  const queryClient = useQueryClient();

  // The shared API client asks this provider for the current token on every
  // request, rather than each module wiring its own header logic.
  useEffect(() => {
    setAuthTokenProvider(() => token);
    return () => setAuthTokenProvider(null);
  }, [token]);

  const currentUserQuery = useQuery({
    queryKey: ["iam", "currentUser", token],
    queryFn: iamApi.getCurrentUser,
    enabled: token !== null,
    retry: false,
  });

  const currentUser = currentUserQuery.data;

  const userRolesQuery = useQuery({
    queryKey: ["iam", "currentUserRoles", currentUser?.user_id],
    queryFn: () => iamApi.listUserRoles(currentUser!.user_id),
    enabled: currentUser !== undefined,
    retry: false,
  });

  const permissions = useMemo(() => {
    const set = new Set<string>();
    for (const userRole of userRolesQuery.data ?? []) {
      for (const permissionId of userRole.permissions) {
        set.add(permissionId);
      }
    }
    return set;
  }, [userRolesQuery.data]);

  // Only a rejected token (401 — expired/invalid/revoked) ends the session.
  // Other failures (network blips, 5xx) leave the stored token alone so a
  // transient outage doesn't silently sign the user out.
  useEffect(() => {
    const error = currentUserQuery.error;
    if (token !== null && error instanceof ApiError && error.status === 401) {
      authStorage.clearToken();
      setToken(null);
    }
  }, [token, currentUserQuery.error]);

  async function login(username: string, password: string, remember = true): Promise<void> {
    const response = await iamApi.login({ username, password });
    authStorage.setToken(response.access_token, remember);
    setToken(response.access_token);
  }

  async function logout(): Promise<void> {
    try {
      await iamApi.logout();
    } finally {
      authStorage.clearToken();
      setToken(null);
      queryClient.clear();
    }
  }

  const value: AuthContextValue = {
    token,
    currentUser,
    isLoadingCurrentUser: token !== null && currentUserQuery.isLoading,
    permissions,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
