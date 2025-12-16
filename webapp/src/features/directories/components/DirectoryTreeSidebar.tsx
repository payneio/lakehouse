import { useLocation, useSearchParams, useNavigate } from 'react-router-dom';
import { DirectoriesList } from './DirectoriesList';
import { useUnreadCounts } from '@/hooks/useUnreadCounts';

interface DirectoryTreeSidebarProps {
  onNavigate?: () => void;
}

export function DirectoryTreeSidebar({ onNavigate }: DirectoryTreeSidebarProps) {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const isOnDirectoriesRoute = location.pathname.startsWith('/directories');

  // Fetch unread counts for badges
  const { data: unreadCounts } = useUnreadCounts();

  const selectedPath = isOnDirectoriesRoute ? searchParams.get('path') || undefined : undefined;

  const handleSelectDirectory = (path: string) => {
    navigate(`/directories?path=${encodeURIComponent(path)}`);
    onNavigate?.();
  };

  return (
    <div className="border-t pt-4 flex-1 overflow-hidden flex flex-col">
      <div className="px-4 pb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">Projects</h3>
      </div>
      <div className="flex-1 overflow-y-auto px-2">
        <DirectoriesList
          compact={true}
          onSelectDirectory={handleSelectDirectory}
          selectedPath={selectedPath}
          unreadCounts={unreadCounts || {}}
        />
      </div>
    </div>
  );
}
