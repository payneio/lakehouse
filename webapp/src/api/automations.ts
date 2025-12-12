/**
 * API client for automation endpoints
 *
 * Provides functions for managing scheduled project prompts (automations).
 */

export interface ScheduleConfig {
  type: "cron" | "interval" | "once";
  value: string; // cron expression, interval notation (e.g., "1h"), or ISO datetime
}

export interface Automation {
  id: string;
  project_id: string;
  name: string;
  message: string;
  schedule: ScheduleConfig;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  last_execution: string | null;
  next_execution: string | null;
}

export interface AutomationCreate {
  name: string;
  message: string;
  schedule: ScheduleConfig;
  enabled?: boolean;
}

export interface AutomationUpdate {
  name?: string;
  message?: string;
  schedule?: ScheduleConfig;
  enabled?: boolean;
}

export interface ExecutionRecord {
  id: string;
  automation_id: string;
  session_id: string;
  executed_at: string;
  status: "success" | "failed";
  error: string | null;
}

export interface AutomationList {
  automations: Automation[];
  total: number;
}

export interface ExecutionHistory {
  executions: ExecutionRecord[];
  total: number;
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8421";

/**
 * Create a new automation for a project
 */
export async function createAutomation(
  projectId: string,
  automation: AutomationCreate
): Promise<Automation> {
  const response = await fetch(
    `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/automations/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(automation),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `Failed to create automation: ${response.statusText}`);
  }

  const data = await response.json();
  return data.automation;
}

/**
 * List automations for a project
 */
export async function listAutomations(
  projectId: string,
  options?: {
    enabled?: boolean;
    limit?: number;
    offset?: number;
  }
): Promise<AutomationList> {
  const params = new URLSearchParams();
  if (options?.enabled !== undefined) params.set("enabled", String(options.enabled));
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));

  const url = `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/automations/${
    params.toString() ? `?${params}` : ""
  }`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to list automations: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a specific automation by ID
 */
export async function getAutomation(
  projectId: string,
  automationId: string
): Promise<Automation> {
  const response = await fetch(
    `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/automations/${encodeURIComponent(automationId)}/`
  );

  if (!response.ok) {
    throw new Error(`Failed to get automation: ${response.statusText}`);
  }

  const data = await response.json();
  return data.automation;
}

/**
 * Update an automation
 */
export async function updateAutomation(
  projectId: string,
  automationId: string,
  update: AutomationUpdate
): Promise<Automation> {
  const response = await fetch(
    `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/automations/${encodeURIComponent(automationId)}/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `Failed to update automation: ${response.statusText}`);
  }

  const data = await response.json();
  return data.automation;
}

/**
 * Delete an automation
 */
export async function deleteAutomation(
  projectId: string,
  automationId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/automations/${encodeURIComponent(automationId)}/`,
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to delete automation: ${response.statusText}`);
  }
}

/**
 * Toggle automation enabled status
 */
export async function toggleAutomation(
  projectId: string,
  automationId: string,
  enabled: boolean
): Promise<{ automation_id: string; enabled: boolean }> {
  const response = await fetch(
    `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/automations/${encodeURIComponent(automationId)}/toggle/`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to toggle automation: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get execution history for an automation
 */
export async function getExecutionHistory(
  projectId: string,
  automationId: string,
  options?: {
    status?: "success" | "failed";
    limit?: number;
    offset?: number;
  }
): Promise<ExecutionHistory> {
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));

  const url = `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/automations/${encodeURIComponent(automationId)}/executions/${
    params.toString() ? `?${params}` : ""
  }`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to get execution history: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Helper: Convert user-friendly schedule string to ScheduleConfig
 */
export function parseScheduleString(schedule: string): ScheduleConfig {
  // Map common schedule strings to cron expressions
  const scheduleMap: Record<string, ScheduleConfig> = {
    "Daily at 9:00 AM": { type: "cron", value: "0 9 * * *" },
    "Weekly on Mondays": { type: "cron", value: "0 9 * * 1" },
    "Every hour": { type: "interval", value: "1h" },
    "Every 30 minutes": { type: "interval", value: "30m" },
  };

  return scheduleMap[schedule] || { type: "cron", value: "0 9 * * *" };
}

/**
 * Helper: Convert ScheduleConfig to user-friendly string
 */
export function formatSchedule(schedule: ScheduleConfig): string {
  if (schedule.type === "cron") {
    // Map common cron expressions to user-friendly strings
    const cronMap: Record<string, string> = {
      "0 9 * * *": "Daily at 9:00 AM",
      "0 9 * * 1": "Weekly on Mondays",
      "0 0 * * *": "Daily at midnight",
    };
    return cronMap[schedule.value] || `Cron: ${schedule.value}`;
  }

  if (schedule.type === "interval") {
    const match = schedule.value.match(/^(\d+)([smhd])$/);
    if (match) {
      const [, value, unit] = match;
      const unitMap: Record<string, string> = {
        s: "second",
        m: "minute",
        h: "hour",
        d: "day",
      };
      const unitName = unitMap[unit] || "unit";
      const plural = parseInt(value) > 1 ? "s" : "";
      return `Every ${value} ${unitName}${plural}`;
    }
    return `Interval: ${schedule.value}`;
  }

  if (schedule.type === "once") {
    const date = new Date(schedule.value);
    return `Once at ${date.toLocaleString()}`;
  }

  return "Unknown schedule";
}
