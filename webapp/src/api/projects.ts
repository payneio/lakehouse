import { fetchApi } from './client';
import type {
  Project,
  ProjectCreate,
  ListProjectsResponse,
} from '@/types/api';

export const listProjects = () =>
  fetchApi<ListProjectsResponse>('/api/v1/projects/');

export const getProject = (relativePath: string) => {
  // Special case: Use /root endpoint for root directory to avoid FastAPI routing issues
  const path = relativePath === '.' ? 'root' : encodeURIComponent(relativePath);
  return fetchApi<Project>(`/api/v1/projects/${path}`);
};

export const createProject = (data: ProjectCreate) =>
  fetchApi<Project>('/api/v1/projects/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateProject = (
  relativePath: string,
  data: Partial<ProjectCreate>
) =>
  fetchApi<Project>(`/api/v1/projects/${relativePath}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteProject = (
  relativePath: string,
  removeMarker: boolean = false
) =>
  fetchApi<void>(
    `/api/v1/projects/${relativePath}?remove_marker=${removeMarker}`,
    { method: 'DELETE' }
  );


