"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type AppMode = "director" | "manager" | "owner";

interface ModeState {
  mode: AppMode;
  setMode: (m: AppMode) => void;
  scopedManagerId: string | undefined;
  setScopedManagerId: (id: string | undefined) => void;
}

const ModeContext = createContext<ModeState | null>(null);

const MODE_KEY = "remi_app_mode";
const MANAGER_KEY = "remi_scoped_manager";

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<AppMode>("director");
  const [scopedManagerId, setScopedState] = useState<string | undefined>(undefined);

  useEffect(() => {
    const stored = localStorage.getItem(MODE_KEY) as AppMode | null;
    if (stored && ["director", "manager", "owner"].includes(stored)) {
      setModeState(stored);
    }
    const storedMgr = localStorage.getItem(MANAGER_KEY);
    if (storedMgr) setScopedState(storedMgr);
  }, []);

  const setMode = useCallback((m: AppMode) => {
    setModeState(m);
    localStorage.setItem(MODE_KEY, m);
  }, []);

  const setScopedManagerId = useCallback((id: string | undefined) => {
    setScopedState(id);
    if (id) localStorage.setItem(MANAGER_KEY, id);
    else localStorage.removeItem(MANAGER_KEY);
  }, []);

  return (
    <ModeContext.Provider value={{ mode, setMode, scopedManagerId, setScopedManagerId }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode(): ModeState {
  const ctx = useContext(ModeContext);
  if (!ctx) throw new Error("useMode must be used inside ModeProvider");
  return ctx;
}

export const MODE_META: Record<AppMode, { label: string; icon: string; description: string }> = {
  director: {
    label: "Director",
    icon: "M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5m.75-9 3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605",
    description: "Cross-portfolio view across all managers",
  },
  manager: {
    label: "Manager",
    icon: "M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z",
    description: "Single manager's portfolio, operational view",
  },
  owner: {
    label: "Owner",
    icon: "M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25",
    description: "Property financial performance, owner lens",
  },
};
