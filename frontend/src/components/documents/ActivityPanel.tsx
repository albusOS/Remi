import { Empty } from "@/components/ui/Empty";
import { formatDate } from "@/components/documents/DocumentHelpers";

interface ActivityPanelProps {
  events: Array<Record<string, unknown>>;
  loading: boolean;
}

export function ActivityPanel({ events, loading }: ActivityPanelProps) {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      {loading && <div className="p-8 text-center text-xs text-fg-faint animate-pulse">Loading activity...</div>}
      {!loading && events.length === 0 && (
        <div className="flex items-center justify-center h-64">
          <Empty title="No activity yet" description="Events will appear as data is ingested and entities change" />
        </div>
      )}
      {!loading && events.length > 0 && (
        <div className="space-y-2 max-w-4xl">
          {events.map((evt, i) => (
            <div key={(evt.id as string) ?? i} className="rounded-lg border border-border-subtle p-3 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-fg">
                  {String(evt.source ?? "")}
                  {evt.report_type ? <span className="text-fg-faint ml-2">{String(evt.report_type).replace(/_/g, " ")}</span> : null}
                </p>
                <div className="flex items-center gap-3 mt-1 text-[10px] text-fg-faint">
                  {(evt.created as number) > 0 && <span className="text-ok">+{evt.created as number} created</span>}
                  {(evt.updated as number) > 0 && <span className="text-accent">{evt.updated as number} updated</span>}
                  {(evt.removed as number) > 0 && <span className="text-error">{evt.removed as number} removed</span>}
                </div>
              </div>
              <span className="text-[10px] text-fg-ghost shrink-0">
                {evt.timestamp ? formatDate(evt.timestamp as string) : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
