"use client";

import { useState } from "react";
import Link from "next/link";
import { fmt$, pct } from "@/lib/format";
import { MetricCard } from "@/components/ui/MetricCard";
import { MetricStrip } from "@/components/ui/MetricStrip";
import { Badge } from "@/components/ui/Badge";
import { StatusDot } from "@/components/ui/StatusDot";
import type { ManagerReview, ManagerPropertySummary } from "@/lib/types";

function PropertyRow({ p }: { p: ManagerPropertySummary }) {
  const occ = p.total_units > 0 ? p.occupied / p.total_units : 0;
  return (
    <Link
      href={`/properties/${p.property_id}`}
      className="flex items-center gap-4 px-5 py-3 border-b border-border-subtle hover:bg-surface-raised transition-colors"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <StatusDot status={p.issue_count === 0 ? "done" : p.emergency_maintenance > 0 ? "error" : "calling"} size={6} />
          <span className="text-sm font-medium text-fg truncate">{p.property_name}</span>
        </div>
      </div>
      <div className="flex items-center gap-6 shrink-0 text-xs">
        <div className="text-right w-16">
          <p className="text-fg-muted">Units</p>
          <p className="text-fg font-medium">{p.occupied}/{p.total_units}</p>
        </div>
        <div className="text-right w-16">
          <p className="text-fg-muted">Occ.</p>
          <p className={`font-medium ${occ < 0.9 ? "text-warn" : "text-fg"}`}>{pct(occ)}</p>
        </div>
        <div className="text-right w-20">
          <p className="text-fg-muted">Revenue</p>
          <p className="text-fg font-mono font-medium">{fmt$(p.monthly_actual)}</p>
        </div>
        <div className="text-right w-20">
          <p className="text-fg-muted">LTL</p>
          <p className={`font-mono font-medium ${p.loss_to_lease > 0 ? "text-warn" : "text-fg-muted"}`}>{fmt$(p.loss_to_lease)}</p>
        </div>
        <div className="flex flex-wrap gap-1 w-40 justify-end">
          {p.vacant > 0 && <Badge variant="red">{p.vacant} vac</Badge>}
          {p.expiring_leases > 0 && <Badge variant="amber">{p.expiring_leases} exp</Badge>}
          {p.expired_leases > 0 && <Badge variant="red">{p.expired_leases} expired</Badge>}
          {p.below_market_units > 0 && <Badge variant="amber">{p.below_market_units} ↓mkt</Badge>}
          {p.open_maintenance > 0 && <Badge variant="cyan">{p.open_maintenance} maint</Badge>}
          {p.issue_count === 0 && <Badge variant="emerald">OK</Badge>}
        </div>
      </div>
    </Link>
  );
}

export function OverviewTab({ review }: { review: ManagerReview }) {
  const [propSearch, setPropSearch] = useState("");
  const { metrics } = review;
  const totalIssues = metrics.vacant + metrics.open_maintenance + metrics.expiring_leases_90d + review.expired_leases + review.below_market_units;

  const filteredProps = propSearch
    ? review.properties.filter((p) => p.property_name.toLowerCase().includes(propSearch.toLowerCase()))
    : review.properties;

  return (
    <div className="space-y-6">
      <MetricStrip>
        <MetricCard label="Units" value={metrics.total_units} sub={`${metrics.occupied} occupied`} />
        <MetricCard label="Occupancy" value={pct(metrics.occupancy_rate)} trend={metrics.occupancy_rate >= 0.9 ? "up" : "down"} />
        <MetricCard label="Revenue" value={fmt$(metrics.total_actual_rent)} />
        <MetricCard label="Market Rent" value={fmt$(metrics.total_market_rent)} />
        <MetricCard label="Loss to Lease" value={fmt$(metrics.loss_to_lease)} alert={metrics.loss_to_lease > 0} />
        <MetricCard label="Vacancy Loss" value={fmt$(metrics.vacancy_loss)} alert={metrics.vacancy_loss > 0} />
        <MetricCard label="Delinquent" value={review.delinquent_count} sub={review.total_delinquent_balance > 0 ? fmt$(review.total_delinquent_balance) + " owed" : undefined} alert={review.delinquent_count > 0} />
        <MetricCard label="Expiring (90d)" value={metrics.expiring_leases_90d} alert={metrics.expiring_leases_90d > 0} />
        <MetricCard label="Issues" value={totalIssues} alert={totalIssues > 0} />
      </MetricStrip>

      <section className="rounded-xl border border-border bg-surface overflow-hidden">
        <div className="px-5 py-3 border-b border-border-subtle flex items-center gap-3">
          <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wide shrink-0">
            Properties {propSearch ? `(${filteredProps.length} of ${review.properties.length})` : `(${review.properties.length})`}
          </h2>
          <div className="flex-1" />
          {review.properties.length > 3 && (
            <input
              type="text"
              value={propSearch}
              onChange={(e) => setPropSearch(e.target.value)}
              placeholder="Filter properties..."
              className="bg-surface border border-border rounded-lg px-3 py-1 text-xs text-fg-secondary placeholder-fg-ghost focus:outline-none focus:border-fg-ghost w-44"
            />
          )}
        </div>
        <div className="max-h-[600px] overflow-y-auto">
          {filteredProps.map((p) => (
            <PropertyRow key={p.property_id} p={p} />
          ))}
          {filteredProps.length === 0 && review.properties.length > 0 && (
            <p className="text-sm text-fg-faint text-center py-12">No properties match &quot;{propSearch}&quot;</p>
          )}
          {review.properties.length === 0 && (
            <p className="text-sm text-fg-faint text-center py-12">No properties</p>
          )}
        </div>
      </section>

      {review.top_issues.length > 0 && (
        <section className="rounded-xl border border-border bg-surface overflow-hidden">
          <div className="px-5 py-3 border-b border-border-subtle">
            <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wide">
              Unit Issues ({review.top_issues.length})
            </h2>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {review.top_issues.map((issue) => (
              <Link
                key={issue.unit_id}
                href={`/properties/${issue.property_id}/units/${issue.unit_id}`}
                className="flex items-center gap-4 px-5 py-2.5 border-b border-border-subtle hover:bg-surface-raised transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-fg-secondary font-mono">{issue.unit_number}</span>
                  <span className="text-[10px] text-fg-faint ml-2">{issue.property_name}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {issue.issues.map((iss) => (
                    <Badge key={iss} variant={iss === "vacant" || iss === "expired_lease" ? "red" : iss === "below_market" || iss === "expiring_soon" ? "amber" : "cyan"}>
                      {iss.replace(/_/g, " ")}
                    </Badge>
                  ))}
                </div>
                {issue.monthly_impact > 0 && (
                  <span className="text-xs text-warn font-mono">-{fmt$(issue.monthly_impact)}/mo</span>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
