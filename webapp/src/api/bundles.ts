import { fetchApi } from './client';

export interface Bundle {
  name: string;
}

export const listBundles = () =>
  fetchApi<Bundle[]>('/api/v1/bundles/');
