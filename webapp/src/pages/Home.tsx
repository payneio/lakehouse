import { BASE_URL } from "@/api/client";
import { useMobileMenu } from "@/components/layout/MobileMenuContext";
import {
  ArrowRight,
  BookOpen,
  FolderOpen,
  FolderPlus,
  Menu,
  MessageSquare,
  Settings,
  Users,
  Workflow,
} from "lucide-react";
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
        const response = await fetch(`${BASE_URL}/api/v1/status`, {
          mode: "cors",
        });

        const data = await response.json();
        setApiStatus("connected");
        setApiVersion(data.version || "unknown");
        setDataPath(data.rootDir || "");

        // Fetch system info for debugging
        try {
          const infoResponse = await fetch(`${BASE_URL}/api/info`, {
            mode: "cors",
          });
          const infoData = await infoResponse.json();
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
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Your Intelligent Computation Platform. Works directly on your data,
            building custom tools and workflows on the fly. No apps, no
            limits—just you and your computer, working together.
          </p>

          {/* Status Indicator */}
          <StatusIndicator
            status={apiStatus}
            version={apiVersion}
            dataPath={dataPath}
          />

          {/* Debug Info */}
          {systemInfo && (
            <DebugInfo systemInfo={systemInfo} />
          )}

          {/* Primary CTA */}
          <div className="pt-4">
            <Link
              to="/directories"
              className="inline-flex items-center gap-2 px-8 py-4 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-semibold text-lg"
            >
              <FolderPlus className="h-5 w-5" />
              Create Project
              <ArrowRight className="h-5 w-5" />
            </Link>
          </div>
        </div>
      </section>

      {/* Quick Start Section */}
      <section className="py-12 px-8 max-w-7xl mx-auto">
        <h2 className="text-3xl font-semibold text-center mb-8">Get Started</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <StepCard
            step={1}
            title="Amplify a Directory"
            description="Turn any folder into an intelligent project with its own context and chat history."
            icon={<FolderOpen className="h-6 w-6" />}
          />
          <StepCard
            step={2}
            title="Start a Chat Session"
            description="Interact naturally with your data using AI-powered conversations."
            icon={<MessageSquare className="h-6 w-6" />}
          />
          <StepCard
            step={3}
            title="Switch Profiles"
            description="Customize agent behavior for different domains and tasks."
            icon={<Users className="h-6 w-6" />}
          />
        </div>
      </section>

      {/* Key Concepts Section */}
      <section className="py-16 px-8 max-w-7xl mx-auto bg-muted/30">
        <h2 className="text-3xl font-semibold text-center mb-12">
          Four Core Concepts
        </h2>
        <div className="grid md:grid-cols-2 gap-6">
          <ConceptCard
            title="Your Data, Your Control"
            description="Works on YOUR directories. Your data stays local, private, and under your control."
            icon={<FolderOpen className="h-8 w-8" />}
            linkText="Configure data path"
            linkTo="/directories"
          />
          <ConceptCard
            title="Contextual Intelligence"
            description="Different expertise for different tasks. Switch profiles to customize agent behavior."
            icon={<Users className="h-8 w-8" />}
            linkText="Browse profiles"
            linkTo="/collections"
          />
          <ConceptCard
            title="Always Learning"
            description="The daemon runs continuously, enabling scheduled workflows and reactive automation."
            icon={<Workflow className="h-8 w-8" />}
            linkText="View automation"
            linkTo="/home"
            isPlaceholder
          />
          <ConceptCard
            title="Project Organization"
            description="Each project has its own context, chat history, and workflows."
            icon={<Settings className="h-8 w-8" />}
            linkText="See projects"
            linkTo="/directories"
          />
        </div>
      </section>

      {/* Help Resources Footer */}
      <section className="py-12 px-8 max-w-7xl mx-auto">
        <div className="border-t pt-8">
          <h3 className="text-xl font-semibold mb-4">Help & Resources</h3>
          <div className="grid md:grid-cols-4 gap-4">
            <ResourceLink
              icon={<BookOpen className="h-5 w-5" />}
              title="Vision Document"
              href="https://github.com/payneio/lakehouse/blob/main/amplifierd/docs/the-amplifier-computation-platform.md"
            />
            <ResourceLink
              icon={<BookOpen className="h-5 w-5" />}
              title="Getting Started"
              href="/home"
              isPlaceholder
            />
            <ResourceLink
              icon={<Workflow className="h-5 w-5" />}
              title="Example Workflows"
              href="/home"
              isPlaceholder
            />
            <ResourceLink
              icon={<MessageSquare className="h-5 w-5" />}
              title="Support & Feedback"
              href="/home"
              isPlaceholder
            />
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

interface StepCardProps {
  step: number;
  title: string;
  description: string;
  icon: React.ReactNode;
}

function StepCard({ step, title, description, icon }: StepCardProps) {
  return (
    <div className="relative p-6 border rounded-lg bg-background hover:border-primary/50 transition-colors">
      <div className="absolute -top-3 -left-3 w-8 h-8 bg-primary text-primary-foreground rounded-full flex items-center justify-center font-bold">
        {step}
      </div>
      <div className="flex items-center gap-3 mb-3">
        <div className="text-primary">{icon}</div>
        <h3 className="text-xl font-semibold">{title}</h3>
      </div>
      <p className="text-muted-foreground">{description}</p>
    </div>
  );
}

interface ConceptCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  linkText: string;
  linkTo: string;
  isPlaceholder?: boolean;
}

function ConceptCard({
  title,
  description,
  icon,
  linkText,
  linkTo,
  isPlaceholder,
}: ConceptCardProps) {
  return (
    <div className="p-6 border rounded-lg bg-background hover:border-primary/50 transition-colors">
      <div className="flex items-start gap-4 mb-4">
        <div className="text-primary">{icon}</div>
        <div>
          <h3 className="text-xl font-semibold mb-2">{title}</h3>
          <p className="text-muted-foreground">{description}</p>
        </div>
      </div>
      {isPlaceholder ? (
        <span className="text-sm text-muted-foreground italic">
          {linkText} (coming soon)
        </span>
      ) : (
        <Link
          to={linkTo}
          className="text-sm text-primary hover:underline inline-flex items-center gap-1"
        >
          {linkText}
          <ArrowRight className="h-3 w-3" />
        </Link>
      )}
    </div>
  );
}

interface ResourceLinkProps {
  icon: React.ReactNode;
  title: string;
  href: string;
  isPlaceholder?: boolean;
}

function ResourceLink({ icon, title, href, isPlaceholder }: ResourceLinkProps) {
  if (isPlaceholder) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-sm">{title}</span>
        <span className="text-xs italic">(coming soon)</span>
      </div>
    );
  }

  const isExternal = href.startsWith("http");

  if (isExternal) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2 text-primary hover:underline"
      >
        {icon}
        <span className="text-sm">{title}</span>
      </a>
    );
  }

  return (
    <Link
      to={href}
      className="flex items-center gap-2 text-primary hover:underline"
    >
      {icon}
      <span className="text-sm">{title}</span>
    </Link>
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
