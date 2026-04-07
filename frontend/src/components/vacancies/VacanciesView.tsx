"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmt$ } from "@/lib/format";
import { MetricCard } from "@/components/ui/MetricCard";
import { MetricStrip } from "@/components/ui/MetricStrip";
import { PageContainer } from "@/components/ui/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ManagerFilter } from "@/components/ui/ManagerFilter";
import { useApiQuery } from "@/hooks/useApiQuery";
import type { VacancyTracker } from "@/lib/types";

export function VacanciesView() {
  const [managerId, setManagerId] = useState("");

  const effectiveScope = managerId ? { manager_id: managerId } : undefined;

  const { data, loading, error, refetch } = useApiQuery<VacancyTracker>(
    () => api.vacancyTracker(effectiveScope),
    [managerId],
  );

  return (
    <PageContainer>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-fg">Vacancies</h1>
            <p className="text-sm text-fg-muted mt-1">
              Vacant and notice units across the portfolio
            </p>
          </div>
          <ManagerFilter value={managerId} onChange={setManagerId} />
        </div>

        {data && (
          <MetricStrip className="lg:grid-cols-4">
            <MetricCard
              label="Vacant Units"
              value={data.total_vacant}
              alert={data.total_vacant > 0}
            />
            <MetricCard
              label="Notice Units"
              value={data.total_notice}
              alert={data.total_notice > 0}
            />
            <MetricCard
              label="Revenue at Risk"
              value={fmt$(data.total_market_rent_at_risk)}
              sub="monthly market rent"
              alert={data.total_market_rent_at_risk > 0}
            />
            <MetricCard
              label="Avg Days Vacant"
              value={data.avg_days_vacant != null ? String(data.avg_days_vacant) : "—"}
            />
          </MetricStrip>
        )}

        <ErrorBanner error={error} onRetry={refetch} />

        {loading && (
          <div className="py-12 text-center text-sm text-fg-faint animate-pulse">Loading...</div>
        )}

        {!loading && data && data.units.length > 0 && (() => {
          const stuckCount = data.units.filter((u) => (u.days_vacant ?? 0) > 30).length;
          return (
            <>
              <div className="flex items-center gap-4 text-xs">
                {stuckCount > 0 && (
                  <span className="text-error">
                    <span className="font-semibold">{stuckCount}</span> vacant 30+ days
                  </span>
                )}
              </div>

              <div className="rounded-xl border border-border bg-surface overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Property</th>
                        <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Unit</th>
                        <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Status</th>
                        <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Days Vacant</th>
                        <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Market Rent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.units.map((u) => {
                        const isNotice = u.occupancy_status?.includes("notice");
                        const stuck = (u.days_vacant ?? 0) > 30;
                        return (
                          <tr key={u.unit_id} className={`border-b border-border-subtle hover:bg-surface-raised transition-colors ${stuck ? "bg-error-soft/30" : ""}`}>
                            <td className="px-4 py-2.5">
                              <Link href={`/properties/${u.property_id}`} className="text-fg hover:text-accent transition-colors">
                                {u.property_name}
                              </Link>
                            </td>
                            <td className="px-4 py-2.5">
                              <Link href={`/properties/${u.property_id}/units/${u.unit_id}`} className="text-fg-secondary font-mono text-xs hover:text-accent transition-colors">
                                {u.unit_number}
                              </Link>
                            </td>
                            <td className="px-4 py-2.5">
                              <Badge variant={stuck ? "red" : isNotice ? "amber" : "red"}>
                                {stuck ? "stuck" : u.occupancy_status?.replace(/_/g, " ") ?? "vacant"}
                              </Badge>
                            </td>
                            <td className={`px-4 py-2.5 text-right font-mono ${(u.days_vacant ?? 0) > 30 ? "text-error" : "text-fg-secondary"}`}>
                              {u.days_vacant ?? "—"}
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-fg-secondary">{fmt$(u.market_rent)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          );
        })()}

        {!loading && data && data.units.length === 0 && (
          <div className="py-12 text-center text-sm text-fg-faint">
            No vacant units found
          </div>
        )}
    </PageContainer>
  );
}
