"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import type {
  MeetingBriefResponse,
  MeetingBriefListResponse,
  MeetingAgendaItem,
} from "@/lib/types";

const SEVERITY_VARIANT: Record<string, "red" | "amber" | "blue"> = {
  high: "red",
  medium: "amber",
  low: "blue",
};

const OWNER_LABEL: Record<string, string> = {
  manager: "PM",
  director: "Director",
  both: "Joint",
};

function fmtTimestamp(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function AgendaCard({ item, index }: { item: MeetingAgendaItem; index: number }) {
  const [expanded, setExpanded] = useState(index === 0);

  return (
    <div className="rounded-xl border border-border bg-surface overflow-hidden">
      <button
        onClick={() => setExpanded((x) => !x)}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-surface-raised/50 transition-colors"
      >
        <span className="shrink-0 w-6 h-6 rounded-full bg-surface-sunken border border-border-subtle flex items-center justify-center text-[10px] font-bold text-fg-muted">
          {index + 1}
        </span>
        <span className="flex-1 text-sm font-medium text-fg">{item.topic}</span>
        <Badge variant={SEVERITY_VARIANT[item.severity] ?? "blue"}>{item.severity}</Badge>
        <svg
          className={`w-4 h-4 text-fg-muted transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-4 border-t border-border-subtle">
          {item.talking_points.length > 0 && (
            <div className="pt-4">
              <h4 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide mb-2">Talking Points</h4>
              <ul className="space-y-1.5">
                {item.talking_points.map((tp, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-fg-secondary">
                    <span className="shrink-0 mt-1.5 w-1.5 h-1.5 rounded-full bg-accent/60" />
                    {tp}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {item.questions.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide mb-2">Questions to Ask</h4>
              <ul className="space-y-1.5">
                {item.questions.map((q, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-fg-secondary italic">
                    <span className="shrink-0 text-accent mt-0.5">?</span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {item.suggested_actions.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide mb-2">Suggested Actions</h4>
              <div className="space-y-2">
                {item.suggested_actions.map((action, i) => (
                  <div key={i} className="rounded-lg bg-surface-sunken border border-border-subtle px-3.5 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-fg font-medium">{action.title}</span>
                      <Badge variant={SEVERITY_VARIANT[action.priority] ?? "blue"}>{action.priority}</Badge>
                      <span className="text-[10px] text-fg-faint px-1.5 py-0.5 rounded bg-surface border border-border-subtle">
                        {OWNER_LABEL[action.owner] ?? action.owner}
                      </span>
                    </div>
                    <p className="text-xs text-fg-muted mt-1">{action.description}</p>
                    <p className="text-[10px] text-fg-faint mt-1">{action.timeframe}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function BriefView({
  brief,
  currentHash,
  onRegenerate,
  generating,
}: {
  brief: MeetingBriefResponse;
  currentHash: string | null;
  onRegenerate: () => void;
  generating: boolean;
}) {
  const b = brief.brief;
  const analysis = brief.analysis;
  const isStale = currentHash !== null && brief.snapshot_hash !== currentHash;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-fg">Meeting Brief</h2>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-fg-faint">
              {fmtTimestamp(brief.generated_at)}
            </span>
            {brief.focus && (
              <Badge variant="default">{brief.focus}</Badge>
            )}
            {isStale ? (
              <span className="text-[10px] font-medium text-warn bg-warn-soft px-1.5 py-0.5 rounded border border-warn/20">
                Data changed since this brief
              </span>
            ) : (
              <span className="text-[10px] font-medium text-ok bg-ok/10 px-1.5 py-0.5 rounded border border-ok/20">
                Current
              </span>
            )}
          </div>
          <p className="text-[10px] text-fg-ghost mt-0.5 font-mono">
            snapshot {brief.snapshot_hash}
          </p>
        </div>
        <button
          onClick={onRegenerate}
          disabled={generating}
          className="shrink-0 h-8 px-3.5 rounded-xl border border-border text-xs font-medium text-fg-muted hover:text-accent hover:border-accent/40 transition-all flex items-center gap-1.5 disabled:opacity-40"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
          </svg>
          {generating ? "Generating..." : isStale ? "Regenerate (data changed)" : "Regenerate"}
        </button>
      </div>

      {/* Executive summary */}
      <section className="rounded-xl border border-border bg-surface p-5">
        <h3 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide mb-3">Executive Summary</h3>
        <div className="text-sm text-fg-secondary leading-relaxed whitespace-pre-line">{b.summary}</div>
      </section>

      {/* Positives */}
      {b.positives.length > 0 && (
        <section className="rounded-xl border border-ok/20 bg-ok/5 p-5">
          <h3 className="text-[10px] font-semibold text-ok uppercase tracking-wide mb-3">What&apos;s Going Well</h3>
          <ul className="space-y-1.5">
            {b.positives.map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-fg-secondary">
                <span className="shrink-0 mt-1 text-ok">+</span>
                {p}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Agenda items */}
      <div className="space-y-3">
        <h3 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide">
          Agenda
          <span className="text-fg-faint font-normal ml-1">
            &middot; {b.agenda.length} items &middot;
            {b.agenda.reduce((n, a) => n + a.suggested_actions.length, 0)} actions
            {b.follow_up_date && <> &middot; Follow-up: {b.follow_up_date}</>}
          </span>
        </h3>
        {b.agenda.map((item, i) => (
          <AgendaCard key={i} item={item} index={i} />
        ))}
      </div>

      {/* Analysis themes */}
      {analysis?.themes && analysis.themes.length > 0 && (
        <section className="rounded-xl border border-border bg-surface overflow-hidden">
          <div className="px-5 py-3.5 border-b border-border-subtle">
            <h3 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide">
              Underlying Themes <span className="text-fg-faint font-normal">&middot; {analysis.themes.length}</span>
            </h3>
          </div>
          <div className="divide-y divide-border-subtle">
            {analysis.themes.map((theme) => (
              <div key={theme.id} className="px-5 py-3.5">
                <div className="flex items-center gap-2">
                  <Badge variant={SEVERITY_VARIANT[theme.severity] ?? "blue"}>{theme.severity}</Badge>
                  <span className="text-sm font-medium text-fg">{theme.title}</span>
                  {theme.monthly_impact > 0 && (
                    <span className="text-xs text-warn font-mono ml-auto">-${theme.monthly_impact.toLocaleString()}/mo</span>
                  )}
                </div>
                <p className="text-xs text-fg-muted mt-1">{theme.summary}</p>
                {theme.affected_properties.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {theme.affected_properties.map((p) => (
                      <span key={p} className="text-[10px] text-fg-faint bg-surface-sunken border border-border-subtle rounded px-1.5 py-0.5">{p}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Data gaps */}
      {analysis?.data_gaps && analysis.data_gaps.length > 0 && (
        <section className="rounded-xl border border-border-subtle bg-surface-sunken/50 p-5">
          <h3 className="text-[10px] font-semibold text-fg-faint uppercase tracking-wide mb-2">Data Gaps</h3>
          <ul className="space-y-1">
            {analysis.data_gaps.map((gap, i) => (
              <li key={i} className="text-xs text-fg-faint">&bull; {gap}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Usage */}
      <p className="text-[10px] text-fg-ghost text-right">
        {brief.usage.prompt_tokens.toLocaleString()} prompt + {brief.usage.completion_tokens.toLocaleString()} completion tokens
      </p>
    </div>
  );
}

function PastBriefRow({
  brief,
  currentHash,
  isActive,
  onClick,
}: {
  brief: MeetingBriefResponse;
  currentHash: string | null;
  isActive: boolean;
  onClick: () => void;
}) {
  const isStale = currentHash !== null && brief.snapshot_hash !== currentHash;
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3.5 py-2.5 border-b border-border-subtle hover:bg-surface-raised/50 transition-colors ${
        isActive ? "bg-accent/5 border-l-2 border-l-accent" : ""
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-xs text-fg font-medium">{fmtTimestamp(brief.generated_at)}</span>
        {isStale ? (
          <span className="w-1.5 h-1.5 rounded-full bg-warn shrink-0" title="Stale — data has changed" />
        ) : (
          <span className="w-1.5 h-1.5 rounded-full bg-ok shrink-0" title="Current" />
        )}
      </div>
      <div className="flex items-center gap-1.5 mt-0.5">
        <span className="text-[10px] text-fg-faint font-mono">{brief.snapshot_hash}</span>
        {brief.focus && <span className="text-[10px] text-fg-muted">&middot; {brief.focus}</span>}
      </div>
    </button>
  );
}

export function ReviewPrepTab({ managerId }: { managerId: string }) {
  const [listData, setListData] = useState<MeetingBriefListResponse | null>(null);
  const [activeBrief, setActiveBrief] = useState<MeetingBriefResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState("");

  const loadBriefs = useCallback(async () => {
    try {
      const data = await api.listMeetingBriefs(managerId);
      setListData(data);
      if (data.briefs.length > 0 && !activeBrief) {
        setActiveBrief(data.briefs[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load briefs");
    } finally {
      setLoading(false);
    }
  }, [managerId, activeBrief]);

  useEffect(() => { loadBriefs(); }, [loadBriefs]);

  const generate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await api.generateMeetingBrief(managerId, focus || undefined);
      setActiveBrief(result);
      const updated = await api.listMeetingBriefs(managerId);
      setListData(updated);
      setFocus("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate meeting brief");
    } finally {
      setGenerating(false);
    }
  }, [managerId, focus]);

  const currentHash = listData?.current_snapshot_hash ?? null;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <span className="text-sm text-fg-faint animate-pulse">Loading...</span>
      </div>
    );
  }

  const hasBriefs = listData && listData.briefs.length > 0;

  return (
    <div className="space-y-6">
      {/* Generate section */}
      <div className="rounded-xl border border-border bg-surface p-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-accent/10 border border-accent/20 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-fg">
              {hasBriefs ? "Generate New Brief" : "Meeting Brief"}
            </h3>
            <p className="text-xs text-fg-muted mt-0.5">
              AI analysis of this manager&apos;s portfolio — talking points, questions, and action items.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-3">
          <input
            type="text"
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="Optional: focus area (e.g. delinquency, vacancies)"
            className="flex-1 bg-surface-sunken border border-border rounded-xl px-3 py-2 text-sm text-fg placeholder:text-fg-ghost focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-all"
            onKeyDown={(e) => e.key === "Enter" && generate()}
          />
          <button
            onClick={generate}
            disabled={generating}
            className="shrink-0 px-4 py-2 rounded-xl bg-accent text-accent-fg text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-40"
          >
            {generating ? "Generating..." : "Generate"}
          </button>
        </div>
        {error && <p className="text-sm text-error mt-2">{error}</p>}
        {generating && (
          <div className="flex items-center gap-3 mt-3">
            <div className="relative w-5 h-5">
              <div className="absolute inset-0 rounded-full border-2 border-accent/20" />
              <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent animate-spin" />
            </div>
            <span className="text-xs text-fg-muted">Analyzing portfolio... this takes 15–30 seconds</span>
          </div>
        )}
      </div>

      {/* Past briefs + active brief */}
      {hasBriefs && (
        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-4">
          {/* Sidebar: past briefs */}
          <div className="rounded-xl border border-border bg-surface overflow-hidden">
            <div className="px-3.5 py-2.5 border-b border-border-subtle">
              <h3 className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide">
                Past Briefs <span className="text-fg-faint font-normal">&middot; {listData!.total}</span>
              </h3>
            </div>
            <div className="max-h-[500px] overflow-y-auto">
              {listData!.briefs.map((b) => (
                <PastBriefRow
                  key={b.id}
                  brief={b}
                  currentHash={currentHash}
                  isActive={activeBrief?.id === b.id}
                  onClick={() => setActiveBrief(b)}
                />
              ))}
            </div>
          </div>

          {/* Main: active brief */}
          {activeBrief && (
            <BriefView
              brief={activeBrief}
              currentHash={currentHash}
              onRegenerate={generate}
              generating={generating}
            />
          )}
        </div>
      )}
    </div>
  );
}
