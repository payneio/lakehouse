import { Menu } from "lucide-react";
import { useMobileMenu } from "./MobileMenuContext";

interface MobileMenuButtonProps {
  className?: string;
}

export function MobileMenuButton({ className = "" }: MobileMenuButtonProps) {
  const { toggle } = useMobileMenu();

  return (
    <button
      onClick={toggle}
      className={`lg:hidden p-2 -ml-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground ${className}`}
      aria-label="Open menu"
    >
      <Menu className="h-5 w-5" />
    </button>
  );
}
