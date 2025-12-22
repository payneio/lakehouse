import { SettingsDialog } from "@/components/SettingsDialog";
import { DirectoryTreeSidebar } from "@/features/directories/components/DirectoryTreeSidebar";
import { cn } from "@/lib/utils";
import { FolderOpen, Home, Package, X } from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { MobileMenuProvider, useMobileMenu } from "./MobileMenuContext";

function MainLayoutContent() {
  const { isOpen, close } = useMobileMenu();

  return (
    <div className="flex h-screen">
      {/* Mobile menu backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={close}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "w-64 border-r flex flex-col bg-background",
          // Mobile: fixed positioning, slide in/out
          "fixed inset-y-0 left-0 z-40 transform transition-transform duration-300",
          isOpen ? "translate-x-0" : "-translate-x-full",
          // Desktop: static positioning, always visible
          "lg:relative lg:translate-x-0"
        )}
        style={{
          backgroundImage: "url(/background.jpg)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {/* Close button inside sidebar on mobile */}
        <button
          onClick={close}
          className="lg:hidden absolute top-4 right-4 p-2 rounded-md hover:bg-black/10"
          aria-label="Close menu"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="p-4 pr-14 lg:pr-4 flex items-center justify-between">
          <h1 className="text-xl font-bold">Lakehouse</h1>
          <SettingsDialog />
        </div>
        <nav className="p-4">
          <ul className="space-y-2">
            <li>
              <NavLink
                to="/home"
                onClick={close}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-gray-200"
                  )
                }
              >
                <Home className="h-4 w-4" />
                <span>Home</span>
              </NavLink>
            </li>
            <li>
              <NavLink
                to="/profiles"
                onClick={close}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-gray-200"
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
                onClick={close}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-gray-200"
                  )
                }
              >
                <FolderOpen className="h-4 w-4" />
                <span>Projects</span>
              </NavLink>
            </li>
          </ul>
        </nav>
        <DirectoryTreeSidebar onNavigate={close} />
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

export function MainLayout() {
  return (
    <MobileMenuProvider>
      <MainLayoutContent />
    </MobileMenuProvider>
  );
}
