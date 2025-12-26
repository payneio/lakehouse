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

export const cancelExecution = (sessionId: string) =>
  fetchApi<{ status: string; session_id: string }>(
    `/api/v1/sessions/${sessionId}/cancel-execution`,
    { method: 'POST' }
  );

export const deleteLastMessage = (sessionId: string) =>
  fetchApi<{ status: string; session_id: string; deleted_message?: { role: string; timestamp: string } }>(
    `/api/v1/sessions/${sessionId}/messages/last`,
    { method: 'DELETE' }
  );

export const changeProfile = (sessionId: string, profileName: string) =>
  fetchApi<Session>(`/api/v1/sessions/${sessionId}/change-profile`, {
    method: 'POST',
    body: JSON.stringify({ profile_name: profileName }),
  });

export const updateSession = (
  sessionId: string,
  updates: { name?: string }
) =>
  fetchApi<Session>(`/api/v1/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });

// Session events types
export interface SessionEvent {
  event: string;
  lvl?: string;
  ts: string;
  data?: Record<string, unknown>;
  session_id?: string;
}

export interface SessionEventsResponse {
  events: SessionEvent[];
  total: number;
  hasMore: boolean;
}

export const getSessionEvents = (
  sessionId: string,
  params?: {
    limit?: number;
    offset?: number;
    level?: string;
    eventType?: string;
    includeChildren?: boolean;
  }
) => {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.offset) searchParams.set('offset', String(params.offset));
  if (params?.level) searchParams.set('level', params.level);
  if (params?.eventType) searchParams.set('event_type', params.eventType);
  if (params?.includeChildren) searchParams.set('include_children', 'true');

  const query = searchParams.toString();
  return fetchApi<SessionEventsResponse>(
    `/api/v1/sessions/${sessionId}/events${query ? `?${query}` : ''}`
  );
};
