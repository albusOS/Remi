"use client";

import Link from "next/link";
import { fmt$, fmtDate } from "@/lib/format";
import { MetricCard } from "@/components/ui/MetricCard";
import { MetricStrip } from "@/components/ui/MetricStrip";
import { Badge } from "@/components/ui/Badge";
import type { LeaseCalendar } from "@/lib/types";

export function ManagerLeasesTab({ data }: { data: LeaseCalendar | null }) {
  if (!data || data.total_expiring === 0) {
    return <p className="text-sm text-fg-faint text-center py-12">No expiring leases in the next {data?.days_window || 90} days</p>;
  }

  return (
    <div className="space-y-4">
      <MetricStrip className="lg:grid-cols-3">
        <MetricCard label="Expiring" value={data.total_expiring} alert={data.total_expiring > 5} />
        <MetricCard label="Month-to-Month" value={data.month_to_month_count} alert={data.month_to_month_count > 0} />
        <MetricCard label="Window" value={`${data.days_window}d`} />
      </MetricStrip>
      <div className="rounded-xl border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Tenant</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Property</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Unit</th>
                <th className="text-right px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Rent</th>
                <th className="text-right px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Market</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Expires</th>
                <th className="text-right px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Days Left</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">MTM</th>
              </tr>
            </thead>
            <tbody>
              {data.leases.map((l) => (
                <tr key={l.lease_id} className="border-b border-border-subtle hover:bg-surface-raised">
                  <td className="px-4 py-2 text-fg font-medium">{l.tenant_name}</td>
                  <td className="px-4 py-2">
                    <Link href={`/properties/${l.property_id}`} className="text-fg-secondary hover:text-accent transition-colors">{l.property_name}</Link>
                  </td>
                  <td className="px-4 py-2 font-mono">
                    <Link href={`/properties/${l.property_id}/units/${l.unit_id}`} className="text-fg-secondary hover:text-accent transition-colors">{l.unit_number}</Link>
                  </td>
                  <td className="px-4 py-2 text-right text-fg-secondary font-mono">{fmt$(l.monthly_rent)}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    <span className={l.market_rent > l.monthly_rent ? "text-warn" : "text-fg-secondary"}>{fmt$(l.market_rent)}</span>
                  </td>
                  <td className="px-4 py-2 text-fg-secondary">{fmtDate(l.end_date)}</td>
                  <td className="px-4 py-2 text-right">
                    <span className={l.days_left <= 30 ? "text-error font-bold" : l.days_left <= 60 ? "text-warn" : "text-fg-secondary"}>
                      {l.days_left}
                    </span>
                  </td>
                  <td className="px-4 py-2">{l.is_month_to_month ? <Badge variant="amber">MTM</Badge> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
