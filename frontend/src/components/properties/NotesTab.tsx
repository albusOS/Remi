"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { Badge } from "@/components/ui/Badge";

export function NotesTab({ entityType, entityId }: { entityType: string; entityId: string }) {
  const { data, loading, refetch } = useApiQuery(() => api.listEntityNotes(entityType, entityId), [entityType, entityId]);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleAdd() {
    if (!draft.trim()) return;
    setSaving(true);
    try { await api.createEntityNote(entityType, entityId, draft.trim()); setDraft(""); refetch(); } finally { setSaving(false); }
  }
  async function handleDelete(noteId: string) { await api.deleteEntityNote(noteId); refetch(); }

  if (loading) return <div className="py-12 text-center text-sm text-fg-faint animate-pulse">Loading notes...</div>;
  const notes = data?.notes ?? [];

  return (
    <section className="rounded-2xl border border-border bg-surface overflow-hidden anim-fade-up">
      <div className="px-5 py-3.5 border-b border-border-subtle">
        <h2 className="text-xs font-semibold text-fg-secondary uppercase tracking-wide">Notes <span className="text-fg-faint font-normal">· {notes.length}</span></h2>
      </div>
      <div className="p-4 border-b border-border-subtle">
        <div className="flex gap-2">
          <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleAdd()} placeholder="Add a note..." className="flex-1 bg-surface-sunken border border-border rounded-xl px-3.5 py-2.5 text-sm text-fg placeholder:text-fg-ghost focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-all" />
          <button onClick={handleAdd} disabled={saving || !draft.trim()} className="px-5 py-2.5 rounded-xl bg-accent text-accent-fg text-sm font-medium disabled:opacity-40 hover:bg-accent-hover transition-colors">Add</button>
        </div>
      </div>
      {notes.length > 0 ? (
        <div className="divide-y divide-border-subtle">
          {notes.map((note) => (
            <div key={note.id} className="px-5 py-3.5 group flex items-start gap-3 hover:bg-surface-raised/50 transition-colors">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-fg">{note.content}</p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant={note.provenance === "user_stated" ? "blue" : note.provenance === "data_derived" ? "emerald" : "violet"}>{note.provenance}</Badge>
                  {note.created_at && <span className="text-xs text-fg-faint">{fmtDate(note.created_at)}</span>}
                </div>
              </div>
              {note.provenance === "user_stated" && (
                <button onClick={() => handleDelete(note.id)} className="shrink-0 text-xs text-fg-ghost hover:text-error opacity-0 group-hover:opacity-100 transition-all">Delete</button>
              )}
            </div>
          ))}
        </div>
      ) : <div className="py-12 text-center text-sm text-fg-faint">No notes yet</div>}
    </section>
  );
}
