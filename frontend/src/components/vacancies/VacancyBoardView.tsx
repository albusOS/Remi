"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmt$ } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageContainer } from "@/components/ui/PageContainer";
import { StatHero } from "@/components/ui/StatHero";
import { Badge } from "@/components/ui/Badge";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ManagerFilter } from "@/components/ui/ManagerFilter";
import type { VacancyTracker } from "@/lib/types";

export function VacancyBoardView() {
  const [managerId, setManagerId] = useState("");
  const effectiveScope = managerId ? { manager_id: managerId } : undefined;

  const { data, loading, error, refetch } = useApiQuery<VacancyTracker>(
    () => api.vacancyTracker(effectiveScope),
    [managerId],
  );

  const grouped = (() => {
    if (!data) return [];
    const map: Record<string, { propertyName: string; propertyId: string; units: VacancyTracker["units"] }> = {};
    for (const u of data.units) {
      if (!map[u.property_id]) {
        map[u.property_id] = { propertyName: u.property_name, propertyId: u.property_id, units: [] };
      }
      map[u.property_id].units.push(u);
    }
    return Object.values(map).sort((a, b) => b.units.length - a.units.length);
  })();

  return (
    <PageContainer>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-fg">Vacancies</h1>
          <p className="text-sm text-fg-muted mt-1">Vacant units grouped by property</p>
        </div>
        <ManagerFilter value={managerId} onChange={setManagerId} />
      </div>

      {data && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatHero
            label="Vacant Units"
            value={String(data.total_vacant)}
            color={data.total_vacant > 0 ? "var(--color-error-fg)" : "var(--color-fg)"}
            supporting={[
              { label: "Revenue at Risk", value: fmt$(data.total_market_rent_at_risk), alert: data.total_market_rent_at_risk > 0 },
              { label: "Avg Rent", value: data.total_vacant > 0 ? fmt$(Math.round(data.total_market_rent_at_risk / data.total_vacant)) : "—" },
            ]}
          />
          <div className="sm:col-span-2 rounded-2xl border border-border bg-surface p-5">
            <p className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest mb-3">
              By duration
            </p>
            <div className="space-y-2">
              {[
                { label: "0–7 days", min: 0, max: 7, color: "bg-ok/50" },
                { label: "8–30 days", min: 8, max: 30, color: "bg-warn" },
                { label: "31–60 days", min: 31, max: 60, color: "bg-warn" },
                { label: "60+ days", min: 61, max: Infinity, color: "bg-error" },
              ].map((bucket) => {
                const count = data.units.filter((u) => (u.days_vacant ?? 0) >= bucket.min && (u.days_vacant ?? 0) < bucket.max).length;
                const maxCount = data.total_vacant || 1;
                return (
                  <div key={bucket.label} className="flex items-center gap-3">
                    <span className="text-[10px] text-fg-muted w-20 shrink-0 text-right font-mono">{bucket.label}</span>
                    <div className="flex-1 bg-border-subtle rounded-full h-4 overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-700 ${bucket.color}`} style={{ width: `${Math.max((count / maxCount) * 100, count > 0 ? 8 : 0)}%` }} />
                    </div>
                    <span className="text-xs font-semibold font-mono text-fg w-6 text-right shrink-0">{count > 0 ? count : "—"}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {data && data.total_vacant === 0 && (
        <div className="py-12 text-center text-sm text-ok font-medium">No vacant units</div>
      )}

      <ErrorBanner error={error} onRetry={refetch} />

      {loading && (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-border bg-surface h-32 number-shimmer" />
          ))}
        </div>
      )}

      {!loading && grouped.length > 0 && (
        <div className="space-y-3">
          {grouped.map((g) => (
            <div key={g.propertyId} className="rounded-xl border border-error/15 bg-error-soft/20 overflow-hidden">
              <div className="px-4 py-3 border-b border-error/10 flex items-center justify-between">
                <Link href={`/properties/${g.propertyId}`} className="text-sm font-semibold text-fg hover:text-accent transition-colors">
                  {g.propertyName}
                </Link>
                <Badge variant="red">{g.units.length} vacant</Badge>
              </div>
              <div className="flex flex-wrap gap-2 p-3">
                {g.units.map((u) => (
                  <div key={u.unit_id} className="rounded-lg border border-error/20 bg-surface px-3 py-2 min-w-[100px]">
                    <p className="text-xs font-semibold text-fg">{u.unit_number}</p>
                    <p className="text-[10px] font-mono text-fg-muted">{fmt$(u.market_rent)}/mo</p>
                    {u.days_vacant != null && u.days_vacant > 0 && (
                      <p className={`text-[10px] font-mono ${u.days_vacant > 30 ? "text-error-fg" : "text-warn"}`}>
                        {u.days_vacant}d empty
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
