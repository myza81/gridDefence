const TOKEN_STORAGE_KEY = "griddefence.iam.access_token";

/**
 * Session token persistence. Tokens are stateless HMAC-signed values
 * (backend/app/modules/iam/security.py) — the client only needs to remember
 * and forward one, never validate or decode it.
 */
export const authStorage = {
  getToken(): string | null {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  },
  setToken(token: string): void {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  },
  clearToken(): void {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  },
};
