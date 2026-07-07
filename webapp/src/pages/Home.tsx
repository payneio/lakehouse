import { fetchApi } from "@/api/client";
import { useMobileMenu } from "@/components/layout/MobileMenuContext";
import { ArrowRight, FolderPlus, Menu, Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";

interface SystemInfo {
  daemonPath: string;
  daemonPid: number;
  webappPath: string;
  webappUrl: string;
}

export function HomePage() {
  const { toggle, isOpen } = useMobileMenu();
  const [apiStatus, setApiStatus] = useState<
    "checking" | "connected" | "error"
  >("checking");
  const [apiVersion, setApiVersion] = useState<string>("");
  const [dataPath, setDataPath] = useState<string>("");
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);

  useEffect(() => {
    // Check API connection on mount
    const checkConnection = async () => {
      try {
        const data = await fetchApi<{ version?: string; rootDir?: string }>(
          "/api/v1/status"
        );
        setApiStatus("connected");
        setApiVersion(data.version || "unknown");
        setDataPath(data.rootDir || "");

        // Fetch system info for debugging
        try {
          const infoData = await fetchApi<{
            daemon_path: string;
            daemon_pid: number;
            webapp_path: string;
            webapp_url: string;
          }>("/api/info");
          setSystemInfo({
            daemonPath: infoData.daemon_path,
            daemonPid: infoData.daemon_pid,
            webappPath: infoData.webapp_path,
            webappUrl: infoData.webapp_url,
          });
        } catch {
          // System info is optional, don't fail if it's not available
          console.warn("Could not fetch system info");
        }
      } catch {
        setApiStatus("error");
      }
    };

    checkConnection();
  }, []);

  return (
    <div className="min-h-screen">
      {/* Floating menu button for mobile - hidden when menu is open */}
      {!isOpen && (
        <button
          onClick={toggle}
          className="lg:hidden fixed top-4 left-4 z-30 p-2 rounded-md bg-background shadow-lg hover:bg-accent"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}

      {/* Hero Section */}
      <section className="py-16 px-8 max-w-7xl mx-auto">
        <div className="text-center space-y-6">
          <h1 className="text-5xl font-bold">Amplifier: Lakehouse</h1>

          {/* Status Indicator */}
          <StatusIndicator
            status={apiStatus}
            version={apiVersion}
            dataPath={dataPath}
          />

          {/* Debug Info */}
          {systemInfo && <DebugInfo systemInfo={systemInfo} />}

          {/* Primary CTA */}
          <div className="pt-4">
            <Link
              to="/projects"
              className="inline-flex items-center gap-2 px-8 py-4 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-semibold text-lg"
            >
              <FolderPlus className="h-5 w-5" />
              Create Project
              <ArrowRight className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

// Sub-components following "bricks and studs" philosophy

interface StatusIndicatorProps {
  status: "checking" | "connected" | "error";
  version: string;
  dataPath: string;
}

function StatusIndicator({ status, version, dataPath }: StatusIndicatorProps) {
  const getStatusColor = () => {
    switch (status) {
      case "connected":
        return "bg-green-100 text-green-800 border-green-300";
      case "error":
        return "bg-red-100 text-red-800 border-red-300";
      default:
        return "bg-yellow-100 text-yellow-800 border-yellow-300";
    }
  };

  const getStatusText = () => {
    switch (status) {
      case "connected":
        return "Connected";
      case "error":
        return "Disconnected";
      default:
        return "Checking...";
    }
  };

  return (
    <div className="inline-flex items-center gap-4 px-6 py-3 border rounded-lg bg-background">
      <div className="flex items-center gap-2">
        <div
          className={`px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor()}`}
        >
          {getStatusText()}
        </div>
      </div>
      {version && (
        <div className="text-sm text-muted-foreground border-l pl-4">
          v{version}
        </div>
      )}
      {dataPath && (
        <div className="text-sm text-muted-foreground border-l pl-4 font-mono max-w-xs truncate">
          {dataPath}
        </div>
      )}
      {status === "error" && (
        <div className="text-xs text-destructive border-l pl-4">
          Cannot connect to daemon
        </div>
      )}
    </div>
  );
}

interface DebugInfoProps {
  systemInfo: SystemInfo;
}

function DebugInfo({ systemInfo }: DebugInfoProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="mt-4 max-w-3xl mx-auto">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-2"
      >
        <Settings className="h-3 w-3" />
        {isExpanded ? "Hide" : "Show"} system info
      </button>

      {isExpanded && (
        <div className="mt-3 p-4 border rounded-lg bg-muted/30 text-left space-y-2">
          <div className="text-xs font-mono space-y-1">
            <div className="flex items-start gap-2">
              <span className="text-muted-foreground min-w-[100px]">Daemon:</span>
              <span className="break-all">{systemInfo.daemonPath}</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-muted-foreground min-w-[100px]">Daemon PID:</span>
              <span>{systemInfo.daemonPid}</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-muted-foreground min-w-[100px]">Webapp:</span>
              <span className="break-all">{systemInfo.webappPath}</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-muted-foreground min-w-[100px]">Webapp URL:</span>
              <span>{systemInfo.webappUrl}</span>
            </div>
          </div>
          <div className="pt-2 border-t text-xs text-muted-foreground">
            This info helps with debugging. Daemon and webapp paths show where the services are running from.
          </div>
        </div>
      )}
    </div>
  );
}
