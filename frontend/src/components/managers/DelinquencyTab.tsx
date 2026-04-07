"use client";

import Link from "next/link";
import { fmt$, fmtDate } from "@/lib/format";
import { MetricCard } from "@/components/ui/MetricCard";
import { MetricStrip } from "@/components/ui/MetricStrip";
import { Badge } from "@/components/ui/Badge";
import type { DelinquencyBoard } from "@/lib/types";

export function DelinquencyTab({ data }: { data: DelinquencyBoard | null }) {
  if (!data || data.total_delinquent === 0) {
    return <p className="text-sm text-fg-faint text-center py-12">No delinquent tenants</p>;
  }

  return (
    <div className="space-y-4">
      <MetricStrip className="lg:grid-cols-2">
        <MetricCard label="Delinquent Tenants" value={data.total_delinquent} alert />
        <MetricCard label="Total Balance Owed" value={fmt$(data.total_balance)} alert />
      </MetricStrip>
      <div className="rounded-xl border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Tenant</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Property</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Unit</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Status</th>
                <th className="text-right px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">0-30</th>
                <th className="text-right px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">30+</th>
                <th className="text-right px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Total</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold text-fg-muted uppercase">Last Paid</th>
              </tr>
            </thead>
            <tbody>
              {data.tenants.map((t) => (
                <tr key={t.tenant_id} className="border-b border-border-subtle hover:bg-surface-raised">
                  <td className="px-4 py-2 text-fg font-medium">{t.tenant_name}</td>
                  <td className="px-4 py-2">
                    {t.property_id ? (
                      <Link href={`/properties/${t.property_id}`} className="text-fg-secondary hover:text-accent transition-colors">{t.property_name || "—"}</Link>
                    ) : (
                      <span className="text-fg-secondary">{t.property_name || "—"}</span>
                    )}
                  </td>
                  <td className="px-4 py-2 font-mono">
                    {t.property_id && t.unit_id ? (
                      <Link href={`/properties/${t.property_id}/units/${t.unit_id}`} className="text-fg-secondary hover:text-accent transition-colors">{t.unit_number || "—"}</Link>
                    ) : (
                      <span className="text-fg-secondary">{t.unit_number || "—"}</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={t.status === "evict" ? "red" : t.status === "notice" ? "amber" : "blue"}>{t.status}</Badge>
                  </td>
                  <td className="px-4 py-2 text-right text-fg-secondary font-mono">{fmt$(t.balance_0_30)}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    <span className={t.balance_30_plus > 0 ? "text-error" : "text-fg-muted"}>{fmt$(t.balance_30_plus)}</span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono font-bold text-error">{fmt$(t.balance_owed)}</td>
                  <td className="px-4 py-2 text-fg-muted">{t.last_payment_date ? fmtDate(t.last_payment_date) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
