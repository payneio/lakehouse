import { fetchApi } from './client';
import type {
  AmplifiedDirectory,
  AmplifiedDirectoryCreate,
  ListDirectoriesResponse,
  DirectoryListResponse,
  DirectoryCreateRequest,
  DirectoryCreateResponse,
} from '@/types/api';

export const listDirectories = () =>
  fetchApi<ListDirectoriesResponse>('/api/v1/amplified-directories/');

export const listDirectoryContents = (path: string = '') =>
  fetchApi<DirectoryListResponse>(`/api/v1/directories/list?path=${encodeURIComponent(path)}`);

export const createDirectoryPath = (data: DirectoryCreateRequest) =>
  fetchApi<DirectoryCreateResponse>('/api/v1/directories/create', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const getDirectory = (relativePath: string) =>
  fetchApi<AmplifiedDirectory>(`/api/v1/amplified-directories/${relativePath}`);

export const createDirectory = (data: AmplifiedDirectoryCreate) =>
  fetchApi<AmplifiedDirectory>('/api/v1/amplified-directories/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateDirectory = (
  relativePath: string,
  data: Partial<AmplifiedDirectoryCreate>
) =>
  fetchApi<AmplifiedDirectory>(`/api/v1/amplified-directories/${relativePath}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteDirectory = (
  relativePath: string,
  removeMarker: boolean = false
) =>
  fetchApi<void>(
    `/api/v1/amplified-directories/${relativePath}?remove_marker=${removeMarker}`,
    { method: 'DELETE' }
  );
