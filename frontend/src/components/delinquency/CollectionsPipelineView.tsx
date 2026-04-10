"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmt$ } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageContainer } from "@/components/ui/PageContainer";
import { PipelineStrip, type PipelineStage } from "@/components/ui/PipelineStrip";
import { StatHero } from "@/components/ui/StatHero";
import { Badge } from "@/components/ui/Badge";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ManagerFilter } from "@/components/ui/ManagerFilter";
import type { DelinquencyBoard, EntityNoteResponse } from "@/lib/types";

const STAGE_ORDER = ["current", "notice", "demand", "filing", "hearing", "eviction", "judgment"] as const;
type Stage = (typeof STAGE_ORDER)[number];

function collectionsStage(status: string): Stage {
  const s = status.toLowerCase().trim();
  if (STAGE_ORDER.includes(s as Stage)) return s as Stage;
  if (s.includes("evict")) return "eviction";
  if (s.includes("hearing")) return "hearing";
  if (s.includes("filing")) return "filing";
  if (s.includes("demand")) return "demand";
  if (s.includes("notice")) return "notice";
  return "current";
}

function daysSince(date: string | null): number | null {
  if (!date) return null;
  const d = new Date(date);
  if (isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / 86_400_000);
}

interface NoteSeed { content: string; id: string | null; }

function InlineNoteCell({ tenantId, reportNote, seed, onMutate }: { tenantId: string; reportNote?: string | null; seed: NoteSeed | undefined; onMutate: () => void; }) {
  const [userNote, setUserNote] = useState<string | null>(seed?.content ?? null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [noteId, setNoteId] = useState<string | null>(seed?.id ?? null);

  useEffect(() => {
    if (seed !== undefined) { setUserNote(seed.content); setNoteId(seed.id); }
  }, [seed]);

  const save = async () => {
    setSaving(true);
    try {
      if (noteId && draft) { await api.updateEntityNote(noteId, draft); }
      else if (noteId && !draft) { await api.deleteEntityNote(noteId); setNoteId(null); }
      else if (draft) { const c = await api.createEntityNote("Tenant", tenantId, draft); setNoteId(c.id); }
      setUserNote(draft);
      setEditing(false);
      onMutate();
    } catch { /* keep editing */ }
    finally { setSaving(false); }
  };

  if (userNote === null) return <span className="text-fg-ghost text-[10px]">...</span>;

  if (editing) {
    return (
      <div className="flex flex-col gap-1 min-w-[140px]">
        {reportNote && <p className="text-[10px] text-fg-ghost italic mb-0.5">{reportNote}</p>}
        <textarea ref={null} value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save(); if (e.key === "Escape") setEditing(false); }} rows={2} className="bg-surface border border-border rounded px-2 py-1 text-xs text-fg resize-none focus:outline-none focus:border-accent" autoFocus />
        <div className="flex gap-1">
          <button onClick={save} disabled={saving} className="text-[10px] text-accent hover:underline">{saving ? "..." : "Save"}</button>
          <button onClick={() => setEditing(false)} className="text-[10px] text-fg-ghost hover:underline">Cancel</button>
        </div>
      </div>
    );
  }

  const display = userNote || reportNote;
  return (
    <button onClick={() => { setDraft(userNote ?? ""); setEditing(true); }} className="text-left text-xs max-w-[200px] truncate" title={display || "Click to add note"}>
      {reportNote && !userNote && <span className="text-fg-ghost italic">{reportNote}</span>}
      {userNote && <span className="text-fg-muted">{userNote}</span>}
      {!display && <span className="text-fg-ghost italic">+ note</span>}
    </button>
  );
}

function useBatchNotes(tenantIds: string[]) {
  const [noteMap, setNoteMap] = useState<Record<string, NoteSeed>>({});
  const idsKey = tenantIds.join(",");
  const refresh = useCallback(() => {
    if (!tenantIds.length) return;
    api.batchEntityNotes("Tenant", tenantIds).then((r) => {
      const map: Record<string, NoteSeed> = {};
      for (const [eid, notes] of Object.entries(r.notes_by_entity)) {
        const first = (notes as EntityNoteResponse[]).find((n) => n.provenance === "user_stated");
        map[eid] = { content: first?.content || "", id: first?.id || null };
      }
      setNoteMap(map);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey]);
  useEffect(() => { refresh(); }, [refresh]);
  return { noteMap, refresh };
}

export function CollectionsPipelineView() {
  const [managerId, setManagerId] = useState("");
  const effectiveScope = managerId ? { manager_id: managerId } : undefined;

  const { data, loading, error, refetch } = useApiQuery<DelinquencyBoard>(
    () => api.delinquencyBoard(effectiveScope),
    [managerId],
  );

  const tenantIds = data?.tenants.map((t) => t.tenant_id) ?? [];
  const { noteMap, refresh: refreshNotes } = useBatchNotes(tenantIds);

  // Build pipeline stages
  const stages: PipelineStage[] = [];
  if (data) {
    const counts: Record<string, { count: number; amount: number }> = {};
    for (const t of data.tenants) {
      const s = collectionsStage(t.status);
      if (!counts[s]) counts[s] = { count: 0, amount: 0 };
      counts[s].count++;
      counts[s].amount += t.balance_owed;
    }
    const stageOrder: { id: Stage; label: string; variant: PipelineStage["variant"] }[] = [
      { id: "current", label: "Current", variant: "warn" },
      { id: "notice", label: "Notice", variant: "warn" },
      { id: "demand", label: "Demand", variant: "warn" },
      { id: "filing", label: "Filing", variant: "error" },
      { id: "hearing", label: "Hearing", variant: "error" },
      { id: "eviction", label: "Eviction", variant: "error" },
      { id: "judgment", label: "Judgment", variant: "error" },
    ];
    for (const s of stageOrder) {
      if ((counts[s.id]?.count ?? 0) > 0) {
        stages.push({ id: s.id, label: s.label, count: counts[s.id].count, amount: counts[s.id].amount, variant: s.variant });
      }
    }
  }

  return (
    <PageContainer>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-fg">Delinquency</h1>
          <p className="text-sm text-fg-muted mt-1">Collections pipeline and outstanding balances</p>
        </div>
        <ManagerFilter value={managerId} onChange={setManagerId} />
      </div>

      {data && data.total_delinquent > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatHero
            label="Total Owed"
            value={fmt$(data.total_balance)}
            color="var(--color-error-fg)"
            supporting={[
              { label: "Tenants", value: String(data.total_delinquent) },
              { label: "Avg Balance", value: fmt$(data.total_balance / data.total_delinquent) },
            ]}
          />
          {stages.length > 0 && (
            <div className="sm:col-span-2">
              <PipelineStrip stages={stages} />
            </div>
          )}
        </div>
      )}

      {data && data.total_delinquent === 0 && (
        <div className="py-12 text-center text-sm text-fg-faint">No delinquent tenants</div>
      )}

      <ErrorBanner error={error} onRetry={refetch} />

      {loading && (
        <div className="rounded-2xl border border-border bg-surface overflow-hidden">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex gap-4 px-4 py-3 border-b border-border-subtle">
              <div className="h-3 w-32 rounded bg-border number-shimmer" />
              <div className="h-3 w-24 rounded bg-border number-shimmer" />
              <div className="h-3 w-16 rounded bg-border number-shimmer ml-auto" />
            </div>
          ))}
        </div>
      )}

      {!loading && data && data.tenants.length > 0 && (
        <div className="rounded-xl border border-border bg-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["Tenant", "Property / Unit", "Stage", "Balance", "30+d", "Days Since Payment", "Notes"].map((h) => (
                    <th key={h} className="text-left px-4 py-2.5 text-[11px] font-semibold text-fg-muted uppercase tracking-wide whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.tenants.map((t) => {
                  const stage = collectionsStage(t.status);
                  const days = daysSince(t.last_payment_date);
                  const stuck = stage === "current" && (days ?? 0) > 10;
                  const stageVariant = ["filing", "hearing", "eviction", "judgment"].includes(stage) ? "red" : "amber";
                  return (
                    <tr key={t.tenant_id} className={`border-b border-border-subtle hover:bg-surface-raised transition-colors ${stuck ? "bg-error-soft/20" : ""}`}>
                      <td className="px-4 py-2.5 font-medium text-fg">{t.tenant_name}</td>
                      <td className="px-4 py-2.5 text-xs">
                        <div className="flex flex-col gap-0.5">
                          {t.property_id ? (
                            <Link href={`/properties/${t.property_id}`} className="text-fg-secondary hover:text-accent transition-colors">{t.property_name || "—"}</Link>
                          ) : <span className="text-fg-secondary">{t.property_name || "—"}</span>}
                          <span className="text-fg-faint font-mono">{t.unit_number || "—"}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge variant={stageVariant}>{stage}</Badge>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-error-fg font-semibold">{fmt$(t.balance_owed)}</td>
                      <td className="px-4 py-2.5 font-mono text-warn">{t.balance_30_plus > 0 ? fmt$(t.balance_30_plus) : "—"}</td>
                      <td className={`px-4 py-2.5 font-mono ${(days ?? 0) > 30 ? "text-error-fg font-semibold" : "text-fg-secondary"}`}>
                        {days != null ? `${days}d` : "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        <InlineNoteCell tenantId={t.tenant_id} reportNote={t.delinquency_notes} seed={noteMap[t.tenant_id]} onMutate={refreshNotes} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
