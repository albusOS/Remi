"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Empty } from "@/components/ui/Empty";
import type { DocumentMeta, ManagerListItem, NeedsManagerResponse } from "@/lib/types";

// Report types that embed per-row manager tags (Tags column) so auto-assign
// can resolve properties without explicit manager selection.
const SELF_TAGGING_TYPES = ["lease_expiration", "delinquency"];

export function DocumentsView() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);
  const [managers, setManagers] = useState<ManagerListItem[]>([]);
  const [needsMgr, setNeedsMgr] = useState<NeedsManagerResponse | null>(null);
  const [selectedManager, setSelectedManager] = useState("");
  const [managerError, setManagerError] = useState<string | null>(null);
  const [autoAssigning, setAutoAssigning] = useState(false);
  const [autoAssignMsg, setAutoAssignMsg] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<(DocumentMeta & { preview: Record<string, unknown>[] }) | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const [docs, mgrs, nm] = await Promise.all([
        api.listDocuments().catch(() => []),
        api.listManagers().catch(() => []),
        api.needsManager().catch(() => null),
      ]);
      setDocuments(docs);
      setManagers(mgrs);
      setNeedsMgr(nm);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setManagerError(null);
    setUploading(true);
    setUploadMsg(null);

    try {
      const result = await api.uploadDocument(file, selectedManager || undefined);
      const isSelfTagging = SELF_TAGGING_TYPES.includes(result.report_type);
      const noManager = !selectedManager;

      const mgrNote = selectedManager ? ` → ${selectedManager}` : "";

      const k = result.knowledge;
      const parts = [
        `${result.filename}: ${result.row_count} rows`,
        result.report_type.replace(/_/g, " "),
        `${k.entities_extracted} entities extracted`,
      ];
      if (k.rows_rejected > 0) {
        parts.push(`${k.rows_rejected} rows rejected`);
      }
      if (k.rows_skipped > 0) {
        parts.push(`${k.rows_skipped} rows skipped`);
      }
      setUploadMsg(parts.join(" · ") + mgrNote);

      // Auto-assign only makes sense for self-tagging report types (those
      // with a Tags column) when no manager was explicitly selected.
      if (noManager && isSelfTagging) {
        setUploadMsg((prev) => (prev ?? "") + " · auto-assigning from tags…");
        try {
          const assigned = await api.autoAssign();
          setUploadMsg((prev) =>
            (prev ?? "") + ` ${assigned.assigned} assigned.`
          );
        } catch {
          // non-fatal — user can retry via the banner
        }
      }

      await load();
    } catch (err) {
      setUploadMsg(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleAutoAssign = async () => {
    setAutoAssigning(true);
    setAutoAssignMsg(null);
    try {
      const result = await api.autoAssign();
      setAutoAssignMsg(result.message);
      await load();
    } catch (err) {
      setAutoAssignMsg(err instanceof Error ? err.message : "Auto-assign failed");
    } finally {
      setAutoAssigning(false);
    }
  };

  const selectDoc = async (id: string) => {
    setSelected(id);
    try {
      const [d, r] = await Promise.all([api.getDocument(id), api.queryRows(id, 100)]);
      setDetail(d);
      setRows(r.rows);
    } catch {
      setDetail(null);
      setRows([]);
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteDocument(id);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    if (selected === id) {
      setSelected(null);
      setDetail(null);
      setRows([]);
    }
  };

  const hasUnassigned = needsMgr && needsMgr.total > 0;

  return (
    <div className="h-full flex">
      {/* Sidebar */}
      <div className="w-72 shrink-0 border-r border-border flex flex-col">
        <div className="p-4 border-b border-border-subtle space-y-3">
          <h1 className="text-sm font-semibold text-fg-secondary">Upload Reports</h1>

          {/* Manager selector — optional */}
          <div>
            <label className="text-[10px] text-fg-faint uppercase tracking-wide font-medium block mb-1">
              Property Manager <span className="text-fg-ghost font-normal normal-case">(optional)</span>
            </label>
            <select
              value={selectedManager}
              onChange={(e) => { setSelectedManager(e.target.value); setManagerError(null); }}
              className={`w-full bg-surface border rounded-lg px-3 py-1.5 text-xs text-fg-secondary focus:outline-none focus:border-fg-faint ${
                managerError ? "border-error/60" : "border-border"
              }`}
            >
              <option value="">Auto-assign from tags…</option>
              {managers.map((m) => (
                <option key={m.id} value={m.name}>
                  {m.name}
                </option>
              ))}
            </select>
            {managerError ? (
              <p className="text-[9px] text-error mt-1 leading-relaxed">{managerError}</p>
            ) : (
              <p className="text-[9px] text-fg-ghost mt-1">
                Leave blank to let REMI auto-assign from embedded manager tags
              </p>
            )}
          </div>

          {/* Upload button */}
          <label
            className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border border-dashed border-border cursor-pointer hover:border-fg-faint hover:bg-surface-raised transition-all text-xs text-fg-muted hover:text-fg-secondary ${uploading ? "opacity-50 pointer-events-none" : ""}`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            {uploading ? "Uploading..." : "Upload CSV / Excel"}
            <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={handleUpload} />
          </label>

          {/* Upload result */}
          {uploadMsg && (
            <p className={`text-[10px] leading-relaxed ${uploadMsg.includes("fail") || uploadMsg.includes("error") ? "text-error" : "text-ok"}`}>
              {uploadMsg}
            </p>
          )}

          {/* Auto-assign panel — shown when unassigned properties exist */}
          {hasUnassigned && (
            <div className="rounded-lg border border-warn/30 bg-warn-soft px-3 py-2.5 space-y-2">
              <div>
                <p className="text-[10px] text-warn font-medium">
                  {needsMgr.total} {needsMgr.total === 1 ? "property" : "properties"} unassigned
                </p>
                <p className="text-[9px] text-warn/60 mt-0.5 leading-relaxed">
                  Upload a report with manager tags or select a manager above, then try auto-assign.
                </p>
              </div>

              <button
                onClick={handleAutoAssign}
                disabled={autoAssigning}
                className="w-full px-3 py-1.5 rounded-md bg-warn-soft border border-warn/40 text-[10px] text-warn-fg font-medium hover:bg-warn/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {autoAssigning ? "Assigning…" : "Auto-assign from tags"}
              </button>

              {autoAssignMsg && (
                <p className={`text-[9px] leading-relaxed ${autoAssignMsg.includes("fail") || autoAssignMsg.includes("error") ? "text-error" : "text-ok"}`}>
                  {autoAssignMsg}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          <div className="px-2 py-1.5">
            <p className="text-[10px] text-fg-faint uppercase tracking-wide font-medium">
              Uploaded Documents
            </p>
          </div>

          {loading && <div className="p-4 text-xs text-fg-faint animate-pulse">Loading...</div>}

          {!loading && documents.length === 0 && (
            <Empty title="No documents" description="Upload a CSV or Excel file to get started" />
          )}

          {documents.map((doc) => (
            <div
              key={doc.id}
              role="button"
              tabIndex={0}
              onClick={() => selectDoc(doc.id)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectDoc(doc.id); } }}
              className={`w-full text-left rounded-lg px-3 py-2.5 transition-all group cursor-pointer ${
                selected === doc.id ? "bg-surface-sunken" : "hover:bg-surface-raised"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-xs text-fg-secondary truncate flex-1">{doc.filename}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }}
                  className="opacity-0 group-hover:opacity-100 text-fg-faint hover:text-error transition-all"
                  aria-label={`Delete ${doc.filename}`}
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <p className="text-[10px] text-fg-faint">{doc.row_count} rows</p>
                {doc.report_type && doc.report_type !== "unknown" && (
                  <Badge variant="blue">{doc.report_type.replace(/_/g, " ")}</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main content: data preview */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!detail && (
          <div className="flex-1 flex items-center justify-center">
            <Empty title="Select a document" description="Choose a document to browse its data" />
          </div>
        )}

        {detail && (
          <>
            <div className="shrink-0 px-6 py-4 border-b border-border-subtle">
              <h2 className="text-sm font-bold text-fg">{detail.filename}</h2>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-[10px] text-fg-faint">{detail.row_count} rows</span>
                <div className="flex flex-wrap gap-1">
                  {detail.columns.map((c) => (
                    <Badge key={c} variant="blue">{c}</Badge>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              {rows.length > 0 ? (
                <table className="w-full text-[11px]">
                  <thead className="sticky top-0 bg-surface z-10">
                    <tr>
                      <th className="text-left px-3 py-2 text-fg-faint font-mono border-b border-border-subtle">#</th>
                      {detail.columns.map((c) => (
                        <th key={c} className="text-left px-3 py-2 text-fg-faint font-mono border-b border-border-subtle whitespace-nowrap">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={i} className="hover:bg-surface-raised transition-colors">
                        <td className="px-3 py-1.5 text-fg-ghost border-b border-border-subtle">{i + 1}</td>
                        {detail.columns.map((c) => (
                          <td key={c} className="px-3 py-1.5 text-fg-secondary border-b border-border-subtle max-w-[200px] truncate">
                            {row[c] != null ? String(row[c]) : <span className="text-fg-ghost">&mdash;</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-8 text-center text-xs text-fg-faint">No rows</div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
