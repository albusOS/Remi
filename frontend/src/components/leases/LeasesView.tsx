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
import { EntityFormPanel, type FieldDef } from "@/components/ui/EntityFormPanel";
import { ManagerFilter } from "@/components/ui/ManagerFilter";
import { useApiQuery } from "@/hooks/useApiQuery";
import type { LeaseCalendar } from "@/lib/types";

const LEASE_FIELDS: FieldDef[] = [
  { name: "property_id", label: "Property ID", required: true, placeholder: "property:..." },
  { name: "unit_id", label: "Unit ID", required: true, placeholder: "unit:..." },
  { name: "tenant_id", label: "Tenant ID", required: true, placeholder: "tenant:..." },
  { name: "start_date", label: "Start Date", type: "date", required: true },
  { name: "end_date", label: "End Date", type: "date", required: true },
  { name: "monthly_rent", label: "Monthly Rent", type: "number", required: true },
  { name: "deposit", label: "Deposit", type: "number" },
  { name: "status", label: "Status", type: "select", defaultValue: "active", options: [
    { value: "active", label: "Active" }, { value: "pending", label: "Pending" },
  ]},
];

const WINDOWS = [30, 60, 90] as const;

export function LeasesView() {
  const [days, setDays] = useState<number>(90);
  const [managerId, setManagerId] = useState("");
  const [showAddLease, setShowAddLease] = useState(false);

  const effectiveScope = managerId ? { manager_id: managerId } : undefined;

  const { data, loading, error, refetch } = useApiQuery<LeaseCalendar>(
    () => api.leasesExpiring(days, effectiveScope),
    [days, managerId],
  );

  return (
    <PageContainer>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-fg">Expiring Leases</h1>
            <p className="text-sm text-fg-muted mt-1">
              Leases expiring within {days} days and month-to-month
            </p>
          </div>
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            <div className="flex rounded-lg border border-border overflow-hidden">
              {WINDOWS.map((w) => (
                <button
                  key={w}
                  onClick={() => setDays(w)}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    days === w
                      ? "bg-accent text-accent-fg"
                      : "text-fg-muted hover:text-fg-secondary hover:bg-surface-sunken"
                  }`}
                >
                  {w}d
                </button>
              ))}
            </div>
            <ManagerFilter value={managerId} onChange={setManagerId} />
            <button
              onClick={() => setShowAddLease(true)}
              className="h-9 flex items-center gap-2 px-4 rounded-xl border border-dashed border-border bg-surface hover:border-accent/40 hover:text-accent hover:shadow-md hover:shadow-accent/5 text-xs font-medium text-fg-muted transition-all btn-glow"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
              Add Lease
            </button>
          </div>
        </div>

        {data && (
          <MetricStrip className="lg:grid-cols-3">
            <MetricCard
              label="Expiring Leases"
              value={data.total_expiring}
              alert={data.total_expiring > 10}
            />
            <MetricCard
              label="Month-to-Month"
              value={data.month_to_month_count}
              alert={data.month_to_month_count > 0}
            />
            <MetricCard
              label="Total Monthly Rent"
              value={fmt$(data.leases.reduce((s, l) => s + l.monthly_rent, 0))}
              sub="at risk of turnover"
            />
          </MetricStrip>
        )}

        {loading && (
          <div className="py-12 text-center text-sm text-fg-faint animate-pulse">Loading...</div>
        )}

        <ErrorBanner error={error} onRetry={refetch} />

        {!loading && data && data.leases.length > 0 && (
          <div className="rounded-xl border border-border bg-surface overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Tenant</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Property</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Unit</th>
                    <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Rent</th>
                    <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Market</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Expires</th>
                    <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Days Left</th>
                    <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {data.leases.map((l) => {
                    const belowMarket = l.market_rent > 0 && l.monthly_rent < l.market_rent;
                    const gap = belowMarket ? l.market_rent - l.monthly_rent : 0;
                    const urgencyClass =
                      l.is_month_to_month ? "" :
                      l.days_left <= 30 ? "bg-error-soft/30" :
                      l.days_left <= 60 ? "bg-warn-soft/30" : "";
                    const daysClass =
                      l.is_month_to_month ? "text-fg-muted" :
                      l.days_left <= 30 ? "text-error font-semibold" :
                      l.days_left <= 60 ? "text-warn font-semibold" : "text-fg-secondary";
                    return (
                      <tr key={l.lease_id} className={`border-b border-border-subtle hover:bg-surface-raised transition-colors ${urgencyClass}`}>
                        <td className="px-4 py-2.5 text-fg font-medium">{l.tenant_name}</td>
                        <td className="px-4 py-2.5 text-xs">
                          <Link href={`/properties/${l.property_id}`} className="text-fg-secondary hover:text-accent transition-colors">
                            {l.property_name}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 font-mono text-xs">
                          <Link href={`/properties/${l.property_id}/units/${l.unit_id}`} className="text-fg-secondary hover:text-accent transition-colors">
                            {l.unit_number}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-fg-secondary">{fmt$(l.monthly_rent)}</td>
                        <td className="px-4 py-2.5 text-right font-mono">
                          <span className="text-fg-muted">{fmt$(l.market_rent)}</span>
                          {belowMarket && (
                            <span className="ml-1.5 text-[10px] text-warn">+{fmt$(gap)}</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-fg-secondary text-xs">{l.end_date}</td>
                        <td className={`px-4 py-2.5 text-right font-mono ${daysClass}`}>
                          {l.days_left}
                        </td>
                        <td className="px-4 py-2.5">
                          {l.is_month_to_month ? (
                            <Badge variant="amber">MTM</Badge>
                          ) : l.days_left <= 30 ? (
                            <Badge variant="red">Urgent</Badge>
                          ) : l.days_left <= 60 ? (
                            <Badge variant="amber">Soon</Badge>
                          ) : (
                            <Badge variant="default">Fixed</Badge>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {!loading && data && data.leases.length === 0 && (
          <div className="py-12 text-center text-sm text-fg-faint">
            No expiring leases in the next {days} days
          </div>
        )}

        <EntityFormPanel
          open={showAddLease}
          onClose={() => setShowAddLease(false)}
          title="Add Lease"
          fields={LEASE_FIELDS}
          submitLabel="Create Lease"
          onSubmit={async (values) => {
            await api.createLease(values as Parameters<typeof api.createLease>[0]);
            refetch();
          }}
        />
    </PageContainer>
  );
}
