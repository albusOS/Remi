"use client";

import Link from "next/link";
import { fmt$ } from "@/lib/format";
import { MetricCard } from "@/components/ui/MetricCard";
import { MetricStrip } from "@/components/ui/MetricStrip";
import { Badge } from "@/components/ui/Badge";
import type { VacancyTracker } from "@/lib/types";

export function VacanciesTab({ data }: { data: VacancyTracker | null }) {
  if (!data || (data.total_vacant === 0 && data.total_notice === 0)) {
    return <p className="text-sm text-fg-faint text-center py-12">No vacant or notice units</p>;
  }

  return (
    <div className="space-y-4">
      <MetricStrip className="lg:grid-cols-4">
        <MetricCard label="Vacant" value={data.total_vacant} alert={data.total_vacant > 0} />
        <MetricCard label="On Notice" value={data.total_notice} alert={data.total_notice > 0} />
        <MetricCard label="Rent at Risk" value={fmt$(data.total_market_rent_at_risk)} alert />
        <MetricCard label="Avg Days Vacant" value={data.avg_days_vacant ?? "—"} />
      </MetricStrip>
      <div className="rounded-xl border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Property</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Unit</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Status</th>
                <th className="text-right px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Days Vacant</th>
                <th className="text-right px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Market Rent</th>
              </tr>
            </thead>
            <tbody>
              {data.units.map((u) => (
                <tr key={u.unit_id} className="border-b border-border-subtle hover:bg-surface-raised">
                  <td className="px-4 py-2">
                    <Link href={`/properties/${u.property_id}`} className="text-fg font-medium hover:text-accent transition-colors">{u.property_name}</Link>
                  </td>
                  <td className="px-4 py-2 font-mono">
                    <Link href={`/properties/${u.property_id}/units/${u.unit_id}`} className="text-fg-secondary hover:text-accent transition-colors">{u.unit_number}</Link>
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={u.occupancy_status?.includes("vacant") ? "red" : "amber"}>
                      {(u.occupancy_status || "vacant").replace(/_/g, " ")}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span className={u.days_vacant && u.days_vacant > 30 ? "text-error font-bold" : "text-fg-secondary"}>
                      {u.days_vacant ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right text-fg-secondary font-mono">{u.market_rent > 0 ? fmt$(u.market_rent) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
