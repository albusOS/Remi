"use client";

import { useEffect, type ReactNode } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title?: string;
  width?: "sm" | "md" | "lg" | "xl";
  children: ReactNode;
}

const WIDTHS = {
  sm: "sm:max-w-sm",
  md: "sm:max-w-md",
  lg: "sm:max-w-lg",
  xl: "sm:max-w-xl",
};

export function SlidePanel({ open, onClose, title, width = "lg", children }: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Frosted overlay */}
      <div
        className="absolute inset-0 bg-fg/8 drawer-overlay"
        onClick={onClose}
      />
      {/* Panel with glass + glow edge */}
      <div
        className={`relative w-full ${WIDTHS[width]} h-full bg-surface/95 backdrop-blur-xl border-l border-border/60 shadow-2xl drawer-panel panel-glow flex flex-col`}
      >
        {/* Header with subtle gradient */}
        <div className="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-border-subtle shrink-0 bg-gradient-to-r from-surface to-surface-raised/50">
          {title && (
            <h2 className="text-sm font-semibold text-fg tracking-tight truncate mr-3">{title}</h2>
          )}
          <button
            onClick={onClose}
            className="ml-auto w-8 h-8 rounded-lg flex items-center justify-center text-fg-muted hover:text-fg hover:bg-surface-sunken transition-all hover:rotate-90 duration-200 shrink-0"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 sm:px-6 py-5">
          {children}
        </div>
      </div>
    </div>
  );
}
