// Session token storage for the password login gate.
// Kept dependency-free so both the API client and auth module can import it
// without creating a circular dependency.

const TOKEN_KEY = 'lakehouse_auth_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// Append the session token as a query param. Used for EventSource (SSE)
// connections, which cannot send custom headers.
export function withToken(url: string): string {
  const token = getToken();
  if (!token) return url;
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}
