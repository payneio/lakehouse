import { useUnreadCounts } from "@/hooks/useUnreadCounts";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { ProjectsList } from "./ProjectsList";

interface ProjectTreeSidebarProps {
  onNavigate?: () => void;
}

export function ProjectTreeSidebar({
  onNavigate,
}: ProjectTreeSidebarProps) {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const isOnProjectsRoute = location.pathname.startsWith("/projects");

  // Fetch unread counts for badges
  const { data: unreadCounts } = useUnreadCounts();

  const selectedPath = isOnProjectsRoute
    ? searchParams.get("path") || undefined
    : undefined;

  const handleSelectDirectory = (path: string) => {
    navigate(`/projects?path=${encodeURIComponent(path)}`);
    onNavigate?.();
  };

  return (
    <div className="border-t pt-4 flex-1 overflow-hidden flex flex-col">
      <div className="px-4 pb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">Projects</h3>
      </div>
      <div className="flex-1 overflow-y-auto px-2">
        <ProjectsList
          compact={true}
          onSelectDirectory={handleSelectDirectory}
          selectedPath={selectedPath}
          unreadCounts={unreadCounts || {}}
        />
      </div>
    </div>
  );
}
