"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmt$, fmtDate } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageContainer } from "@/components/ui/PageContainer";
import { TimelineBuckets, type TimeBucket } from "@/components/ui/TimelineBuckets";
import { StatHero } from "@/components/ui/StatHero";
import { Badge } from "@/components/ui/Badge";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ManagerFilter } from "@/components/ui/ManagerFilter";
import type { LeaseCalendar } from "@/lib/types";

const WINDOWS = [30, 60, 90, 180] as const;
type Window = (typeof WINDOWS)[number];

function urgencyBadge(daysLeft: number, isMtm: boolean) {
  if (isMtm) return <Badge variant="default">MTM</Badge>;
  if (daysLeft <= 0) return <Badge variant="red">Expired</Badge>;
  if (daysLeft <= 30) return <Badge variant="red">{daysLeft}d</Badge>;
  if (daysLeft <= 60) return <Badge variant="amber">{daysLeft}d</Badge>;
  return <Badge variant="default">{daysLeft}d</Badge>;
}

export function LeasePipelineView() {
  const [managerId, setManagerId] = useState("");
  const [window, setWindow] = useState<Window>(90);

  const effectiveScope = managerId ? { manager_id: managerId } : undefined;
  const { data, loading, error, refetch } = useApiQuery<LeaseCalendar>(
    () => api.leasesExpiring(window, effectiveScope),
    [managerId, window],
  );

  const buckets: TimeBucket[] = (() => {
    if (!data) return [];
    const result: TimeBucket[] = [];
    const steps = [30, 60, 90, 180];
    let prev = 0;
    for (const step of steps.filter((s) => s <= window)) {
      const matching = data.leases.filter(
        (l) => !l.is_month_to_month && l.days_left > prev && l.days_left <= step,
      );
      result.push({
        label: `${step}d`,
        count: matching.length,
        amount: matching.reduce((s, l) => s + l.monthly_rent, 0),
        colorClass: step <= 30 ? "bg-error" : step <= 60 ? "bg-warn" : "bg-accent/40",
      });
      prev = step;
    }
    if (data.month_to_month_count > 0) {
      result.push({ label: "MTM", count: data.month_to_month_count, colorClass: "bg-fg-ghost" });
    }
    return result;
  })();

  const sorted = [...(data?.leases ?? [])].sort((a, b) => {
    if (a.is_month_to_month && !b.is_month_to_month) return 1;
    if (!a.is_month_to_month && b.is_month_to_month) return -1;
    return a.days_left - b.days_left;
  });

  const mtmRevenue = data?.leases
    .filter((l) => l.is_month_to_month)
    .reduce((s, l) => s + l.monthly_rent, 0) ?? 0;

  return (
    <PageContainer>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-fg">Leases</h1>
          <p className="text-sm text-fg-muted mt-1">Expiration timeline and renewal pipeline</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-border overflow-hidden text-[11px]">
            {WINDOWS.map((w) => (
              <button
                key={w}
                onClick={() => setWindow(w)}
                className={`px-3 py-1.5 transition-colors ${window === w ? "bg-accent text-accent-fg" : "text-fg-muted hover:bg-surface-raised"}`}
              >
                {w}d
              </button>
            ))}
          </div>
          <ManagerFilter value={managerId} onChange={setManagerId} />
        </div>
      </div>

      {data && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatHero
            label={`Expiring (${window}d)`}
            value={String(data.total_expiring)}
            supporting={[
              { label: "Monthly Revenue at Risk", value: fmt$(data.leases.reduce((s, l) => s + l.monthly_rent, 0)) },
              { label: "Month-to-Month", value: String(data.month_to_month_count), alert: data.month_to_month_count > 0 },
              { label: "MTM Revenue", value: fmt$(mtmRevenue) },
            ]}
          />
          {buckets.length > 0 && (
            <TimelineBuckets buckets={buckets} />
          )}
        </div>
      )}

      <ErrorBanner error={error} onRetry={refetch} />

      {loading && (
        <div className="rounded-2xl border border-border bg-surface overflow-hidden">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 border-b border-border-subtle number-shimmer" />
          ))}
        </div>
      )}

      {!loading && sorted.length > 0 && (
        <div className="rounded-xl border border-border bg-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["Tenant", "Property / Unit", "Status", "Expires", "Rent"].map((h) => (
                    <th key={h} className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((l, i) => (
                  <tr key={i} className="border-b border-border-subtle hover:bg-surface-raised transition-colors">
                    <td className="px-4 py-2.5 font-medium text-fg">{l.tenant_name}</td>
                    <td className="px-4 py-2.5 text-xs">
                      <div className="flex flex-col gap-0.5">
                        <Link href={`/properties/${l.property_id}`} className="text-fg-secondary hover:text-accent transition-colors">{l.property_name}</Link>
                        <span className="text-fg-faint font-mono">{l.unit_number}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      {urgencyBadge(l.days_left, l.is_month_to_month)}
                    </td>
                    <td className={`px-4 py-2.5 font-mono text-xs ${l.days_left <= 0 ? "text-error-fg font-semibold" : l.days_left <= 30 ? "text-warn-fg" : "text-fg-muted"}`}>
                      {l.is_month_to_month ? "Rolling" : l.end_date ? fmtDate(l.end_date) : "—"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-fg-secondary">{fmt$(l.monthly_rent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
