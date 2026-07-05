import { fetchApi } from './client';
import { setToken, clearToken, getToken } from './token';

export { getToken, clearToken };

export interface AuthStatus {
  auth_required: boolean;
}

// Whether the daemon has a password gate enabled.
export const getAuthStatus = () => fetchApi<AuthStatus>('/api/v1/auth/status');

// Exchange the gate password for a session token and store it.
export async function login(password: string): Promise<string> {
  const res = await fetchApi<{ token: string }>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
  setToken(res.token);
  return res.token;
}

export function logout(): void {
  clearToken();
}
