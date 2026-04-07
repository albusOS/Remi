"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { fmt$, fmtDate } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { MetricCard } from "@/components/ui/MetricCard";
import { Badge } from "@/components/ui/Badge";
import { SparklineChart } from "@/components/ui/SparklineChart";
import type { MaintenanceTrend } from "@/lib/types";

function MaintenanceTrendCharts({ trend }: { trend: MaintenanceTrend }) {
  const periods = trend.periods;
  if (periods.length < 2) return null;

  const latestOpen = periods[periods.length - 1]?.opened ?? 0;
  const latestCost = periods[periods.length - 1]?.total_cost ?? 0;
  const latestRes = periods[periods.length - 1]?.avg_resolution_days;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <SparklineChart
        data={periods}
        dataKey="opened"
        color="var(--color-warn)"
        label="Opened / Month"
        value={String(latestOpen)}
        invertTrend
      />
      <SparklineChart
        data={periods}
        dataKey="total_cost"
        color="var(--color-error)"
        label="Cost / Month"
        value={fmt$(latestCost)}
        valueFormatter={(v) => fmt$(v)}
        invertTrend
      />
      <SparklineChart
        data={periods}
        dataKey="avg_resolution_days"
        color="var(--color-accent)"
        label="Avg Resolution (days)"
        value={latestRes != null ? `${latestRes}d` : "—"}
        valueFormatter={(v) => `${v.toFixed(1)}d`}
        invertTrend
      />
    </div>
  );
}

export function PropertyMaintenanceTab({ propertyId }: { propertyId: string }) {
  const { data: list, loading: listLoading } = useApiQuery(() => api.listMaintenance({ property_id: propertyId }), [propertyId]);
  const { data: summary, loading: sumLoading } = useApiQuery(() => api.maintenanceSummary({ property_id: propertyId }), [propertyId]);
  const { data: trend } = useApiQuery(() => api.maintenanceTrend({ property_id: propertyId }), [propertyId]);
  if (listLoading || sumLoading) return <div className="py-12 text-center text-sm text-fg-faint animate-pulse">Loading maintenance...</div>;

  const openCount = (summary?.by_status["open"] ?? 0) + (summary?.by_status["in_progress"] ?? 0);
  const completedCount = summary?.by_status["completed"] ?? 0;

  return (
    <div className="space-y-4 anim-fade-up">
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 stagger">
          <MetricCard label="Total" value={summary.total} />
          <MetricCard label="Open" value={openCount} alert={openCount > 0} />
          <MetricCard label="Completed" value={completedCount} />
          <MetricCard label="Total Cost" value={fmt$(summary.total_cost)} />
        </div>
      )}

      {trend && <MaintenanceTrendCharts trend={trend} />}

      {trend && trend.periods.length > 0 && (() => {
        const allCats: Record<string, number> = {};
        for (const p of trend.periods) {
          for (const [cat, count] of Object.entries(p.by_category)) {
            allCats[cat] = (allCats[cat] ?? 0) + count;
          }
        }
        const sorted = Object.entries(allCats).sort(([, a], [, b]) => b - a);
        if (sorted.length === 0) return null;
        const max = sorted[0][1];
        return (
          <section className="rounded-2xl border border-border bg-surface p-4">
            <h3 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide mb-3">By Category (all time)</h3>
            <div className="space-y-2">
              {sorted.map(([cat, count]) => (
                <div key={cat} className="flex items-center gap-3">
                  <span className="text-xs text-fg-secondary w-28 truncate capitalize">{cat.replace(/_/g, " ")}</span>
                  <div className="flex-1 h-2 bg-surface-sunken rounded-full overflow-hidden">
                    <div
                      className="h-full bg-accent/60 rounded-full"
                      style={{ width: `${(count / max) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-fg-muted font-mono w-8 text-right">{count}</span>
                </div>
              ))}
            </div>
          </section>
        );
      })()}

      <section className="rounded-2xl border border-border bg-surface overflow-hidden">
        <div className="px-5 py-3.5 border-b border-border-subtle">
          <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wide">Work Orders <span className="text-fg-faint font-normal">· {list?.count ?? 0}</span></h2>
        </div>
        {list && list.requests.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-border">{["Title", "Unit", "Category", "Priority", "Status", "Cost", "Created"].map((h) => <th key={h} className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">{h}</th>)}</tr></thead>
              <tbody>
                {list.requests.map((mr) => (
                  <tr key={mr.id} className="border-b border-border-subtle hover:bg-surface-raised transition-colors">
                    <td className="px-4 py-2.5 text-sm text-fg">{mr.title}</td>
                    <td className="px-4 py-2.5"><Link href={`/properties/${propertyId}/units/${mr.unit_id}`} className="font-mono text-sm text-fg-secondary hover:text-accent transition-colors">{mr.unit_id.slice(-6)}</Link></td>
                    <td className="px-4 py-2.5 text-sm text-fg-muted">{mr.category}</td>
                    <td className="px-4 py-2.5"><Badge variant={mr.priority === "emergency" ? "red" : mr.priority === "high" ? "amber" : "default"}>{mr.priority}</Badge></td>
                    <td className="px-4 py-2.5"><Badge variant={mr.status === "open" ? "amber" : mr.status === "completed" ? "emerald" : "default"}>{mr.status}</Badge></td>
                    <td className="px-4 py-2.5 font-mono text-sm text-fg-muted">{mr.cost != null ? fmt$(mr.cost) : "—"}</td>
                    <td className="px-4 py-2.5 text-sm text-fg-muted">{fmtDate(mr.created)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="py-12 text-center text-sm text-fg-faint">No maintenance requests</div>}
      </section>
    </div>
  );
}
