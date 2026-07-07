import { fetchApi } from './client';

// Module reference in an assistant
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

// Assistant list item with summary
export interface AssistantListItem {
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

// Full assistant details (raw structure)
export interface AssistantDetails extends AssistantListItem {
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

// Resolved assistant with source tracking
export interface ResolvedAssistant {
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

// Raw assistant source
export interface AssistantSource {
  name: string;
  content: string;
  path: string;
  format: 'md' | 'yaml' | 'directory';
}

// Request types
export interface CreateAssistantRequest {
  name: string;
  baseBundle?: string;
  description?: string;
}

export interface CopyAssistantRequest {
  newName: string;
}

export interface RenameAssistantRequest {
  newName: string;
}

export interface UpdateAssistantRequest {
  content: string;
}

// API functions

// List all assistants with summary info
export const listAssistants = () =>
  fetchApi<AssistantListItem[]>('/api/v1/assistants/');

// Get full assistant details
export const getAssistantDetails = (name: string) =>
  fetchApi<AssistantDetails>(`/api/v1/assistants/${encodeURIComponent(name)}/`);

// Get resolved assistant with source tracking
export const getResolvedAssistant = (name: string) =>
  fetchApi<ResolvedAssistant>(`/api/v1/assistants/${encodeURIComponent(name)}/resolved`);

// Get raw assistant source
export const getAssistantSource = (name: string) =>
  fetchApi<AssistantSource>(`/api/v1/assistants/${encodeURIComponent(name)}/source`);

// Create a new assistant
export const createAssistant = (data: CreateAssistantRequest) =>
  fetchApi<AssistantListItem>('/api/v1/assistants/', {
    method: 'POST',
    body: JSON.stringify(data),
  });

// Copy an assistant
export const copyAssistant = (name: string, newName: string) =>
  fetchApi<AssistantListItem>(`/api/v1/assistants/${encodeURIComponent(name)}/copy`, {
    method: 'POST',
    body: JSON.stringify({ newName } as CopyAssistantRequest),
  });

// Rename an assistant
export const renameAssistant = (name: string, newName: string) =>
  fetchApi<AssistantListItem>(`/api/v1/assistants/${encodeURIComponent(name)}/rename`, {
    method: 'POST',
    body: JSON.stringify({ newName } as RenameAssistantRequest),
  });

// Update an assistant
export const updateAssistant = (name: string, content: string) =>
  fetchApi<AssistantListItem>(`/api/v1/assistants/${encodeURIComponent(name)}/`, {
    method: 'PUT',
    body: JSON.stringify({ content } as UpdateAssistantRequest),
  });

// Delete an assistant
export const deleteAssistant = (name: string) =>
  fetchApi<{ message: string }>(`/api/v1/assistants/${encodeURIComponent(name)}/`, {
    method: 'DELETE',
  });
