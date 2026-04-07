import Link from "next/link";
import { fmt$ } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { IssuePill } from "./IssueLabels";
import type { RentRollRow } from "@/lib/types";

export function UnitPeek({ row, propertyId }: { row: RentRollRow; propertyId: string }) {
  return (
    <div className="space-y-5 anim-fade-up">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-surface-sunken border border-border flex items-center justify-center">
          <span className="text-base font-bold text-fg font-mono">{row.unit_number}</span>
        </div>
        <div>
          <Badge
            variant={row.status === "occupied" ? "emerald" : row.status === "vacant" ? "red" : row.status === "maintenance" ? "amber" : "default"}
          >
            {row.status}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg bg-surface-sunken p-3">
          <p className="text-[10px] text-fg-muted uppercase tracking-wide">Rent</p>
          <p className="text-sm font-bold font-mono text-fg mt-0.5">{fmt$(row.current_rent)}</p>
        </div>
        <div className="rounded-lg bg-surface-sunken p-3">
          <p className="text-[10px] text-fg-muted uppercase tracking-wide">Market</p>
          <p className="text-sm font-bold font-mono text-fg mt-0.5">{fmt$(row.market_rent)}</p>
        </div>
        <div className={`rounded-lg p-3 ${row.rent_gap < 0 ? "bg-warn-soft" : "bg-ok-soft"}`}>
          <p className="text-[10px] text-fg-muted uppercase tracking-wide">Gap</p>
          <p className={`text-sm font-bold font-mono mt-0.5 ${row.rent_gap < 0 ? "text-warn-fg" : "text-ok-fg"}`}>
            {fmt$(row.rent_gap)}
          </p>
        </div>
      </div>

      <div className="flex gap-4 text-xs text-fg-muted">
        {row.bedrooms != null && <span>{row.bedrooms} bed / {row.bathrooms ?? "—"} bath</span>}
        {row.sqft != null && <span>{row.sqft.toLocaleString()} sq ft</span>}
        {row.floor != null && <span>Floor {row.floor}</span>}
      </div>

      {row.issues.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {row.issues.map((issue) => <IssuePill key={issue} issue={issue} />)}
        </div>
      )}

      <div className="rounded-xl border border-border p-4">
        <h4 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide mb-2">Lease &amp; Tenant</h4>
        {row.lease && row.tenant ? (
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center">
                <span className="text-accent font-bold text-[10px]">{row.tenant.name.charAt(0)}</span>
              </div>
              <div>
                <p className="text-fg font-medium text-xs">{row.tenant.name}</p>
                <p className="text-[10px] text-fg-muted">{row.tenant.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <Badge variant={row.lease.status === "active" ? "emerald" : "red"}>{row.lease.status}</Badge>
              <span className="text-fg-muted">{row.lease.start_date} → {row.lease.end_date}</span>
            </div>
            {row.lease.days_to_expiry != null && (
              <p className={`text-xs ${row.lease.days_to_expiry <= 30 ? "text-error font-medium" : row.lease.days_to_expiry <= 90 ? "text-warn" : "text-fg-muted"}`}>
                {row.lease.days_to_expiry > 0 ? `${row.lease.days_to_expiry} days until expiry` : `Expired ${Math.abs(row.lease.days_to_expiry)} days ago`}
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-fg-faint">No active lease</p>
        )}
      </div>

      {row.maintenance_items.length > 0 && (
        <div className="rounded-xl border border-border p-4">
          <h4 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide mb-2">
            Open Maintenance ({row.maintenance_items.length})
          </h4>
          <div className="space-y-2">
            {row.maintenance_items.map((mr) => (
              <div key={mr.id} className="flex items-center gap-2">
                <Badge variant={mr.priority === "emergency" ? "red" : mr.priority === "high" ? "amber" : "default"}>
                  {mr.priority}
                </Badge>
                <span className="text-xs text-fg-secondary truncate">{mr.title}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <Link
        href={`/properties/${propertyId}/units/${row.unit_id}`}
        className="block w-full text-center rounded-xl bg-accent text-accent-fg py-2.5 text-sm font-medium hover:bg-accent-hover transition-colors"
      >
        Open Full Unit Detail
      </Link>
    </div>
  );
}
