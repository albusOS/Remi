"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { SessionSummary } from "@/lib/types";

function relativeTime(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onCreate,
  open,
  onClose,
}: {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  open: boolean;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="fixed inset-0 bg-fg/10 z-40"
            onClick={onClose}
          />

          <motion.div
            ref={ref}
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: "spring", damping: 28, stiffness: 320 }}
            className="fixed top-0 left-52 bottom-0 w-72 bg-surface border-r border-border z-50 flex flex-col shadow-xl"
          >
            <div className="shrink-0 p-4 flex items-center justify-between border-b border-border-subtle">
              <span className="text-xs font-semibold text-fg-muted tracking-wide uppercase">History</span>
              <button
                onClick={onClose}
                className="p-1 rounded-lg hover:bg-surface-sunken text-fg-faint hover:text-fg-secondary transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="px-3 py-3">
              <button
                onClick={() => { onCreate(); onClose(); }}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl border border-border text-sm text-fg-secondary hover:bg-surface-raised hover:border-fg-ghost transition-all"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                New conversation
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
              {sessions.map((s) => {
                const active = s.id === activeSessionId;
                return (
                  <button
                    key={s.id}
                    onClick={() => { onSelect(s.id); onClose(); }}
                    className={`w-full text-left px-3 py-2.5 rounded-xl transition-all ${
                      active
                        ? "bg-surface-sunken text-fg"
                        : "text-fg-muted hover:bg-surface-raised hover:text-fg-secondary"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {s.streaming && (
                        <span className="w-1.5 h-1.5 rounded-full bg-warn animate-pulse shrink-0" />
                      )}
                      <span className="text-[13px] font-medium truncate flex-1">
                        {s.preview || "New conversation"}
                      </span>
                    </div>
                    <div className="mt-0.5 pl-0.5">
                      <span className="text-[10px] text-fg-faint">
                        {relativeTime(s.updatedAt || s.createdAt)}
                      </span>
                    </div>
                  </button>
                );
              })}

              {sessions.length === 0 && (
                <p className="text-xs text-fg-faint text-center py-8">
                  No conversations yet
                </p>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
