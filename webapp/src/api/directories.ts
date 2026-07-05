import { fetchApi, BASE_URL } from './client';
import type {
  DirectoryListResponse,
  DirectoryCreateRequest,
  DirectoryCreateResponse,
  FileCompletionResponse,
  FileContentResponse,
} from '@/types/api';

// Re-export project functions for backward compatibility
export {
  listProjects,
  listProjects as listDirectories,
  getProject,
  getProject as getDirectory,
  createProject,
  createProject as createDirectory,
  updateProject,
  updateProject as updateDirectory,
  deleteProject,
  deleteProject as deleteDirectory,
} from './projects';

// File system browsing (not project-related)
export const listDirectoryContents = (path: string = '') =>
  fetchApi<DirectoryListResponse>(`/api/v1/directories/list?path=${encodeURIComponent(path)}`);

export const createDirectoryPath = (data: DirectoryCreateRequest) =>
  fetchApi<DirectoryCreateResponse>('/api/v1/directories/create', {
    method: 'POST',
    body: JSON.stringify(data),
  });

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
