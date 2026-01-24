// @deprecated - Collections removed in v3, use registries instead
export interface Collection {
  identifier: string;
  source: string;
  version?: string;
  description?: string;
  last_synced?: string;
  profiles?: string[];
  metadata?: Record<string, unknown>;
}

// @deprecated - Use Bundle interface from bundles.ts instead. Profiles replaced by bundles in v3.
export interface Profile {
  name: string;
  description?: string;
  source: string;
  sourceType: 'local' | 'registry';
  registryId?: string;
  sourceUri?: string;
  isActive: boolean;
  schemaVersion?: number;
  baseProfile?: string;
  settings?: Record<string, unknown>;
  contextFiles?: string[];
  metadata?: Record<string, unknown>;
}

export interface ModuleConfig {
  module: string;
  source?: string;
  config?: Record<string, unknown>;
}

export interface BehaviorRef {
  id: string;
  source: string;
  config?: Record<string, unknown>;
}

export interface SessionConfig {
  orchestrator: ModuleConfig;
  contextManager?: ModuleConfig;
}

// @deprecated - Use BundleDetails interface from bundles.ts instead. Profiles replaced by bundles in v3.
export interface ProfileDetails {
  name: string;
  schemaVersion: number;
  version: string;
  description: string;
  source: string;
  sourceType: 'local' | 'registry';
  registryId?: string;
  sourceUri?: string;
  isActive: boolean;
  inheritanceChain?: string[];
  providers: ModuleConfig[];
  behaviors: BehaviorRef[];
  session?: SessionConfig;
  instruction?: string;
  // Legacy fields (v2 profiles)
  tools?: ModuleConfig[];
  hooks?: ModuleConfig[];
  agents?: Record<string, string>;
  context?: Record<string, string>;
}

export interface DirectoryMetadata {
  name?: string;
  description?: string;
  [key: string]: unknown;
}

export interface Project {
  path: string;
  relative_path: string;
  default_bundle?: string;
  metadata?: DirectoryMetadata;
  agents_content?: string;
  is_project: boolean;
}

export interface ProjectCreate {
  relative_path: string;
  default_bundle?: string;
  metadata?: DirectoryMetadata;
  create_marker?: boolean;
}


export interface Session {
  sessionId: string;
  name?: string;
  bundleName: string;
  status: 'created' | 'active' | 'completed' | 'failed' | 'terminated';
  createdAt: string;
  startedAt?: string;
  endedAt?: string;
  parentSessionId?: string;
  projectPath?: string;
  mountPlanPath?: string;
  messageCount?: number;
  agentInvocations?: number;
  tokenUsage?: unknown;
  errorMessage?: string;
  errorDetails?: unknown;
  isUnread?: boolean;
  lastReadAt?: string;
}

export interface SessionMessage {
  role: string;
  content: string;
  timestamp: string;
  agent?: string;
  token_count?: number;
  metadata?: Record<string, unknown>;
}

export interface CreateSessionRequest {
  bundle_name?: string;  // API expects snake_case for POST body - optional, uses project default if not provided
  project_path?: string;  // API expects snake_case for POST body
  parent_session_id?: string;  // API expects snake_case for POST body
  settings_overrides?: Record<string, unknown>;
}

export interface SyncCollectionsResponse {
  collections: Record<string, string>;
  modules: Record<string, unknown>;
}

export interface ListProjectsResponse {
  projects: Project[];
  total: number;
}

// Backward compatibility alias
export type ListDirectoriesResponse = ListProjectsResponse;

// @deprecated - Profile creation removed in v3. Use bundles instead.
export interface CreateProfileRequest {
  name: string;
  version?: string;
  description?: string;
  providers?: ModuleConfig[];
  behaviors?: BehaviorRef[];
  orchestrator?: ModuleConfig;
  context?: ModuleConfig;
  instruction?: string;
}

// @deprecated - Profile updates removed in v3. Use bundles instead.
export interface UpdateProfileRequest {
  version?: string;
  description?: string;
  providers?: ModuleConfig[];
  behaviors?: BehaviorRef[];
  orchestrator?: ModuleConfig;
  context?: ModuleConfig;
  instruction?: string;
}

export interface DirectoryListResponse {
  current_path: string;
  parent_path: string | null;
  directories: string[];
}

export interface DirectoryCreateRequest {
  relative_path: string;
}

export interface DirectoryCreateResponse {
  created_path: string;
  absolute_path: string;
}

export interface FileEntry {
  name: string;
  path: string;
  is_directory: boolean;
}

export interface FileCompletionResponse {
  entries: FileEntry[];
  base_path: string;
}

export interface FileContentResponse {
  path: string;
  name: string;
  content: string;
  size: number;
  mime_type: string;
  is_viewable: boolean;
  is_image: boolean;
  is_video: boolean;
}

export interface ComponentRef {
  profile: string;
  name: string;
  uri: string;
}

export interface ComponentRefsResponse {
  orchestrators: ComponentRef[];
  contextManagers: ComponentRef[];
  providers: ComponentRef[];
  behaviors: ComponentRef[];
}
