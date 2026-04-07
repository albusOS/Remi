"use client";

import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { Badge } from "@/components/ui/Badge";

export function ActivityTab({ propertyId }: { propertyId: string }) {
  const { data, loading } = useApiQuery(() => api.entityEvents(propertyId, 50), [propertyId]);
  if (loading) return <div className="py-12 text-center text-sm text-fg-faint animate-pulse">Loading activity...</div>;
  if (!data || data.changesets.length === 0) return <div className="py-12 text-center text-sm text-fg-faint">No activity recorded yet</div>;
  return (
    <section className="rounded-2xl border border-border bg-surface overflow-hidden anim-fade-up">
      <div className="px-5 py-3.5 border-b border-border-subtle">
        <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wide">Activity Timeline <span className="text-fg-faint font-normal">· {data.changesets.length} events</span></h2>
      </div>
      <div className="divide-y divide-border-subtle">
        {data.changesets.map((cs) => (
          <div key={cs.id} className="px-5 py-3.5 flex items-start gap-4 group hover:bg-surface-raised/50 transition-colors">
            <div className="shrink-0 w-2 h-2 rounded-full bg-accent mt-1.5 group-hover:scale-150 transition-transform" />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="text-sm text-fg font-medium">{cs.source}</span>
                {cs.report_type && <Badge variant="default">{cs.report_type}</Badge>}
                <span className="text-xs text-fg-faint ml-auto shrink-0">{fmtDate(cs.timestamp)}</span>
              </div>
              <div className="flex gap-3 mt-1 text-xs text-fg-muted">
                {cs.summary.created > 0 && <span className="text-ok">+{cs.summary.created} created</span>}
                {cs.summary.updated > 0 && <span className="text-warn">{cs.summary.updated} updated</span>}
                {cs.summary.removed > 0 && <span className="text-error">{cs.summary.removed} removed</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
