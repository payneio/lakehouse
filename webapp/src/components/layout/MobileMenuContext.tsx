import { createContext, useContext, useState, type ReactNode } from "react";

interface MobileMenuContextType {
  isOpen: boolean;
  toggle: () => void;
  close: () => void;
}

const MobileMenuContext = createContext<MobileMenuContextType | null>(null);

export function MobileMenuProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  const toggle = () => setIsOpen((prev) => !prev);
  const close = () => setIsOpen(false);

  return (
    <MobileMenuContext.Provider value={{ isOpen, toggle, close }}>
      {children}
    </MobileMenuContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useMobileMenu() {
  const context = useContext(MobileMenuContext);
  if (!context) {
    throw new Error("useMobileMenu must be used within MobileMenuProvider");
  }
  return context;
}
