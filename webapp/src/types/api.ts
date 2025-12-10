export interface Collection {
  identifier: string;
  source: string;
  version?: string;
  description?: string;
  last_synced?: string;
  profiles?: string[];
  metadata?: Record<string, unknown>;
}

export interface Profile {
  name: string;
  description?: string;
  source: string;
  isActive: boolean;
  collectionId?: string;
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

export interface SessionConfig {
  orchestrator: ModuleConfig;
  contextManager?: ModuleConfig;
}

export interface ProfileDetails {
  name: string;
  schemaVersion: number;
  version: string;
  description: string;
  collectionId?: string;
  source: string;
  isActive: boolean;
  inheritanceChain?: string[];
  providers: ModuleConfig[];
  tools: ModuleConfig[];
  hooks: ModuleConfig[];
  session?: SessionConfig;
  agents?: Record<string, string>;
  context?: Record<string, string>;
  instruction?: string;
}

export interface DirectoryMetadata {
  name?: string;
  description?: string;
  [key: string]: unknown;
}

export interface AmplifiedDirectory {
  path: string;
  relative_path: string;
  default_profile?: string;
  metadata?: DirectoryMetadata;
  agents_content?: string;
  is_amplified: boolean;
}

export interface AmplifiedDirectoryCreate {
  relative_path: string;
  default_profile?: string;
  metadata?: DirectoryMetadata;
  create_marker?: boolean;
}

export interface Session {
  sessionId: string;
  name?: string;
  profileName: string;
  status: 'created' | 'active' | 'completed' | 'failed' | 'terminated';
  createdAt: string;
  startedAt?: string;
  endedAt?: string;
  parentSessionId?: string;
  amplifiedDir?: string;
  mountPlanPath?: string;
  messageCount?: number;
  agentInvocations?: number;
  tokenUsage?: unknown;
  errorMessage?: string;
  errorDetails?: unknown;
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
  profile_name?: string;  // API expects snake_case for POST body - optional, uses directory default if not provided
  amplified_dir?: string;  // API expects snake_case for POST body
  parent_session_id?: string;  // API expects snake_case for POST body
  settings_overrides?: Record<string, unknown>;
}

export interface SyncCollectionsResponse {
  collections: Record<string, string>;
  modules: Record<string, unknown>;
}

export interface ListDirectoriesResponse {
  directories: AmplifiedDirectory[];
  total: number;
}

export interface CreateProfileRequest {
  name: string;
  version?: string;
  description?: string;
  providers?: ModuleConfig[];
  tools?: ModuleConfig[];
  hooks?: ModuleConfig[];
  orchestrator?: ModuleConfig;
  context?: ModuleConfig;
  agents?: Record<string, string>;
  contexts?: Record<string, string>;
  instruction?: string;
}

export interface UpdateProfileRequest {
  version?: string;
  description?: string;
  providers?: ModuleConfig[];
  tools?: ModuleConfig[];
  hooks?: ModuleConfig[];
  orchestrator?: ModuleConfig;
  context?: ModuleConfig;
  agents?: Record<string, string>;
  contexts?: Record<string, string>;
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

export interface ComponentRef {
  profile: string;
  name: string;
  uri: string;
}

export interface ComponentRefsResponse {
  orchestrators: ComponentRef[];
  contextManagers: ComponentRef[];
  providers: ComponentRef[];
  tools: ComponentRef[];
  hooks: ComponentRef[];
  agents: ComponentRef[];
  contexts: ComponentRef[];
}
