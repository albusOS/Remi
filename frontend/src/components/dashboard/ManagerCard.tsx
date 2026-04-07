import Link from "next/link";
import { fmt$, pct } from "@/lib/format";
import type { ManagerOverview, PropertyOverview } from "@/lib/types";

export function ManagerCard({ mgr, properties }: { mgr: ManagerOverview; properties: PropertyOverview[] }) {
  const m = mgr.metrics;
  const occColor = m.occupancy_rate >= 0.95 ? "text-ok" : m.occupancy_rate >= 0.9 ? "text-warn" : "text-error";

  return (
    <Link
      href={`/managers/${mgr.manager_id}`}
      className="rounded-2xl border border-border bg-surface p-5 card-hover group transition-all hover:border-accent/20"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-accent/10 flex items-center justify-center shrink-0 group-hover:bg-accent/20 transition-colors">
            <span className="text-sm font-bold text-accent">{mgr.manager_name.charAt(0)}</span>
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-fg truncate group-hover:text-accent transition-colors">{mgr.manager_name}</p>
            <p className="text-[10px] text-fg-faint">{mgr.property_count} {mgr.property_count === 1 ? "property" : "properties"}</p>
          </div>
        </div>
        <svg className="w-4 h-4 text-fg-ghost group-hover:text-accent group-hover:translate-x-0.5 transition-all shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-lg font-bold text-fg tracking-tight">{m.total_units}</p>
          <p className="text-[9px] text-fg-faint uppercase tracking-widest">units</p>
        </div>
        <div>
          <p className={`text-lg font-bold tracking-tight ${occColor}`}>{pct(m.occupancy_rate)}</p>
          <p className="text-[9px] text-fg-faint uppercase tracking-widest">occupied</p>
        </div>
        <div>
          <p className="text-lg font-bold text-fg tracking-tight">{fmt$(m.total_actual_rent)}</p>
          <p className="text-[9px] text-fg-faint uppercase tracking-widest">rent</p>
        </div>
      </div>

      {(m.loss_to_lease > 0 || m.open_maintenance > 0 || m.expiring_leases_90d > 0) && (
        <div className="flex gap-3 mt-3 pt-3 border-t border-border-subtle flex-wrap">
          {m.loss_to_lease > 0 && (
            <span className="text-[10px] text-warn">{fmt$(m.loss_to_lease)} LTL</span>
          )}
          {m.open_maintenance > 0 && (
            <span className="text-[10px] text-sky-400">{m.open_maintenance} maint</span>
          )}
          {m.expiring_leases_90d > 0 && (
            <span className="text-[10px] text-fg-muted">{m.expiring_leases_90d} expiring</span>
          )}
        </div>
      )}
    </Link>
  );
}
