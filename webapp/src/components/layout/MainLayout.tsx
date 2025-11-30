import { cn } from '@/lib/utils';
import { FolderOpen, Home, Package } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router';

export function MainLayout() {
  const [directoriesUrl] = useState(() => {
    // Read last Directories URL from sessionStorage on mount
    const lastUrl = sessionStorage.getItem('lastDirectoriesUrl');
    return lastUrl || '/directories';
  });

  return (
    <div className="flex h-screen">
      <aside
        className={cn(
          "w-64 border-r",
          "flex flex-col"
        )}
        style={{
          backgroundImage: 'url(/background.jpg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center'
        }}
      >
        <div className="p-4 border-b">
          <h1 className="text-xl font-bold">Amplifier</h1>
        </div>
        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            <li>
              <NavLink
                to="/home"
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive ? "bg-primary text-primary-foreground" : "hover:bg-gray-200"
                  )
                }
              >
                <Home className="h-4 w-4" />
                <span>Home</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/collections"
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive ? "bg-primary text-primary-foreground" : "hover:bg-gray-200"
                  )
                }
              >
                <Package className="h-4 w-4" />
                <span>Profiles</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to={directoriesUrl}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive ? "bg-primary text-primary-foreground" : "hover:bg-gray-200"
                  )
                }
              >
                <FolderOpen className="h-4 w-4" />
                <span>Projects</span>
              </NavLink>
            </li>
          </ul>
        </nav>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
