"use client";

import Link from "next/link";
import { fmt$, pct } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";

export interface PropertyHealth {
  id: string;
  name: string;
  total_units: number;
  occupied: number;
  occupancy_rate: number;
  monthly_actual: number;
  loss_to_lease?: number;
  open_maintenance?: number;
  issue_count?: number;
  manager_name?: string;
}

interface Props {
  property: PropertyHealth;
  className?: string;
}

export function PropertyHealthCard({ property: p, className = "" }: Props) {
  const occBarColor =
    p.occupancy_rate >= 0.95 ? "bg-ok" : p.occupancy_rate >= 0.9 ? "bg-warn" : "bg-error";
  const occTextColor =
    p.occupancy_rate >= 0.95
      ? "text-ok"
      : p.occupancy_rate >= 0.9
        ? "text-warn"
        : "text-error";
  const hasIssues = (p.issue_count ?? 0) > 0;

  return (
    <Link
      href={`/properties/${p.id}`}
      className={`rounded-2xl border ${hasIssues ? "border-warn/25" : "border-border"} bg-surface p-4 card-hover group transition-all hover:border-accent/20 block ${className}`}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-fg group-hover:text-accent transition-colors truncate">
            {p.name}
          </p>
          {p.manager_name && (
            <p className="text-[10px] text-fg-faint mt-0.5 truncate">{p.manager_name}</p>
          )}
        </div>
        {hasIssues && (
          <span className="w-1.5 h-1.5 rounded-full bg-warn shrink-0 mt-1.5 animate-pulse" />
        )}
      </div>

      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] text-fg-faint uppercase tracking-wider">
            {p.occupied}/{p.total_units} units
          </span>
          <span className={`text-[10px] font-mono font-semibold ${occTextColor}`}>
            {pct(p.occupancy_rate)}
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-border-subtle overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${occBarColor}`}
            style={{ width: `${Math.min(p.occupancy_rate * 100, 100)}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs font-mono font-semibold text-fg-secondary">
          {fmt$(p.monthly_actual)}
        </span>
        <div className="flex items-center gap-1.5">
          {(p.loss_to_lease ?? 0) > 0 && (
            <Badge variant="amber">-{fmt$(p.loss_to_lease!)} LTL</Badge>
          )}
          {(p.open_maintenance ?? 0) > 0 && (
            <Badge variant="cyan">{p.open_maintenance} maint</Badge>
          )}
        </div>
      </div>
    </Link>
  );
}
