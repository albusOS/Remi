import { Empty } from "@/components/ui/Empty";
import { formatDate } from "@/components/documents/DocumentHelpers";
import type { SignalSummary } from "@/lib/types";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-error text-error-fg",
  high: "bg-warning text-warning-fg",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-surface-sunken text-fg-muted",
};

interface SignalsPanelProps {
  signals: SignalSummary[];
  loading: boolean;
}

export function SignalsPanel({ signals, loading }: SignalsPanelProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      {loading && <div className="p-8 text-center text-xs text-fg-faint animate-pulse">Loading signals...</div>}
      {!loading && signals.length === 0 && (
        <div className="flex items-center justify-center h-64">
          <Empty
            title="No signals detected"
            description="Signals appear when REMI detects notable situations in your portfolio data"
          />
        </div>
      )}
      {!loading && signals.length > 0 && (
        <div className="space-y-3 max-w-4xl">
          {signals.map((sig) => (
            <div key={sig.signal_id} className="rounded-xl border border-border p-4 hover:bg-surface-raised transition-colors">
              <div className="flex items-start gap-3">
                <span className={`mt-0.5 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${SEVERITY_COLORS[sig.severity] ?? SEVERITY_COLORS.low}`}>
                  {sig.severity}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-fg">{sig.description}</p>
                  <div className="flex items-center gap-3 mt-1.5 text-[10px] text-fg-faint">
                    <span>{sig.signal_type.replace(/_/g, " ")}</span>
                    <span>&middot;</span>
                    <span>{sig.entity_name}</span>
                    <span>&middot;</span>
                    <span>{formatDate(sig.detected_at)}</span>
                  </div>
                </div>
                <a
                  href={`/ask?q=${encodeURIComponent(`Explain the ${sig.signal_type.replace(/_/g, " ")} signal for ${sig.entity_name}`)}`}
                  className="shrink-0 text-[10px] text-accent/70 hover:text-accent"
                >
                  Ask REMI
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
