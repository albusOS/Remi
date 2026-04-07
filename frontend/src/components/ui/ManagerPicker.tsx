"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ManagerListItem } from "@/lib/types";

export function ManagerPicker({
  currentManagerId,
  currentManagerName,
  onAssign,
}: {
  currentManagerId: string | null;
  currentManagerName: string | null;
  onAssign: (managerId: string | null) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [managers, setManagers] = useState<ManagerListItem[]>([]);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && managers.length === 0) {
      api.listManagers().then(setManagers).catch(() => {});
    }
  }, [open, managers.length]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function handleSelect(managerId: string | null) {
    setSaving(true);
    try {
      await onAssign(managerId);
    } finally {
      setSaving(false);
      setOpen(false);
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 text-xs rounded-lg px-2.5 py-1.5 border transition-all ${
          currentManagerId
            ? "border-accent/20 bg-accent/5 text-accent hover:bg-accent/10"
            : "border-dashed border-violet-500/30 bg-violet-500/5 text-violet-400 hover:bg-violet-500/10 hover:border-violet-500/50"
        }`}
        disabled={saving}
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
        </svg>
        {saving ? "Saving..." : currentManagerName ?? "Assign manager"}
        <svg className="w-3 h-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1.5 z-50 w-64 rounded-xl border border-border bg-surface shadow-xl shadow-black/20 overflow-hidden anim-scale-in">
          <div className="px-3 py-2 border-b border-border-subtle">
            <p className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest">Assign to manager</p>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {currentManagerId && (
              <button
                onClick={() => handleSelect(null)}
                className="w-full text-left px-3 py-2.5 text-xs text-fg-muted hover:bg-surface-sunken transition-colors border-b border-border-subtle"
              >
                Unassign (remove manager)
              </button>
            )}
            {managers.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-fg-faint">Loading managers...</div>
            ) : (
              managers.map((m) => (
                <button
                  key={m.id}
                  onClick={() => handleSelect(m.id)}
                  className={`w-full text-left px-3 py-2.5 text-xs hover:bg-surface-sunken transition-colors flex items-center justify-between gap-2 ${
                    m.id === currentManagerId ? "text-accent font-medium bg-accent/5" : "text-fg"
                  }`}
                >
                  <span className="truncate">{m.name}</span>
                  {m.id === currentManagerId && (
                    <svg className="w-3.5 h-3.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
