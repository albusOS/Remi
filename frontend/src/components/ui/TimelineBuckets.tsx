"use client";

import Link from "next/link";
import { fmt$ } from "@/lib/format";

export interface TimeBucket {
  label: string;
  count: number;
  amount?: number;
  colorClass?: string;
}

interface Props {
  buckets: TimeBucket[];
  title?: string;
  total?: number;
  href?: string;
  className?: string;
}

export function TimelineBuckets({ buckets, title, total, href, className = "" }: Props) {
  const maxCount = Math.max(...buckets.map((b) => b.count), 1);

  return (
    <div className={`rounded-2xl border border-border bg-surface overflow-hidden ${className}`}>
      {title && (
        <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between">
          <h3 className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest">
            {title}
          </h3>
          <div className="flex items-center gap-3">
            {total != null && (
              <span className="text-[10px] text-fg-ghost">{total} total</span>
            )}
            {href && (
              <Link
                href={href}
                className="text-[10px] text-accent hover:text-accent-hover transition-colors"
              >
                View all →
              </Link>
            )}
          </div>
        </div>
      )}
      <div className="p-4 space-y-2.5">
        {buckets.map((b) => (
          <div key={b.label} className="flex items-center gap-3">
            <span className="text-[10px] text-fg-muted w-14 shrink-0 text-right font-mono">
              {b.label}
            </span>
            <div className="flex-1 bg-border-subtle rounded-full h-5 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${b.colorClass ?? "bg-accent/50"}`}
                style={{
                  width: `${Math.max((b.count / maxCount) * 100, b.count > 0 ? 8 : 0)}%`,
                }}
              />
            </div>
            <span className="text-xs font-semibold font-mono text-fg w-7 text-right shrink-0">
              {b.count > 0 ? b.count : "—"}
            </span>
            {b.amount != null && b.amount > 0 && (
              <span className="text-[10px] font-mono text-fg-muted w-20 text-right shrink-0">
                {fmt$(b.amount)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
