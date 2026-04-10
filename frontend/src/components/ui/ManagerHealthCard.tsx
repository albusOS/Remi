"use client";

import Link from "next/link";
import { fmt$, pct } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import type { ManagerListItem } from "@/lib/types";

interface Props {
  manager: ManagerListItem;
  className?: string;
}

export function ManagerHealthCard({ manager: m, className = "" }: Props) {
  const occ = m.metrics.occupancy_rate;
  const occBarColor = occ >= 0.95 ? "bg-ok" : occ >= 0.9 ? "bg-warn" : "bg-error";
  const occTextColor = occ >= 0.95 ? "text-ok" : occ >= 0.9 ? "text-warn" : "text-error";
  const urgent =
    m.emergency_maintenance > 0 || m.expired_leases > 0 || m.delinquent_count > 5;

  return (
    <Link
      href={`/managers/${m.id}`}
      className={`rounded-2xl border ${urgent ? "border-error/20" : "border-border"} bg-surface p-5 card-hover group transition-all hover:border-accent/20 block ${className}`}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-accent/10 flex items-center justify-center shrink-0 group-hover:bg-accent/20 transition-colors">
            <span className="text-sm font-bold text-accent">{m.name.charAt(0)}</span>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-fg group-hover:text-accent transition-colors truncate">
              {m.name}
            </p>
            <p className="text-[10px] text-fg-faint">
              {m.property_count} {m.property_count === 1 ? "property" : "properties"} ·{" "}
              {m.metrics.total_units} units
            </p>
          </div>
        </div>
        {urgent && (
          <span className="w-1.5 h-1.5 rounded-full bg-error animate-pulse shrink-0 mt-1" />
        )}
      </div>

      <div className="mb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] text-fg-faint uppercase tracking-wider">
            {m.metrics.occupied}/{m.metrics.total_units} occupied
          </span>
          <span className={`text-[10px] font-mono font-semibold ${occTextColor}`}>
            {pct(occ)}
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-border-subtle overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${occBarColor}`}
            style={{ width: `${Math.min(occ * 100, 100)}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] text-fg-faint">Revenue</span>
        <span className="text-sm font-bold font-mono text-fg">
          {fmt$(m.metrics.total_actual_rent)}
        </span>
      </div>

      {(m.delinquent_count > 0 ||
        m.metrics.vacant > 0 ||
        m.expired_leases > 0 ||
        m.metrics.expiring_leases_90d > 0 ||
        m.metrics.open_maintenance > 0) && (
        <div className="flex flex-wrap gap-1 pt-3 border-t border-border-subtle">
          {m.delinquent_count > 0 && (
            <Badge variant="red">{m.delinquent_count} delinq</Badge>
          )}
          {m.metrics.vacant > 0 && <Badge variant="red">{m.metrics.vacant} vacant</Badge>}
          {m.expired_leases > 0 && (
            <Badge variant="red">{m.expired_leases} expired</Badge>
          )}
          {m.metrics.expiring_leases_90d > 0 && (
            <Badge variant="amber">{m.metrics.expiring_leases_90d} expiring</Badge>
          )}
          {m.metrics.open_maintenance > 0 && (
            <Badge variant="cyan">{m.metrics.open_maintenance} maint</Badge>
          )}
        </div>
      )}
    </Link>
  );
}
