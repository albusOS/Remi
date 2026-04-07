"use client";

import React, { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { AskView } from "@/components/ask/AskView";
import { Dashboard } from "@/components/dashboard/Dashboard";
import { DocumentsView } from "@/components/documents/DocumentsView";

type WorkspaceTab = "remi" | "portfolio" | "documents";

const TABS: { id: WorkspaceTab; label: string; icon: React.ReactNode }[] = [
  {
    id: "remi",
    label: "REMI",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
      </svg>
    ),
  },
  {
    id: "portfolio",
    label: "Portfolio",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
  {
    id: "documents",
    label: "Documents",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
      </svg>
    ),
  },
];

function TabBar({
  active,
  onChange,
}: {
  active: WorkspaceTab;
  onChange: (tab: WorkspaceTab) => void;
}) {
  return (
    <div className="shrink-0 flex items-center gap-1 px-3 py-2 border-b border-border-subtle bg-surface">
      {TABS.map((tab) => {
        const isActive = active === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`
              relative flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all
              ${isActive
                ? "text-fg"
                : "text-fg-faint hover:text-fg-muted hover:bg-surface-raised"
              }
            `}
          >
            {tab.icon}
            <span>{tab.label}</span>
            {isActive && (
              <motion.div
                layoutId="workspace-tab-indicator"
                className="absolute inset-0 rounded-lg bg-surface-sunken -z-10"
                transition={{ type: "spring", bounce: 0.15, duration: 0.4 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

export function Workspace({ initialTab }: { initialTab?: WorkspaceTab }) {
  const searchParams = useSearchParams();
  const [active, setActive] = useState<WorkspaceTab>(initialTab ?? "remi");

  const handleTabChange = useCallback((tab: WorkspaceTab) => {
    setActive(tab);
  }, []);

  useEffect(() => {
    if (searchParams.get("tab")) {
      const t = searchParams.get("tab") as WorkspaceTab;
      if (["remi", "portfolio", "documents"].includes(t)) {
        setActive(t);
      }
    }
  }, [searchParams]);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <TabBar active={active} onChange={handleTabChange} />
      <div className="flex-1 overflow-hidden relative">
        <AnimatePresence mode="wait" initial={false}>
          {active === "remi" && (
            <motion.div
              key="remi"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="absolute inset-0"
            >
              <AskView />
            </motion.div>
          )}
          {active === "portfolio" && (
            <motion.div
              key="portfolio"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="absolute inset-0"
            >
              <Dashboard />
            </motion.div>
          )}
          {active === "documents" && (
            <motion.div
              key="documents"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="absolute inset-0"
            >
              <DocumentsView />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
