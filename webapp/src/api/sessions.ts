import { fetchApi } from './client';
import type { Session, SessionMessage, CreateSessionRequest } from '@/types/api';

export const listSessions = (params?: {
  status?: string;
  profile_name?: string;
  amplified_dir?: string;
  limit?: number;
}) => {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.profile_name) searchParams.set('profile_name', params.profile_name);
  if (params?.amplified_dir) searchParams.set('amplified_dir', params.amplified_dir);
  if (params?.limit) searchParams.set('limit', String(params.limit));

  const query = searchParams.toString();
  return fetchApi<Session[]>(`/api/v1/sessions/${query ? `?${query}` : ''}`);
};

export const getSession = (sessionId: string) =>
  fetchApi<Session>(`/api/v1/sessions/${sessionId}`);

export const createSession = (data: CreateSessionRequest) =>
  fetchApi<Session>('/api/v1/sessions/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const startSession = (sessionId: string) =>
  fetchApi<void>(`/api/v1/sessions/${sessionId}/start`, {
    method: 'POST',
  });

export const deleteSession = (sessionId: string) =>
  fetchApi<void>(`/api/v1/sessions/${sessionId}`, {
    method: 'DELETE',
  });

export const getTranscript = (sessionId: string, limit?: number) => {
  const query = limit ? `?limit=${limit}` : '';
  return fetchApi<SessionMessage[]>(
    `/api/v1/sessions/${sessionId}/transcript${query}`
  );
};

export const sendMessage = (
  sessionId: string,
  content: string
) =>
  fetchApi<void>(`/api/v1/sessions/${sessionId}/send-message`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });

export const changeProfile = (sessionId: string, profileName: string) =>
  fetchApi<Session>(`/api/v1/sessions/${sessionId}/change-profile`, {
    method: 'POST',
    body: JSON.stringify({ profile_name: profileName }),
  });
