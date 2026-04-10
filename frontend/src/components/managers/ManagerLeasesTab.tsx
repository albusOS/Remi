"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmt$ } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { useApiQuery } from "@/hooks/useApiQuery";

type Sort = "urgency" | "rent" | "property";

export function ManagerLeasesTab({ managerId }: { managerId: string }) {
  const [sort, setSort] = useState<Sort>("urgency");

  const { data: leases, loading } = useApiQuery(
    () => api.leasesExpiring(365, { manager_id: managerId }),
    ["manager_leases_full", managerId],
  );

  if (loading) {
    return <div className="rounded-2xl border border-border bg-surface h-64 number-shimmer" />;
  }

  if (!leases || leases.leases.length === 0) {
    return (
      <div className="py-16 text-center text-sm text-fg-muted">
        No active leases in the next year
      </div>
    );
  }

  const expiring30 = leases.leases.filter((l) => !l.is_month_to_month && l.days_left <= 30).length;
  const expiring60 = leases.leases.filter((l) => !l.is_month_to_month && l.days_left > 30 && l.days_left <= 60).length;
  const totalRent = leases.leases.reduce((s, l) => s + l.monthly_rent, 0);

  const sorted = [...leases.leases].sort((a, b) => {
    if (sort === "urgency") {
      if (a.is_month_to_month !== b.is_month_to_month) return a.is_month_to_month ? 1 : -1;
      return a.days_left - b.days_left;
    }
    if (sort === "rent") return b.monthly_rent - a.monthly_rent;
    return a.property_name.localeCompare(b.property_name);
  });

  return (
    <div className="space-y-4">
      {/* Summary strip */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-fg-muted">
        <span><span className="text-fg font-semibold">{leases.total_expiring}</span> leases in window</span>
        {leases.month_to_month_count > 0 && (
          <>
            <span className="text-fg-ghost">·</span>
            <span><span className="text-warn font-semibold">{leases.month_to_month_count}</span> month-to-month</span>
          </>
        )}
        {expiring30 > 0 && (
          <>
            <span className="text-fg-ghost">·</span>
            <span className="text-error font-semibold">{expiring30} expiring &lt;30d</span>
          </>
        )}
        {expiring60 > 0 && (
          <>
            <span className="text-fg-ghost">·</span>
            <span className="text-warn font-semibold">{expiring60} expiring &lt;60d</span>
          </>
        )}
        <span className="text-fg-ghost">·</span>
        <span className="font-mono"><span className="text-fg font-semibold">{fmt$(totalRent)}</span>/mo</span>
      </div>

      {/* Sort */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-fg-faint uppercase tracking-wide">Sort</span>
        <div className="flex rounded-lg border border-border overflow-hidden text-[10px]">
          {(["urgency", "rent", "property"] as Sort[]).map((s) => (
            <button
              key={s}
              onClick={() => setSort(s)}
              className={`px-2.5 py-1.5 transition-colors capitalize ${
                sort === s ? "bg-accent text-accent-fg" : "text-fg-muted hover:bg-surface-raised"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {["Tenant", "Property", "Unit", "Rent", "Market", "Expires", ""].map((h) => (
                  <th key={h} className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase tracking-wide whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((l) => {
                const urgent = !l.is_month_to_month && l.days_left <= 30;
                const warn = !l.is_month_to_month && l.days_left <= 60;
                return (
                  <tr key={l.lease_id} className="border-b border-border-subtle hover:bg-surface-raised transition-colors">
                    <td className="px-4 py-2.5 font-medium text-fg">{l.tenant_name}</td>
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/properties/${l.property_id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="text-fg-secondary hover:text-accent transition-colors"
                      >
                        {l.property_name}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/properties/${l.property_id}/units/${l.unit_id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="font-mono text-xs text-fg-secondary hover:text-accent transition-colors"
                      >
                        {l.unit_number}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[12px] text-fg-secondary tabular-nums">{fmt$(l.monthly_rent)}</td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-fg-muted tabular-nums">{fmt$(l.market_rent)}</td>
                    <td className="px-4 py-2.5 text-[11px] text-fg-secondary">
                      {l.is_month_to_month ? <Badge variant="default">MTM</Badge> : l.end_date}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {l.is_month_to_month ? (
                        <span className="text-fg-ghost text-[10px]">rolling</span>
                      ) : (
                        <span className={`font-mono font-semibold text-[11px] ${urgent ? "text-error" : warn ? "text-warn" : "text-fg-muted"}`}>
                          {l.days_left}d
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
