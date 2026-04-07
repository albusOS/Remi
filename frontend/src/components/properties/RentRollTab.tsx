"use client";

import { useState } from "react";
import Link from "next/link";
import { fmt$ } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { SlidePanel } from "@/components/ui/SlidePanel";
import { IssuePill, ISSUE_LABELS } from "./IssueLabels";
import { ViewToggle, type ViewMode } from "./ViewToggle";
import { UnitGridCard } from "./UnitGridCard";
import { UnitPeek } from "./UnitPeek";
import type { RentRollResponse, RentRollRow, UnitIssue } from "@/lib/types";

type IssueFilter = UnitIssue | "all";

function UnitTableRow({ row, propertyId, expanded, onToggle }: { row: RentRollRow; propertyId: string; expanded: boolean; onToggle: () => void }) {
  const hasIssues = row.issues.length > 0;
  return (
    <>
      <tr onClick={onToggle} className={`border-b border-border-subtle cursor-pointer transition-colors ${hasIssues ? "bg-surface-raised hover:bg-surface-raised" : "hover:bg-surface-raised"}`}>
        <td className="px-4 py-2.5">
          <Link href={`/properties/${propertyId}/units/${row.unit_id}`} onClick={(e) => e.stopPropagation()} className="font-mono text-fg text-sm hover:text-accent transition-colors">{row.unit_number}</Link>
        </td>
        <td className="px-4 py-2.5"><Badge variant={row.status === "occupied" ? "emerald" : row.status === "vacant" ? "red" : row.status === "maintenance" ? "amber" : "default"}>{row.status}</Badge></td>
        <td className="px-4 py-2.5 text-sm text-fg-secondary">{row.tenant?.name ?? <span className="text-fg-faint">—</span>}</td>
        <td className="px-4 py-2.5 font-mono text-sm text-fg-secondary">{fmt$(row.current_rent)}</td>
        <td className="px-4 py-2.5 font-mono text-sm text-fg-muted">{fmt$(row.market_rent)}</td>
        <td className="px-4 py-2.5 text-sm">{row.pct_below_market > 0 ? <span className="text-warn font-medium">-{row.pct_below_market}%</span> : <span className="text-fg-faint">—</span>}</td>
        <td className="px-4 py-2.5 text-sm">{row.lease ? <span className={(row.lease.days_to_expiry ?? 999) <= 0 ? "text-error" : (row.lease.days_to_expiry ?? 999) <= 90 ? "text-warn" : "text-fg-secondary"}>{row.lease.end_date}</span> : <span className="text-fg-faint">—</span>}</td>
        <td className="px-4 py-2.5 text-sm text-center">{row.open_maintenance > 0 ? <span className="text-sky-400 font-medium">{row.open_maintenance}</span> : <span className="text-fg-ghost">0</span>}</td>
        <td className="px-4 py-2.5"><div className="flex flex-wrap gap-1">{row.issues.map((issue) => <IssuePill key={issue} issue={issue} />)}</div></td>
      </tr>
      {expanded && (
        <tr className="border-b border-border-subtle">
          <td colSpan={9} className="px-6 py-4 bg-surface-raised anim-expand">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-fg-muted uppercase tracking-wide">Unit</h4>
                <div className="space-y-1 text-fg-secondary">
                  {row.bedrooms != null && <p>{row.bedrooms} bed / {row.bathrooms ?? "—"} bath</p>}
                  {row.sqft != null && <p>{row.sqft.toLocaleString()} sq ft</p>}
                  {row.floor != null && <p>Floor {row.floor}</p>}
                  <p>Rent gap: <span className={row.rent_gap < 0 ? "text-warn font-medium" : "text-ok"}>{fmt$(row.rent_gap)}/mo</span></p>
                </div>
              </div>
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-fg-muted uppercase tracking-wide">Lease &amp; Tenant</h4>
                {row.lease && row.tenant ? (
                  <div className="space-y-1 text-fg-secondary">
                    <p className="text-fg font-medium">{row.tenant.name}</p>
                    <p className="text-fg-muted">{row.tenant.email}</p>
                    <p>Lease {row.lease.start_date} → {row.lease.end_date} <Badge variant={row.lease.status === "active" ? "emerald" : "red"} className="ml-2">{row.lease.status}</Badge></p>
                    <p>Deposit: {fmt$(row.lease.deposit)}</p>
                    {row.lease.days_to_expiry != null && (
                      <p className={row.lease.days_to_expiry <= 30 ? "text-error font-medium" : ""}>{row.lease.days_to_expiry > 0 ? `${row.lease.days_to_expiry} days until expiry` : `Expired ${Math.abs(row.lease.days_to_expiry)} days ago`}</p>
                    )}
                  </div>
                ) : <p className="text-fg-faint">No active lease</p>}
              </div>
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-fg-muted uppercase tracking-wide">Open Maintenance ({row.maintenance_items.length})</h4>
                {row.maintenance_items.length > 0 ? (
                  <div className="space-y-2">
                    {row.maintenance_items.map((mr) => (
                      <div key={mr.id} className="rounded-lg bg-surface border border-border-subtle px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Badge variant={mr.priority === "emergency" ? "red" : mr.priority === "high" ? "amber" : "default"}>{mr.priority}</Badge>
                          <span className="text-fg-secondary text-sm">{mr.title}</span>
                        </div>
                        <p className="text-xs text-fg-muted mt-1">{mr.category} · {mr.status}{mr.cost != null && ` · est. ${fmt$(mr.cost)}`}</p>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-fg-faint">None</p>}
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-border-subtle">
              <Link href={`/properties/${propertyId}/units/${row.unit_id}`} className="text-xs text-accent hover:underline">View full unit detail →</Link>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function RentRollTab({ rentRoll, propertyId }: { rentRoll: RentRollResponse; propertyId: string }) {
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [issueFilter, setIssueFilter] = useState<IssueFilter>("all");
  const [peekRow, setPeekRow] = useState<RentRollRow | null>(null);
  const [expandedUnit, setExpandedUnit] = useState<string | null>(null);

  const filteredRows = issueFilter === "all"
    ? rentRoll.rows
    : rentRoll.rows.filter((r) => r.issues.includes(issueFilter));

  const issueCounts: Record<UnitIssue, number> = {
    vacant: 0, down_for_maintenance: 0, below_market: 0,
    expired_lease: 0, expiring_soon: 0, open_maintenance: 0,
  };
  for (const row of rentRoll.rows) {
    for (const issue of row.issues) issueCounts[issue]++;
  }
  const unitsWithIssues = rentRoll.rows.filter((r) => r.issues.length > 0).length;

  return (
    <>
      <section className="rounded-2xl border border-border bg-surface overflow-hidden anim-fade-up">
        <div className="px-4 sm:px-5 py-3.5 border-b border-border-subtle space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wide">
              Rent Roll{" "}
              <span className="text-fg-faint font-normal">
                · {filteredRows.length} of {rentRoll.rows.length} units
                {unitsWithIssues > 0 && ` · ${unitsWithIssues} with issues`}
              </span>
            </h2>
            <ViewToggle mode={viewMode} onChange={setViewMode} />
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={() => setIssueFilter("all")}
              className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${
                issueFilter === "all" ? "bg-accent border-accent text-accent-fg" : "border-border text-fg-muted hover:text-fg-secondary"
              }`}
            >
              All
            </button>
            {(Object.entries(issueCounts) as [UnitIssue, number][])
              .filter(([, count]) => count > 0)
              .map(([issue, count]) => (
                <button
                  key={issue}
                  onClick={() => setIssueFilter(issue === issueFilter ? "all" : issue)}
                  className={`text-[10px] px-2 py-1 rounded-md border transition-colors ${
                    issueFilter === issue ? ISSUE_LABELS[issue].color : "border-border text-fg-muted hover:text-fg-secondary"
                  }`}
                >
                  {ISSUE_LABELS[issue].label} ({count})
                </button>
              ))}
          </div>
        </div>

        {viewMode === "grid" ? (
          <div className="p-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3 stagger">
              {filteredRows.map((row) => (
                <UnitGridCard key={row.unit_id} row={row} propertyId={propertyId} onPeek={setPeekRow} />
              ))}
            </div>
            {filteredRows.length === 0 && (
              <p className="text-center py-12 text-sm text-fg-faint">No units match the selected filter</p>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["Unit", "Status", "Tenant", "Rent", "Market", "Gap", "Lease End", "Maint", "Issues"].map((h) => (
                    <th key={h} className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <UnitTableRow key={row.unit_id} row={row} propertyId={propertyId} expanded={expandedUnit === row.unit_id} onToggle={() => setExpandedUnit(expandedUnit === row.unit_id ? null : row.unit_id)} />
                ))}
                {filteredRows.length === 0 && (
                  <tr><td colSpan={9} className="text-center py-12 text-sm text-fg-faint">No units match the selected filter</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <SlidePanel open={!!peekRow} onClose={() => setPeekRow(null)} title={peekRow ? `Unit ${peekRow.unit_number}` : ""} width="md">
        {peekRow && <UnitPeek row={peekRow} propertyId={propertyId} />}
      </SlidePanel>
    </>
  );
}
