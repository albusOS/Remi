"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { fmt$, fmtDate } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { Badge } from "@/components/ui/Badge";
import type { LeaseListItem } from "@/lib/types";

function LeaseRow({ lease, propertyId }: { lease: LeaseListItem; propertyId: string }) {
  return (
    <tr className="border-b border-border-subtle hover:bg-surface-raised transition-colors">
      <td className="px-4 py-2.5 text-sm text-fg">{lease.tenant}</td>
      <td className="px-4 py-2.5"><Link href={`/properties/${propertyId}/units/${lease.unit_id}`} className="font-mono text-sm text-fg-secondary hover:text-accent transition-colors">{lease.unit_id.slice(-6)}</Link></td>
      <td className="px-4 py-2.5"><Badge variant={lease.status === "active" ? "emerald" : lease.status === "expired" ? "red" : "default"}>{lease.status}</Badge></td>
      <td className="px-4 py-2.5 font-mono text-sm text-fg-secondary">{fmt$(lease.rent)}</td>
      <td className="px-4 py-2.5 text-sm text-fg-muted">{fmtDate(lease.start)}</td>
      <td className="px-4 py-2.5 text-sm text-fg-muted">{fmtDate(lease.end)}</td>
    </tr>
  );
}

export function LeasesTab({ propertyId }: { propertyId: string }) {
  const { data, loading } = useApiQuery(() => api.listLeases({ property_id: propertyId }), [propertyId]);
  if (loading) return <div className="py-12 text-center text-sm text-fg-faint animate-pulse">Loading leases...</div>;
  if (!data || data.leases.length === 0) return <div className="py-12 text-center text-sm text-fg-faint">No leases found</div>;
  const active = data.leases.filter((l) => l.status === "active");
  const other = data.leases.filter((l) => l.status !== "active");
  return (
    <section className="rounded-2xl border border-border bg-surface overflow-hidden anim-fade-up">
      <div className="px-5 py-3.5 border-b border-border-subtle">
        <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wide">All Leases <span className="text-fg-faint font-normal">· {data.count} total · {active.length} active</span></h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border">{["Tenant", "Unit", "Status", "Rent", "Start", "End"].map((h) => <th key={h} className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide">{h}</th>)}</tr></thead>
          <tbody>{[...active, ...other].map((l) => <LeaseRow key={l.id} lease={l} propertyId={propertyId} />)}</tbody>
        </table>
      </div>
    </section>
  );
}
