import { cn } from '@/lib/utils';
import { FolderOpen, Home, Package } from 'lucide-react';
import { NavLink, Outlet } from 'react-router';
import { DirectoryTreeSidebar } from '@/features/directories/components/DirectoryTreeSidebar';

export function MainLayout() {
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
        <div className="p-4">
          <h1 className="text-xl font-bold">Amplifier</h1>
        </div>
        <nav className="p-4">
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
                to="/directories"
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
        <DirectoryTreeSidebar />
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
