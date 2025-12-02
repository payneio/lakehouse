import { fetchApi } from './client';
import type { Collection } from '@/types/api';
import type {
  AllCacheStatus,
  CollectionCacheStatus,
  AllUpdateResult,
  CollectionUpdateResult,
  ProfileUpdateResult,
} from '@/types/cache';

export const listCollections = () =>
  fetchApi<Collection[]>('/api/v1/collections/');

export const getCollection = (identifier: string) =>
  fetchApi<Collection>(`/api/v1/collections/${identifier}`);

// Cache Status APIs
export const getCacheStatus = () =>
  fetchApi<AllCacheStatus>('/api/v1/cache/status');

export const getCollectionStatus = (identifier: string) =>
  fetchApi<CollectionCacheStatus>(`/api/v1/cache/status/collections/${identifier}`);

// Cache Update APIs
export const updateAllCollections = (params?: { checkOnly?: boolean; force?: boolean }) => {
  const searchParams = new URLSearchParams();
  if (params?.checkOnly) searchParams.set('check_only', 'true');
  if (params?.force) searchParams.set('force', 'true');
  return fetchApi<AllUpdateResult>(
    `/api/v1/cache/update${searchParams.toString() ? `?${searchParams}` : ''}`,
    { method: 'POST' }
  );
};

export const updateCollection = (
  identifier: string,
  params?: { checkOnly?: boolean; force?: boolean }
) => {
  const searchParams = new URLSearchParams();
  if (params?.checkOnly) searchParams.set('check_only', 'true');
  if (params?.force) searchParams.set('force', 'true');
  return fetchApi<CollectionUpdateResult>(
    `/api/v1/cache/update/collections/${identifier}${searchParams.toString() ? `?${searchParams}` : ''}`,
    { method: 'POST' }
  );
};

export const updateProfile = (
  collectionId: string,
  profileName: string,
  params?: { checkOnly?: boolean; force?: boolean }
) => {
  const searchParams = new URLSearchParams();
  if (params?.checkOnly) searchParams.set('check_only', 'true');
  if (params?.force) searchParams.set('force', 'true');
  return fetchApi<ProfileUpdateResult>(
    `/api/v1/cache/update/profiles/${collectionId}/${profileName}${searchParams.toString() ? `?${searchParams}` : ''}`,
    { method: 'POST' }
  );
};

export const mountCollection = (data: { identifier: string; source: string }) =>
  fetchApi<{ status: string; identifier: string; source: string }>('/api/v1/collections/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const unmountCollection = (identifier: string) =>
  fetchApi<{ success: boolean }>(`/api/v1/collections/${identifier}`, {
    method: 'DELETE',
  });
