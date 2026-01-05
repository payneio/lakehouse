import { useState } from "react";
import {
  AlertTriangle,
  Clock,
  Eye,
  EyeOff,
  FolderOpen,
  Globe,
  Key,
  Loader2,
  Plus,
  Save,
  Settings,
  Trash2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { ApiKeyInfo, SettingsResponse } from "@/api/settings";
import { getSettings, updateApiKeys, updateDaemonConfig } from "@/api/settings";

interface ApiKeyInputProps {
  keyInfo: ApiKeyInfo;
  value: string;
  onChange: (value: string) => void;
}

function ApiKeyInput({ keyInfo, value, onChange }: ApiKeyInputProps) {
  const [showValue, setShowValue] = useState(false);

  const displayName = keyInfo.providerId
    .replace("provider-", "")
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  return (
    <div className="space-y-1">
      <label className="text-sm font-medium text-foreground">{displayName}</label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type={showValue ? "text" : "password"}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={keyInfo.isSet ? keyInfo.maskedValue || "••••••••" : "Enter API key"}
            className="w-full px-3 py-2 pr-10 border rounded-md bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            type="button"
            onClick={() => setShowValue(!showValue)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            {showValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
      {keyInfo.isSet && !value && (
        <p className="text-xs text-muted-foreground">
          Key is configured. Enter a new value to update.
        </p>
      )}
    </div>
  );
}

interface CorsOriginsInputProps {
  origins: string[];
  onChange: (origins: string[]) => void;
}

function CorsOriginsInput({ origins, onChange }: CorsOriginsInputProps) {
  const [newOrigin, setNewOrigin] = useState("");

  const addOrigin = () => {
    if (newOrigin.trim() && !origins.includes(newOrigin.trim())) {
      onChange([...origins, newOrigin.trim()]);
      setNewOrigin("");
    }
  };

  const removeOrigin = (index: number) => {
    onChange(origins.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">CORS Origins</label>
      <div className="space-y-2">
        {origins.map((origin, index) => (
          <div key={index} className="flex items-center gap-2">
            <input
              type="text"
              value={origin}
              onChange={(e) => {
                const updated = [...origins];
                updated[index] = e.target.value;
                onChange(updated);
              }}
              className="flex-1 px-3 py-2 border rounded-md bg-background text-foreground text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button
              type="button"
              onClick={() => removeOrigin(index)}
              className="p-2 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newOrigin}
            onChange={(e) => setNewOrigin(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addOrigin()}
            placeholder="http://localhost:7777"
            className="flex-1 px-3 py-2 border rounded-md bg-background text-foreground text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            type="button"
            onClick={addOrigin}
            className="p-2 text-muted-foreground hover:text-foreground"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Add origins for LAN access (e.g., http://192.168.1.100:7777).
      </p>
    </div>
  );
}

export function SettingsDialog() {
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSavingKeys, setIsSavingKeys] = useState(false);
  const [isSavingDaemon, setIsSavingDaemon] = useState(false);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [apiKeyValues, setApiKeyValues] = useState<Record<string, string>>({});
  const [corsOrigins, setCorsOrigins] = useState<string[]>([]);
  const [timezone, setTimezone] = useState<string>("UTC");
  const [message, setMessage] = useState<{ type: "success" | "error" | "warning"; text: string } | null>(null);

  const loadSettings = async () => {
    setIsLoading(true);
    setMessage(null);
    try {
      const data = await getSettings();
      setSettings(data);
      const initialValues: Record<string, string> = {};
      data.apiKeys.forEach((key) => {
        initialValues[key.providerId] = "";
      });
      setApiKeyValues(initialValues);
      setCorsOrigins(data.daemon.corsOrigins);
      setTimezone(data.daemon.timezone);
    } catch (error) {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to load settings",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (newOpen && !settings) {
      loadSettings();
    }
  };

  const handleSaveApiKeys = async () => {
    const keysToUpdate = Object.fromEntries(
      Object.entries(apiKeyValues).filter(([, value]) => value.trim() !== "")
    );

    if (Object.keys(keysToUpdate).length === 0) {
      setMessage({ type: "error", text: "No API key changes to save" });
      return;
    }

    setIsSavingKeys(true);
    setMessage(null);
    try {
      const response = await updateApiKeys(keysToUpdate);
      setMessage({ type: "success", text: response.message });
      setApiKeyValues({});
      await loadSettings();
    } catch (error) {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to save API keys",
      });
    } finally {
      setIsSavingKeys(false);
    }
  };

  const handleSaveDaemonConfig = async () => {
    if (!settings) return;

    const originsChanged = JSON.stringify(corsOrigins) !== JSON.stringify(settings.daemon.corsOrigins);
    const timezoneChanged = timezone !== settings.daemon.timezone;

    if (!originsChanged && !timezoneChanged) {
      setMessage({ type: "error", text: "No daemon config changes to save" });
      return;
    }

    setIsSavingDaemon(true);
    setMessage(null);
    try {
      const response = await updateDaemonConfig({
        ...(originsChanged && { corsOrigins }),
        ...(timezoneChanged && { timezone }),
      });
      if (response.restartRequired) {
        setMessage({ type: "warning", text: response.message });
      } else {
        setMessage({ type: "success", text: response.message });
      }
      await loadSettings();
    } catch (error) {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Failed to save daemon config",
      });
    } finally {
      setIsSavingDaemon(false);
    }
  };

  const hasApiKeyChanges = Object.values(apiKeyValues).some((v) => v.trim() !== "");
  const hasDaemonChanges = settings && (
    JSON.stringify(corsOrigins) !== JSON.stringify(settings.daemon.corsOrigins) ||
    timezone !== settings.daemon.timezone
  );

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <button
          className="p-1 rounded hover:bg-black/10 transition-colors"
          aria-label="Settings"
        >
          <Settings className="h-4 w-4" />
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Settings
          </DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : settings ? (
          <div className="space-y-6">
            {/* Data Path (read-only) */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <FolderOpen className="h-4 w-4" />
                Data Directory
              </div>
              <div className="px-3 py-2 border rounded-md bg-muted/50 font-mono text-sm">
                {settings.dataPath}
              </div>
              <p className="text-xs text-muted-foreground">
                Set via AMPLIFIERD_DATA_PATH environment variable.
              </p>
            </div>

            {/* Timezone & Network Settings */}
            <div className="space-y-4 pt-3 border-t">
              {/* Timezone */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Clock className="h-4 w-4" />
                  Automation Timezone
                </div>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <optgroup label="Americas">
                    <option value="America/Los_Angeles">Pacific Time (Los Angeles)</option>
                    <option value="America/Denver">Mountain Time (Denver)</option>
                    <option value="America/Chicago">Central Time (Chicago)</option>
                    <option value="America/New_York">Eastern Time (New York)</option>
                    <option value="America/Anchorage">Alaska Time (Anchorage)</option>
                    <option value="Pacific/Honolulu">Hawaii Time (Honolulu)</option>
                    <option value="America/Phoenix">Arizona (Phoenix)</option>
                    <option value="America/Toronto">Toronto</option>
                    <option value="America/Vancouver">Vancouver</option>
                    <option value="America/Mexico_City">Mexico City</option>
                    <option value="America/Sao_Paulo">Sao Paulo</option>
                  </optgroup>
                  <optgroup label="Europe">
                    <option value="Europe/London">London (GMT/BST)</option>
                    <option value="Europe/Paris">Paris (CET)</option>
                    <option value="Europe/Berlin">Berlin (CET)</option>
                    <option value="Europe/Amsterdam">Amsterdam (CET)</option>
                    <option value="Europe/Rome">Rome (CET)</option>
                    <option value="Europe/Madrid">Madrid (CET)</option>
                    <option value="Europe/Zurich">Zurich (CET)</option>
                    <option value="Europe/Moscow">Moscow</option>
                  </optgroup>
                  <optgroup label="Asia & Pacific">
                    <option value="Asia/Tokyo">Tokyo (JST)</option>
                    <option value="Asia/Shanghai">Shanghai (CST)</option>
                    <option value="Asia/Hong_Kong">Hong Kong</option>
                    <option value="Asia/Singapore">Singapore</option>
                    <option value="Asia/Seoul">Seoul (KST)</option>
                    <option value="Asia/Kolkata">India (IST)</option>
                    <option value="Asia/Dubai">Dubai (GST)</option>
                    <option value="Australia/Sydney">Sydney (AEST)</option>
                    <option value="Australia/Melbourne">Melbourne (AEST)</option>
                    <option value="Pacific/Auckland">Auckland (NZST)</option>
                  </optgroup>
                  <optgroup label="Other">
                    <option value="UTC">UTC</option>
                  </optgroup>
                </select>
                <p className="text-xs text-muted-foreground">
                  Timezone for automation scheduling. Changes require daemon restart.
                </p>
              </div>

              {/* CORS Origins */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Globe className="h-4 w-4" />
                  Network Access
                </div>
                <CorsOriginsInput origins={corsOrigins} onChange={setCorsOrigins} />
              </div>

              <div className="flex justify-end">
                <button
                  onClick={handleSaveDaemonConfig}
                  disabled={!hasDaemonChanges || isSavingDaemon}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSavingDaemon ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Save className="h-3 w-3" />
                  )}
                  Save
                </button>
              </div>
            </div>

            {/* API Keys */}
            <div className="space-y-3 pt-3 border-t">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Key className="h-4 w-4" />
                API Keys
              </div>
              <div className="space-y-3">
                {settings.apiKeys.map((keyInfo) => (
                  <ApiKeyInput
                    key={keyInfo.providerId}
                    keyInfo={keyInfo}
                    value={apiKeyValues[keyInfo.providerId] || ""}
                    onChange={(value) =>
                      setApiKeyValues((prev) => ({
                        ...prev,
                        [keyInfo.providerId]: value,
                      }))
                    }
                  />
                ))}
              </div>
              <div className="flex justify-between items-center">
                <p className="text-xs text-muted-foreground">
                  Changes take effect for new sessions.
                </p>
                <button
                  onClick={handleSaveApiKeys}
                  disabled={!hasApiKeyChanges || isSavingKeys}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSavingKeys ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Save className="h-3 w-3" />
                  )}
                  Save
                </button>
              </div>
            </div>

            {/* Message */}
            {message && (
              <div
                className={`flex items-center gap-2 text-sm p-3 rounded ${
                  message.type === "success"
                    ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                    : message.type === "warning"
                    ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                    : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                }`}
              >
                {message.type === "warning" && <AlertTriangle className="h-4 w-4" />}
                {message.text}
              </div>
            )}

            {/* Config file path */}
            <p className="text-xs text-muted-foreground text-center pt-2 border-t">
              Config: {settings.configPath}
            </p>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
