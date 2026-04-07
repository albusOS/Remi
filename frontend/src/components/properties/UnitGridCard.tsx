import Link from "next/link";
import { fmt$ } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { IssuePill, ISSUE_LABELS } from "./IssueLabels";
import type { RentRollRow } from "@/lib/types";

export function UnitGridCard({ row, propertyId, onPeek }: { row: RentRollRow; propertyId: string; onPeek: (row: RentRollRow) => void }) {
  const hasIssues = row.issues.length > 0;
  const worstIssue = row.issues[0];
  const gridAccent = worstIssue ? ISSUE_LABELS[worstIssue].gridColor : "border-border bg-surface";

  return (
    <div
      onClick={() => onPeek(row)}
      className={`rounded-xl border-2 p-3 cursor-pointer card-hover group transition-all ${gridAccent} ${
        !hasIssues ? "hover:border-accent/30" : ""
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-sm font-bold text-fg">{row.unit_number}</span>
        <Badge
          variant={
            row.status === "occupied" ? "emerald" :
            row.status === "vacant" ? "red" :
            row.status === "maintenance" ? "amber" : "default"
          }
        >
          {row.status}
        </Badge>
      </div>

      {row.tenant ? (
        <p className="text-xs text-fg-secondary truncate">{row.tenant.name}</p>
      ) : (
        <p className="text-xs text-fg-ghost italic">Vacant</p>
      )}

      <div className="flex items-baseline justify-between mt-2">
        <span className="font-mono text-xs text-fg-secondary">{fmt$(row.current_rent)}</span>
        {row.pct_below_market > 0 && (
          <span className="text-[10px] text-warn font-medium">-{row.pct_below_market}%</span>
        )}
      </div>

      {hasIssues && (
        <div className="flex flex-wrap gap-1 mt-2">
          {row.issues.slice(0, 2).map((issue) => (
            <IssuePill key={issue} issue={issue} />
          ))}
          {row.issues.length > 2 && (
            <span className="text-[10px] text-fg-muted">+{row.issues.length - 2}</span>
          )}
        </div>
      )}

      <Link
        href={`/properties/${propertyId}/units/${row.unit_id}`}
        onClick={(e) => e.stopPropagation()}
        className="block mt-2 text-[10px] text-fg-ghost group-hover:text-accent transition-colors"
      >
        Open →
      </Link>
    </div>
  );
}
