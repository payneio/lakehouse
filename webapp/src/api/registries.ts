import { fetchApi } from './client';

export interface Registry {
  id: string;
  uri: string;
  description: string;
}

export interface RegistryCreateRequest {
  uri: string;
  description?: string;
}

export interface RegistryUpdateRequest {
  description: string;
}

export const listRegistries = () =>
  fetchApi<Registry[]>('/api/v1/registries/');

export const getRegistry = (id: string) =>
  fetchApi<Registry>(`/api/v1/registries/${id}`);

export const createRegistry = (data: RegistryCreateRequest) =>
  fetchApi<Registry>('/api/v1/registries/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const updateRegistry = (id: string, data: RegistryUpdateRequest) =>
  fetchApi<Registry>(`/api/v1/registries/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const deleteRegistry = (id: string) =>
  fetchApi<void>(`/api/v1/registries/${id}`, {
    method: 'DELETE',
  });
