const TOKEN_STORAGE_KEY = "griddefence.iam.access_token";

/**
 * Session token persistence. Tokens are stateless HMAC-signed values
 * (backend/app/modules/iam/security.py) — the client only needs to remember
 * and forward one, never validate or decode it.
 *
 * Persistence mode (added for the login page's approved "Remember me" control):
 * `persist: true` (the default, unchanged behaviour) keeps the token in
 * localStorage so the session survives a browser restart; `persist: false`
 * keeps it in sessionStorage so it is dropped when the tab/browser closes.
 * `getToken`/`clearToken` span both stores so the mode is transparent to
 * every existing caller.
 */
export const authStorage = {
  getToken(): string | null {
    return (
      window.localStorage.getItem(TOKEN_STORAGE_KEY) ??
      window.sessionStorage.getItem(TOKEN_STORAGE_KEY)
    );
  },
  setToken(token: string, persist = true): void {
    if (persist) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
      window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    } else {
      window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  },
  clearToken(): void {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  },
};
