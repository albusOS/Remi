"use client";

import Link from "next/link";
import { fmt$ } from "@/lib/format";

export interface PipelineStage {
  id: string;
  label: string;
  count: number;
  amount?: number;
  variant?: "default" | "ok" | "warn" | "error";
}

interface Props {
  stages: PipelineStage[];
  title?: string;
  href?: string;
  className?: string;
}

const STYLES: Record<string, { bg: string; text: string; count: string; border: string }> = {
  default: {
    bg: "bg-surface-raised",
    text: "text-fg-muted",
    count: "text-fg-ghost",
    border: "border-border",
  },
  ok: {
    bg: "bg-surface-raised",
    text: "text-ok",
    count: "text-ok",
    border: "border-ok/20",
  },
  warn: {
    bg: "bg-warn-soft",
    text: "text-warn-fg",
    count: "text-warn-fg",
    border: "border-warn/20",
  },
  error: {
    bg: "bg-error-soft",
    text: "text-error-fg",
    count: "text-error-fg",
    border: "border-error/20",
  },
};

export function PipelineStrip({ stages, title, href, className = "" }: Props) {
  return (
    <div className={`rounded-2xl border border-border bg-surface overflow-hidden ${className}`}>
      {title && (
        <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between">
          <h3 className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest">
            {title}
          </h3>
          {href && (
            <Link
              href={href}
              className="text-[10px] text-accent hover:text-accent-hover transition-colors"
            >
              View all →
            </Link>
          )}
        </div>
      )}
      <div className="flex overflow-x-auto scrollbar-none p-3 gap-1.5 items-stretch">
        {stages.map((stage, i) => {
          const active = stage.count > 0;
          const s = STYLES[active ? (stage.variant ?? "default") : "default"];
          const isLast = i === stages.length - 1;
          return (
            <div key={stage.id} className="flex items-center gap-1.5 min-w-0 flex-1">
              <div
                className={`flex-1 rounded-xl border px-3 py-2.5 min-w-[72px] transition-colors ${s.bg} ${s.border}`}
              >
                <p
                  className={`text-[9px] font-semibold uppercase tracking-widest mb-1 ${s.text}`}
                >
                  {stage.label}
                </p>
                <p
                  className={`text-xl font-bold font-mono tracking-tight ${active ? s.count : "text-fg-ghost"}`}
                >
                  {stage.count}
                </p>
                {stage.amount != null && stage.amount > 0 && (
                  <p className={`text-[10px] font-mono mt-0.5 ${s.text}`}>
                    {fmt$(stage.amount)}
                  </p>
                )}
              </div>
              {!isLast && (
                <svg
                  className="w-3 h-3 text-fg-ghost shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="m8.25 4.5 7.5 7.5-7.5 7.5"
                  />
                </svg>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
