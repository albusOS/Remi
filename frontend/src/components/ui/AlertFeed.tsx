"use client";

import Link from "next/link";

export interface AlertItem {
  id: string;
  label: string;
  sub?: string;
  count?: number;
  amount?: string;
  href: string;
  severity: "critical" | "warn" | "info";
  pulse?: boolean;
}

interface Props {
  alerts: AlertItem[];
  title?: string;
  className?: string;
}

const SEVERITY: Record<
  AlertItem["severity"],
  { dot: string; countColor: string; hover: string }
> = {
  critical: {
    dot: "bg-error",
    countColor: "text-error-fg",
    hover: "hover:bg-error-soft/40",
  },
  warn: {
    dot: "bg-warn",
    countColor: "text-warn-fg",
    hover: "hover:bg-warn-soft/40",
  },
  info: {
    dot: "bg-accent/60",
    countColor: "text-accent",
    hover: "hover:bg-accent-soft",
  },
};

export function AlertFeed({ alerts, title, className = "" }: Props) {
  if (!alerts.length) return null;

  return (
    <div className={`rounded-2xl border border-border bg-surface overflow-hidden ${className}`}>
      {title && (
        <div className="px-4 py-3 border-b border-border-subtle">
          <h3 className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest">
            {title}
          </h3>
        </div>
      )}
      <div className="divide-y divide-border-subtle">
        {alerts.map((a) => {
          const sev = SEVERITY[a.severity];
          return (
            <Link
              key={a.id}
              href={a.href}
              className={`flex items-center gap-3 px-4 py-3 transition-colors ${sev.hover} group`}
            >
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${sev.dot} ${a.pulse ? "animate-pulse" : ""}`}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-fg group-hover:text-accent transition-colors truncate">
                  {a.label}
                </p>
                {a.sub && (
                  <p className="text-[11px] text-fg-faint mt-0.5 truncate">{a.sub}</p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {a.count != null && (
                  <span className={`text-sm font-bold font-mono ${sev.countColor}`}>
                    {a.count}
                  </span>
                )}
                {a.amount && (
                  <span className="text-[11px] font-mono text-fg-muted">{a.amount}</span>
                )}
                <svg
                  className="w-3.5 h-3.5 text-fg-ghost group-hover:text-accent transition-colors"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="m8.25 4.5 7.5 7.5-7.5 7.5"
                  />
                </svg>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
