import type { UnitIssue } from "@/lib/types";

export const ISSUE_LABELS: Record<UnitIssue, { label: string; color: string; gridColor: string }> = {
  vacant: { label: "Vacant", color: "bg-error-soft text-error-fg border-error/30", gridColor: "border-error/40 bg-error-soft/50" },
  down_for_maintenance: { label: "Down", color: "bg-orange-500/20 text-orange-300 border-orange-500/30", gridColor: "border-orange-500/30 bg-orange-500/10" },
  below_market: { label: "Below Market", color: "bg-warn-soft text-warn-fg border-warn/30", gridColor: "border-warn/30 bg-warn-soft/50" },
  expired_lease: { label: "Expired Lease", color: "bg-error-soft text-error-fg border-error/30", gridColor: "border-error/40 bg-error-soft/50" },
  expiring_soon: { label: "Expiring", color: "bg-warn-soft text-warn-fg border-warn/30", gridColor: "border-warn/30 bg-warn-soft/50" },
  open_maintenance: { label: "Maint.", color: "bg-sky-500/20 text-sky-300 border-sky-500/30", gridColor: "border-sky-500/30 bg-sky-500/5" },
};

export function IssuePill({ issue }: { issue: UnitIssue }) {
  const cfg = ISSUE_LABELS[issue];
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}
