import { fetchApi } from './client';

// Module reference in a bundle
export interface ModuleRef {
  module: string;
  source?: string | null;
  config?: Record<string, unknown> | null;
}

// Module reference with source tracking
export interface ResolvedModuleRef extends ModuleRef {
  definedIn: string;
  overridden: boolean;
  overrideIn?: string | null;
  originalConfig?: Record<string, unknown> | null;
}

// Session config reference
export interface SessionConfigRef {
  orchestrator?: ModuleRef | null;
  context?: ModuleRef | null;
}

// Resolved session config
export interface ResolvedSessionConfig {
  orchestrator?: ResolvedModuleRef | null;
  context?: ResolvedModuleRef | null;
}

// Bundle list item with summary
export interface BundleListItem {
  name: string;
  version: string;
  description?: string | null;
  source: 'user' | 'system';
  path: string;

  // Quick stats
  providerCount: number;
  toolCount: number;
  hookCount: number;
  agentCount: number;

  // Composition
  includes: string[];
}

// Full bundle details (raw structure)
export interface BundleDetails extends BundleListItem {
  session?: SessionConfigRef | null;
  providers: ModuleRef[];
  tools: ModuleRef[];
  hooks: ModuleRef[];
  agents: ModuleRef[];
  context: Record<string, string>;
  instruction?: string | null;
}

// Tree node for includes hierarchy
export interface IncludesTreeNode {
  name: string;
  includes: IncludesTreeNode[];
}

// Resolved bundle with source tracking
export interface ResolvedBundle {
  name: string;
  source: 'user' | 'system';
  gitUrl?: string | null;
  includesChain: string[];
  includesTree: IncludesTreeNode;

  session?: ResolvedSessionConfig | null;
  providers: ResolvedModuleRef[];
  tools: ResolvedModuleRef[];
  hooks: ResolvedModuleRef[];
  agents: ResolvedModuleRef[];

  instruction?: string | null;
}

// Raw bundle source
export interface BundleSource {
  name: string;
  content: string;
  path: string;
  format: 'md' | 'yaml' | 'directory';
}

// Request types
export interface CreateBundleRequest {
  name: string;
  baseBundle?: string;
  description?: string;
}

export interface CopyBundleRequest {
  newName: string;
}

export interface RenameBundleRequest {
  newName: string;
}

export interface AddRegistryBundleRequest {
  name: string;
  gitUrl: string;
}

export interface UpdateBundleRequest {
  content: string;
}

// API functions

// List all bundles with summary info
export const listBundles = () =>
  fetchApi<BundleListItem[]>('/api/v1/bundles/');

// Get full bundle details
export const getBundleDetails = (name: string) =>
  fetchApi<BundleDetails>(`/api/v1/bundles/${encodeURIComponent(name)}/`);

// Get resolved bundle with source tracking
export const getResolvedBundle = (name: string) =>
  fetchApi<ResolvedBundle>(`/api/v1/bundles/${encodeURIComponent(name)}/resolved`);

// Get raw bundle source
export const getBundleSource = (name: string) =>
  fetchApi<BundleSource>(`/api/v1/bundles/${encodeURIComponent(name)}/source`);

// Create a new bundle
export const createBundle = (data: CreateBundleRequest) =>
  fetchApi<BundleListItem>('/api/v1/bundles/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

// Copy a bundle
export const copyBundle = (name: string, newName: string) =>
  fetchApi<BundleListItem>(`/api/v1/bundles/${encodeURIComponent(name)}/copy`, {
    method: 'POST',
    body: JSON.stringify({ newName } as CopyBundleRequest),
  });

// Rename a bundle
export const renameBundle = (name: string, newName: string) =>
  fetchApi<BundleListItem>(`/api/v1/bundles/${encodeURIComponent(name)}/rename`, {
    method: 'POST',
    body: JSON.stringify({ newName } as RenameBundleRequest),
  });

// Update a bundle
export const updateBundle = (name: string, content: string) =>
  fetchApi<BundleListItem>(`/api/v1/bundles/${encodeURIComponent(name)}/`, {
    method: 'PUT',
    body: JSON.stringify({ content } as UpdateBundleRequest),
  });

// Delete a bundle
export const deleteBundle = (name: string) =>
  fetchApi<{ message: string }>(`/api/v1/bundles/${encodeURIComponent(name)}/`, {
    method: 'DELETE',
  });

// Add a bundle from git URL to registry
export const addRegistryBundle = (name: string, gitUrl: string) =>
  fetchApi<{ message: string }>('/api/v1/bundles/registry', {
    method: 'POST',
    body: JSON.stringify({ name, gitUrl } as AddRegistryBundleRequest),
  });

// Remove a bundle from registry
export const removeRegistryBundle = (name: string) =>
  fetchApi<{ message: string }>(`/api/v1/bundles/registry/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
