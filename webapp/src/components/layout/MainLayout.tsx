import { DirectoryTreeSidebar } from "@/features/directories/components/DirectoryTreeSidebar";
import { cn } from "@/lib/utils";
import { FolderOpen, Home, Menu, Package, X } from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { useState } from "react";

export function MainLayout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const closeMobileMenu = () => setIsMobileMenuOpen(false);

  return (
    <div className="flex h-screen">
      {/* Mobile menu backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Hamburger button - visible only on mobile */}
      <button
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        className="fixed top-4 left-4 z-50 p-2 rounded-md bg-white shadow-lg lg:hidden hover:bg-gray-100"
        aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
      >
        {isMobileMenuOpen ? (
          <X className="h-6 w-6" />
        ) : (
          <Menu className="h-6 w-6" />
        )}
      </button>

      {/* Sidebar */}
      <aside
        className={cn(
          "w-64 border-r flex flex-col",
          // Mobile: fixed positioning, slide in/out
          "fixed inset-y-0 left-0 z-40 transform transition-transform duration-300",
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-full",
          // Desktop: static positioning, always visible
          "lg:relative lg:translate-x-0"
        )}
        style={{
          backgroundImage: "url(/background.jpg)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="p-4">
          <h1 className="text-xl font-bold">Lakehouse</h1>
        </div>
        <nav className="p-4">
          <ul className="space-y-2">
            <li>
              <NavLink
                to="/home"
                onClick={closeMobileMenu}
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
                onClick={closeMobileMenu}
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
                onClick={closeMobileMenu}
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
        <DirectoryTreeSidebar onNavigate={closeMobileMenu} />
      </aside>

      {/* Main content - add left padding on mobile to account for hamburger button */}
      <main className="flex-1 overflow-auto lg:ml-0">
        <Outlet />
      </main>
    </div>
  );
}
