import { fetchApi, BASE_URL } from './client';
import type {
  AmplifiedDirectory,
  AmplifiedDirectoryCreate,
  ListDirectoriesResponse,
  DirectoryListResponse,
  DirectoryCreateRequest,
  DirectoryCreateResponse,
  FileCompletionResponse,
  FileContentResponse,
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

export const getDirectory = (relativePath: string) => {
  // Special case: Use /root endpoint for root directory to avoid FastAPI routing issues
  const path = relativePath === '.' ? 'root' : encodeURIComponent(relativePath);
  return fetchApi<AmplifiedDirectory>(`/api/v1/amplified-directories/${path}`);
};

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

export const listFilesForCompletion = (
  path: string = '',
  prefix: string = '',
  maxResults: number = 50
) => {
  const params = new URLSearchParams();
  if (path) params.set('path', path);
  if (prefix) params.set('prefix', prefix);
  params.set('max_results', maxResults.toString());
  return fetchApi<FileCompletionResponse>(`/api/v1/directories/files?${params.toString()}`);
};

export const getFileContent = (path: string) =>
  fetchApi<FileContentResponse>(`/api/v1/directories/file/content?path=${encodeURIComponent(path)}`);

export const getFileDownloadUrl = (path: string) =>
  `${BASE_URL}/api/v1/directories/file/download?path=${encodeURIComponent(path)}`;
