import { fetchApi } from "./client";

export interface ApiKeyInfo {
  providerId: string;
  isSet: boolean;
  maskedValue: string | null;
}

export interface DaemonSettings {
  host: string;
  port: number;
  workers: number;
  logLevel: string;
  corsOrigins: string[];
}

export interface StartupSettings {
  autoDiscoverProfiles: boolean;
  autoCompileProfiles: boolean;
  parallelCompilation: boolean;
  maxParallelWorkers: number;
}

export interface SettingsResponse {
  daemon: DaemonSettings;
  startup: StartupSettings;
  apiKeys: ApiKeyInfo[];
  configPath: string;
  dataPath: string;
}

export interface UpdateApiKeysResponse {
  updated: string[];
  message: string;
}

export interface UpdateDaemonConfigRequest {
  corsOrigins?: string[];
  logLevel?: string;
  host?: string;
  port?: number;
}

export interface UpdateDaemonConfigResponse {
  updated: string[];
  message: string;
  restartRequired: boolean;
}

export async function getSettings(): Promise<SettingsResponse> {
  return fetchApi<SettingsResponse>("/api/v1/settings");
}

export async function updateApiKeys(
  apiKeys: Record<string, string>
): Promise<UpdateApiKeysResponse> {
  return fetchApi<UpdateApiKeysResponse>("/api/v1/settings/api-keys", {
    method: "PATCH",
    body: JSON.stringify({ apiKeys }),
  });
}

export async function updateDaemonConfig(
  config: UpdateDaemonConfigRequest
): Promise<UpdateDaemonConfigResponse> {
  return fetchApi<UpdateDaemonConfigResponse>("/api/v1/settings/daemon", {
    method: "PATCH",
    body: JSON.stringify(config),
  });
}
