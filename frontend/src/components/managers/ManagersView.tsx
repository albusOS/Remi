"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { fmt$, pct } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageContainer } from "@/components/ui/PageContainer";
import { Badge } from "@/components/ui/Badge";
import type { ManagerListItem } from "@/lib/types";

function issueCount(m: ManagerListItem): number {
  return (
    m.metrics.vacant +
    m.metrics.open_maintenance +
    m.metrics.expiring_leases_90d +
    m.expired_leases +
    m.below_market_units +
    m.delinquent_count
  );
}

function hasUrgent(m: ManagerListItem): boolean {
  return m.emergency_maintenance > 0 || m.expired_leases > 0 || m.delinquent_count > 5;
}

function revenuePerUnit(m: ManagerListItem): number {
  return m.metrics.total_units > 0 ? m.metrics.total_actual_rent / m.metrics.total_units : 0;
}

type SortKey = "issues" | "revenue" | "occupancy" | "units" | "name" | "rev_per_unit" | "delinquency" | "ltl";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "issues", label: "Most Issues" },
  { value: "delinquency", label: "Delinquency" },
  { value: "occupancy", label: "Lowest Occupancy" },
  { value: "revenue", label: "Revenue" },
  { value: "rev_per_unit", label: "Rev / Unit" },
  { value: "ltl", label: "Loss to Lease" },
  { value: "units", label: "Portfolio Size" },
  { value: "name", label: "Name" },
];

function sortManagers(mgrs: ManagerListItem[], key: SortKey): ManagerListItem[] {
  const copy = [...mgrs];
  switch (key) {
    case "issues":
      return copy.sort((a, b) => issueCount(b) - issueCount(a) || b.metrics.total_units - a.metrics.total_units);
    case "delinquency":
      return copy.sort((a, b) => b.total_delinquent_balance - a.total_delinquent_balance);
    case "revenue":
      return copy.sort((a, b) => b.metrics.total_actual_rent - a.metrics.total_actual_rent);
    case "rev_per_unit":
      return copy.sort((a, b) => revenuePerUnit(b) - revenuePerUnit(a));
    case "occupancy":
      return copy.sort((a, b) => a.metrics.occupancy_rate - b.metrics.occupancy_rate);
    case "units":
      return copy.sort((a, b) => b.metrics.total_units - a.metrics.total_units);
    case "ltl":
      return copy.sort((a, b) => b.metrics.loss_to_lease - a.metrics.loss_to_lease);
    case "name":
      return copy.sort((a, b) => a.name.localeCompare(b.name));
  }
}

function OccupancyBar({ rate }: { rate: number }) {
  const color = rate >= 0.95 ? "bg-ok" : rate >= 0.9 ? "bg-warn" : "bg-error";
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 rounded-full bg-border-subtle overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${Math.min(rate * 100, 100)}%` }} />
      </div>
      <span className={`text-[11px] font-mono font-semibold w-11 text-right ${rate < 0.9 ? "text-warn" : "text-fg"}`}>
        {pct(rate)}
      </span>
    </div>
  );
}

function IssueChips({ m }: { m: ManagerListItem }) {
  const chips: { label: string; variant: "red" | "amber" | "cyan" }[] = [];
  if (m.delinquent_count > 0) chips.push({ label: `${m.delinquent_count} delinq`, variant: "red" });
  if (m.metrics.vacant > 0) chips.push({ label: `${m.metrics.vacant} vacant`, variant: "red" });
  if (m.expired_leases > 0) chips.push({ label: `${m.expired_leases} expired`, variant: "red" });
  if (m.metrics.expiring_leases_90d > 0) chips.push({ label: `${m.metrics.expiring_leases_90d} expiring`, variant: "amber" });
  if (m.below_market_units > 0) chips.push({ label: `${m.below_market_units} ↓mkt`, variant: "amber" });
  if (m.metrics.open_maintenance > 0) chips.push({ label: `${m.metrics.open_maintenance} maint`, variant: "cyan" });

  if (chips.length === 0) return <Badge variant="emerald">OK</Badge>;

  return (
    <div className="flex flex-wrap gap-1">
      {chips.slice(0, 4).map((c) => (
        <Badge key={c.label} variant={c.variant}>{c.label}</Badge>
      ))}
      {chips.length > 4 && (
        <span className="text-[9px] text-fg-faint">+{chips.length - 4}</span>
      )}
    </div>
  );
}

function AggregateStrip({ managers, loading }: { managers: ManagerListItem[]; loading?: boolean }) {
  const totalUnits = managers.reduce((s, m) => s + m.metrics.total_units, 0);
  const totalOccupied = managers.reduce((s, m) => s + m.metrics.occupied, 0);
  const totalRevenue = managers.reduce((s, m) => s + m.metrics.total_actual_rent, 0);
  const totalLTL = managers.reduce((s, m) => s + m.metrics.loss_to_lease, 0);
  const totalDelinq = managers.reduce((s, m) => s + m.total_delinquent_balance, 0);
  const totalVacant = managers.reduce((s, m) => s + m.metrics.vacant, 0);
  const totalIssues = managers.reduce((s, m) => s + issueCount(m), 0);
  const avgOcc = totalUnits > 0 ? totalOccupied / totalUnits : 0;

  const stats: { label: string; value: string; alert?: boolean }[] = [
    { label: "Managers", value: managers.length > 0 ? String(managers.length) : "—" },
    { label: "Units", value: totalUnits > 0 ? totalUnits.toLocaleString() : "—" },
    { label: "Occupancy", value: totalUnits > 0 ? pct(avgOcc) : "—", alert: totalUnits > 0 && avgOcc < 0.9 },
    { label: "Revenue", value: totalRevenue > 0 ? fmt$(totalRevenue) : "—" },
    { label: "LTL", value: totalLTL > 0 ? fmt$(totalLTL) : "—", alert: totalLTL > 0 },
    { label: "Delinquent", value: totalDelinq > 0 ? fmt$(totalDelinq) : "—", alert: totalDelinq > 0 },
    { label: "Vacant", value: totalUnits > 0 ? String(totalVacant) : "—", alert: totalVacant > 0 },
    { label: "Issues", value: totalUnits > 0 ? String(totalIssues) : "—", alert: totalIssues > 0 },
  ];

  return (
    <div className="rounded-xl border border-border bg-surface-raised px-4 py-3">
      <div className="flex flex-wrap gap-x-6 gap-y-3">
        {stats.map((s) => (
          <div key={s.label} className="text-center min-w-[56px]">
            <p className="text-[9px] text-fg-faint uppercase tracking-wider mb-0.5">{s.label}</p>
            <p className={`text-sm font-bold font-mono tracking-tight transition-colors ${
              loading ? "text-fg-ghost number-shimmer" : s.alert ? "text-warn-fg" : "text-fg"
            }`}>
              {s.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ManagerRow({ m, rank }: { m: ManagerListItem; rank: number }) {
  const router = useRouter();
  const urgent = hasUrgent(m);
  const issues = issueCount(m);

  return (
    <tr
      onClick={() => router.push(`/managers/${m.id}`)}
      className={`group cursor-pointer border-b border-border-subtle transition-colors ${
        urgent
          ? "hover:bg-error-soft/50"
          : issues > 0
          ? "hover:bg-warn-soft/30"
          : "hover:bg-surface-raised"
      }`}
    >
      <td className="pl-4 pr-2 py-3 w-8">
        <span className={`text-[10px] font-mono ${urgent ? "text-error font-bold" : "text-fg-ghost"}`}>
          {rank}
        </span>
      </td>
      <td className="px-2 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {urgent && <span className="w-1.5 h-1.5 rounded-full bg-error animate-pulse shrink-0" />}
            <Link
              href={`/managers/${m.id}`}
              onClick={(e) => e.stopPropagation()}
              className="text-sm font-medium text-fg group-hover:text-accent transition-colors truncate"
            >
              {m.name}
            </Link>
          </div>
          <p className="text-[10px] text-fg-faint mt-0.5">
            {m.property_count} properties · {m.metrics.total_units} units
            {m.company ? ` · ${m.company}` : ""}
          </p>
        </div>
      </td>
      <td className="px-2 py-3 hidden lg:table-cell">
        <OccupancyBar rate={m.metrics.occupancy_rate} />
      </td>
      <td className="px-2 py-3 text-right hidden md:table-cell">
        <p className="text-xs font-mono font-semibold text-fg">{fmt$(m.metrics.total_actual_rent)}</p>
        <p className="text-[10px] font-mono text-fg-faint">{fmt$(revenuePerUnit(m))}/u</p>
      </td>
      <td className="px-2 py-3 text-right hidden lg:table-cell">
        <span className={`text-xs font-mono ${m.metrics.loss_to_lease > 0 ? "text-warn font-semibold" : "text-fg-ghost"}`}>
          {m.metrics.loss_to_lease > 0 ? fmt$(m.metrics.loss_to_lease) : "—"}
        </span>
      </td>
      <td className="px-2 py-3 text-right hidden lg:table-cell">
        {m.total_delinquent_balance > 0 ? (
          <div>
            <p className="text-xs font-mono font-semibold text-error">{fmt$(m.total_delinquent_balance)}</p>
            <p className="text-[10px] text-fg-faint">{m.delinquent_count} tenants</p>
          </div>
        ) : (
          <span className="text-xs text-fg-ghost">—</span>
        )}
      </td>
      <td className="px-2 py-3 hidden sm:table-cell">
        <IssueChips m={m} />
      </td>
      <td className="pr-4 pl-2 py-3">
        <Link
          href={`/?q=${encodeURIComponent(`How is ${m.name} doing?`)}`}
          onClick={(e) => e.stopPropagation()}
          className="flex items-center justify-center w-7 h-7 rounded-lg text-fg-ghost hover:text-accent hover:bg-accent-soft transition-all opacity-0 group-hover:opacity-100"
          title={`Ask REMI about ${m.name}`}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
        </Link>
      </td>
    </tr>
  );
}

export function ManagersView() {
  const [sortBy, setSortBy] = useState<SortKey>("issues");
  const [search, setSearch] = useState("");

  const { data: managers, loading, refetch } = useApiQuery(
    () => api.listManagers().catch(() => [] as ManagerListItem[]),
    [],
  );

  const activeMgrs = (managers ?? ([] as ManagerListItem[])).filter((m) => m.metrics.total_units > 0 || m.property_count > 0);
  const filtered = search
    ? activeMgrs.filter((m) => m.name.toLowerCase().includes(search.toLowerCase()) || m.company?.toLowerCase().includes(search.toLowerCase()))
    : activeMgrs;
  const sorted = sortManagers(filtered, sortBy);

  return (
    <PageContainer wide>
      <div className="space-y-1">
        <h1 className="text-lg font-bold text-fg tracking-tight">Property Managers</h1>
        <p className="text-[11px] text-fg-faint">
          Oversee performance, compare metrics, and drill down into any manager&apos;s portfolio.
        </p>
      </div>

      {/* AggregateStrip — always rendered; zeros when loading or empty */}
      <AggregateStrip managers={loading ? [] : activeMgrs} loading={loading} />

      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-xs">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-fg-ghost pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter managers..."
            className="w-full bg-surface border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-fg placeholder-fg-ghost focus:outline-none focus:border-fg-ghost transition-colors"
          />
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortKey)}
          className="bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-fg-secondary focus:outline-none focus:border-fg-ghost cursor-pointer"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Table — skeleton rows on load, real rows after */}
      <div className="rounded-xl border border-border bg-surface overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border text-[9px] font-semibold text-fg-muted uppercase tracking-wider">
              <th className="pl-4 pr-2 py-2.5 text-left w-8">#</th>
              <th className="px-2 py-2.5 text-left">Manager</th>
              <th className="px-2 py-2.5 text-left hidden lg:table-cell">Occupancy</th>
              <th className="px-2 py-2.5 text-right hidden md:table-cell">Revenue</th>
              <th className="px-2 py-2.5 text-right hidden lg:table-cell">LTL</th>
              <th className="px-2 py-2.5 text-right hidden lg:table-cell">Delinquent</th>
              <th className="px-2 py-2.5 text-left hidden sm:table-cell">Issues</th>
              <th className="pr-4 pl-2 py-2.5 w-10"></th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? [...Array(5)].map((_, i) => (
                  <tr key={i} className="border-b border-border-subtle">
                    <td className="pl-4 pr-2 py-3"><span className="block w-4 h-2.5 rounded bg-border number-shimmer" /></td>
                    <td className="px-2 py-3">
                      <div className="h-3 w-32 rounded bg-border number-shimmer mb-1" />
                      <div className="h-2 w-20 rounded bg-border-subtle number-shimmer" />
                    </td>
                    <td className="px-2 py-3 hidden lg:table-cell"><div className="h-2 w-24 rounded bg-border number-shimmer" /></td>
                    <td className="px-2 py-3 hidden md:table-cell"><div className="h-2.5 w-16 rounded bg-border number-shimmer ml-auto" /></td>
                    <td className="px-2 py-3 hidden lg:table-cell"><div className="h-2 w-12 rounded bg-border number-shimmer ml-auto" /></td>
                    <td className="px-2 py-3 hidden lg:table-cell"><div className="h-2 w-12 rounded bg-border number-shimmer ml-auto" /></td>
                    <td className="px-2 py-3 hidden sm:table-cell"><div className="h-5 w-16 rounded bg-border number-shimmer" /></td>
                    <td className="pr-4 pl-2 py-3" />
                  </tr>
                ))
              : sorted.map((m, i) => (
                  <ManagerRow key={m.id} m={m} rank={i + 1} />
                ))
            }
          </tbody>
        </table>
        {!loading && sorted.length === 0 && activeMgrs.length > 0 && (
          <div className="py-10 text-center text-sm text-fg-faint">
            No managers match &quot;{search}&quot;
          </div>
        )}
        {!loading && activeMgrs.length === 0 && (
          <div className="py-16 text-center">
            <p className="text-sm text-fg-faint mb-2">No managers yet</p>
            <Link href="/documents" className="text-xs text-accent hover:text-accent-hover transition-colors">
              Upload reports to get started →
            </Link>
          </div>
        )}
      </div>
    </PageContainer>
  );
}
