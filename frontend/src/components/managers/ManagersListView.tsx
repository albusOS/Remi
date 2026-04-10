"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { fmt$, pct } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageContainer } from "@/components/ui/PageContainer";
import { ManagerHealthCard } from "@/components/ui/ManagerHealthCard";
import { EntityFormPanel } from "@/components/ui/EntityFormPanel";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { HealthRing } from "@/components/ui/HealthRing";
import type { ManagerListItem } from "@/lib/types";

type SortKey = "name" | "occupancy" | "revenue" | "units" | "issues";

function sortManagers(managers: ManagerListItem[], key: SortKey): ManagerListItem[] {
  return [...managers].sort((a, b) => {
    switch (key) {
      case "name": return a.name.localeCompare(b.name);
      case "occupancy": return a.metrics.occupancy_rate - b.metrics.occupancy_rate;
      case "revenue": return b.metrics.total_actual_rent - a.metrics.total_actual_rent;
      case "units": return b.metrics.total_units - a.metrics.total_units;
      case "issues": return (b.delinquent_count + b.metrics.vacant + b.expired_leases) - (a.delinquent_count + a.metrics.vacant + a.expired_leases);
      default: return 0;
    }
  });
}

function PortfolioRing({ managers }: { managers: ManagerListItem[] }) {
  const totalUnits = managers.reduce((s, m) => s + m.metrics.total_units, 0);
  const occupied = managers.reduce((s, m) => s + m.metrics.occupied, 0);
  const totalRevenue = managers.reduce((s, m) => s + m.metrics.total_actual_rent, 0);
  const totalDelinquent = managers.reduce((s, m) => s + m.delinquent_count, 0);
  const totalLTL = managers.reduce((s, m) => s + m.metrics.loss_to_lease, 0);
  // Use weighted average of per-manager rates (already computed server-side) rather than recalculating
  const rate = managers.length > 0
    ? managers.reduce((s, m) => s + m.metrics.occupancy_rate * m.metrics.total_units, 0) / Math.max(totalUnits, 1)
    : 0;

  return (
    <div className="flex items-center gap-8 px-1">
      <HealthRing rate={rate} size={96} label="occupied" />
      <div className="space-y-2">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-fg font-mono">{fmt$(totalRevenue)}</span>
          <span className="text-xs text-fg-faint">/mo across {managers.length} managers</span>
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-[11px]">
          <span className="text-fg-muted"><span className="text-fg font-semibold">{occupied}/{totalUnits}</span> units occupied</span>
          <span className="text-fg-muted"><span className="text-fg font-semibold">{managers.reduce((s, m) => s + m.property_count, 0)}</span> properties</span>
          {totalDelinquent > 0 && <span className="text-error font-semibold">{totalDelinquent} delinquent</span>}
          {totalLTL > 0 && <span className="text-warn font-mono">{fmt$(totalLTL)} LTL</span>}
        </div>
      </div>
    </div>
  );
}

export function ManagersListView() {
  const [sort, setSort] = useState<SortKey>("issues");
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  const { data, loading, error, refetch } = useApiQuery<ManagerListItem[]>(
    () => api.listManagers(),
    ["managers_list"],
  );

  const managers = Array.isArray(data) ? data : [];
  const active = managers.filter((m) => m.metrics.total_units > 0);
  const filtered = sortManagers(
    search ? active.filter((m) => m.name.toLowerCase().includes(search.toLowerCase())) : active,
    sort,
  );

  const urgent = filtered.filter((m) => m.emergency_maintenance > 0 || m.delinquent_count > 0 || m.expired_leases > 0);
  const healthy = filtered.filter((m) => m.emergency_maintenance === 0 && m.delinquent_count === 0 && m.expired_leases === 0);

  const SORT_OPTIONS: { key: SortKey; label: string }[] = [
    { key: "issues", label: "Issues" },
    { key: "occupancy", label: "Occupancy" },
    { key: "revenue", label: "Revenue" },
    { key: "units", label: "Units" },
    { key: "name", label: "Name" },
  ];

  return (
    <PageContainer wide>
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-lg font-semibold text-fg">Managers</h1>
        <button
          onClick={() => setShowAdd(true)}
          className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent text-accent-fg text-xs font-medium hover:bg-accent-hover transition-colors"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Add
        </button>
      </div>

      <ErrorBanner error={error} onRetry={refetch} />

      {/* Portfolio ring summary */}
      {!loading && active.length > 0 && <PortfolioRing managers={active} />}

      {/* Controls */}
      {!loading && active.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search managers..."
            className="min-w-[160px] max-w-xs bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-fg placeholder:text-fg-faint focus:outline-none focus:border-accent"
          />
          <div className="flex rounded-lg border border-border overflow-hidden text-[10px]">
            {SORT_OPTIONS.map((o) => (
              <button
                key={o.key}
                onClick={() => setSort(o.key)}
                className={`px-2.5 py-1.5 transition-colors ${sort === o.key ? "bg-accent text-accent-fg" : "text-fg-muted hover:bg-surface-raised"}`}
              >
                {o.label}
              </button>
            ))}
          </div>
          {search && <span className="text-[10px] text-fg-faint">{filtered.length} result{filtered.length !== 1 ? "s" : ""}</span>}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-border bg-surface h-44 number-shimmer" />
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && active.length === 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-dashed border-border bg-surface/50 h-44 flex items-center justify-center">
              <span className="text-xs text-fg-ghost">Manager {i + 1}</span>
            </div>
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && search && (
        <p className="py-12 text-center text-sm text-fg-faint">No managers matching &ldquo;{search}&rdquo;</p>
      )}

      {/* Needs attention — visually elevated */}
      {!loading && urgent.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-error animate-pulse inline-block" />
            Needs Attention ({urgent.length})
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {urgent.map((m) => <ManagerHealthCard key={m.id} manager={m} />)}
          </div>
        </div>
      )}

      {/* Healthy */}
      {!loading && healthy.length > 0 && (
        <div className="space-y-2">
          {urgent.length > 0 && (
            <p className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest">
              Healthy ({healthy.length})
            </p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {healthy.map((m) => <ManagerHealthCard key={m.id} manager={m} />)}
          </div>
        </div>
      )}

      <EntityFormPanel
        open={showAdd}
        onClose={() => setShowAdd(false)}
        title="Add Manager"
        fields={[
          { name: "name", label: "Name", required: true, placeholder: "Jane Smith" },
          { name: "email", label: "Email", placeholder: "jane@example.com" },
          { name: "company", label: "Company", placeholder: "Acme Property Mgmt" },
        ]}
        submitLabel="Create Manager"
        onSubmit={async (values) => {
          await api.createManager(values as Parameters<typeof api.createManager>[0]);
          refetch();
        }}
      />
    </PageContainer>
  );
}
