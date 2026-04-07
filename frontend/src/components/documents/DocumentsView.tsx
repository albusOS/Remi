"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Empty } from "@/components/ui/Empty";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { UploadPanel } from "@/components/documents/UploadPanel";
import { DocumentDetailPanel } from "@/components/documents/DocumentDetailPanel";
import { SignalsPanel } from "@/components/documents/SignalsPanel";
import { ActivityPanel } from "@/components/documents/ActivityPanel";
import { FileIcon, KIND_LABELS, KIND_COLORS, formatBytes, formatDate } from "@/components/documents/DocumentHelpers";
import { useFileUpload } from "@/hooks/useFileUpload";
import type { DocumentMeta, DocumentKind, ManagerListItem, SignalSummary } from "@/lib/types";

type DetailDoc = DocumentMeta & { preview: Record<string, unknown>[] };

type Tab = "documents" | "signals" | "activity";

export function DocumentsView() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);
  const [managers, setManagers] = useState<ManagerListItem[]>([]);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<string>("");
  const [tagFilter, setTagFilter] = useState<string>("");
  const [selectedManager, setSelectedManager] = useState("");

  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<DetailDoc | null>(null);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [chunks, setChunks] = useState<{ index: number; text: string; page: number | null }[]>([]);

  const [loading, setLoading] = useState(true);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [showUpload, setShowUpload] = useState(false);

  const [activeTab, setActiveTab] = useState<Tab>("documents");
  const [signals, setSignals] = useState<SignalSummary[]>([]);
  const [signalsLoading, setSignalsLoading] = useState(false);
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  const [editingTags, setEditingTags] = useState(false);
  const [editTagValue, setEditTagValue] = useState("");

  const [loadError, setLoadError] = useState<Error | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [docs, mgrs, tags] = await Promise.all([
        api.listDocuments({
          q: searchQuery || undefined,
          kind: kindFilter || undefined,
          tags: tagFilter || undefined,
        }),
        api.listManagers().catch(() => []),
        api.listDocumentTags().catch(() => []),
      ]);
      setDocuments(docs);
      setManagers(mgrs);
      setAllTags(tags);
    } catch (err) {
      setLoadError(err instanceof Error ? err : new Error("Failed to load documents"));
    } finally {
      setLoading(false);
    }
  }, [searchQuery, kindFilter, tagFilter]);

  useEffect(() => {
    setLoading(true);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(), 200);
    return () => clearTimeout(debounceRef.current);
  }, [load]);

  const upload = useFileUpload({
    manager: selectedManager || undefined,
    onAllComplete: load,
  });

  useEffect(() => {
    if (activeTab === "signals" && signals.length === 0) {
      setSignalsLoading(true);
      api.listSignals().then((r) => setSignals(r.signals)).catch(() => {}).finally(() => setSignalsLoading(false));
    }
    if (activeTab === "activity" && events.length === 0) {
      setEventsLoading(true);
      api.listEvents(30).then((r) => setEvents(r.changesets as unknown as Array<Record<string, unknown>>)).catch(() => {}).finally(() => setEventsLoading(false));
    }
  }, [activeTab, signals.length, events.length]);

  const selectDoc = async (id: string) => {
    setSelected(id);
    setRows([]);
    setChunks([]);
    setEditingTags(false);
    try {
      const d = await api.getDocument(id);
      setDetail(d);
      if (d.kind === "tabular") {
        const r = await api.queryRows(id, 100);
        setRows(r.rows);
      } else if (d.kind === "text") {
        const c = await api.queryChunks(id, 100);
        setChunks(c.chunks);
      }
    } catch {
      setDetail(null);
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteDocument(id);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    if (selected === id) {
      setSelected(null);
      setDetail(null);
      setRows([]);
      setChunks([]);
    }
  };

  const handleSaveTags = async () => {
    if (!detail) return;
    const newTags = editTagValue.split(",").map((t) => t.trim()).filter(Boolean);
    try {
      await api.updateDocumentTags(detail.id, newTags);
      setDetail({ ...detail, tags: newTags });
      setDocuments((prev) => prev.map((d) => d.id === detail.id ? { ...d, tags: newTags } : d));
      setEditingTags(false);
      const freshTags = await api.listDocumentTags().catch(() => []);
      setAllTags(freshTags);
    } catch (err) {
      console.warn("Failed to update tags:", err);
    }
  };

  const closeDetail = () => {
    setSelected(null);
    setDetail(null);
    setRows([]);
    setChunks([]);
  };

  const kindCounts = documents.reduce<Record<string, number>>((acc, d) => {
    acc[d.kind] = (acc[d.kind] || 0) + 1;
    return acc;
  }, {});

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "documents", label: "Documents", count: documents.length },
    { key: "signals", label: "Signals", count: signals.length },
    { key: "activity", label: "Activity" },
  ];

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="shrink-0 border-b border-border-subtle px-4 sm:px-6 py-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold text-fg tracking-tight">Knowledge Base</h1>
            <p className="text-[11px] text-fg-faint mt-0.5">
              Documents, signals, and activity across your portfolio
            </p>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <select
              value={selectedManager}
              onChange={(e) => setSelectedManager(e.target.value)}
              className="bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-fg-secondary focus:outline-none focus:border-fg-faint min-w-0"
            >
              <option value="">All managers</option>
              {managers.map((m) => (
                <option key={m.id} value={m.name}>{m.name}</option>
              ))}
            </select>

            <button
              onClick={() => setShowUpload((v) => !v)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-accent-fg text-xs font-medium hover:opacity-90 transition-opacity shrink-0"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              <span className="hidden sm:inline">Upload</span>
              {upload.processing && (
                <span className="w-3 h-3 rounded-full border-2 border-accent-fg border-t-transparent animate-spin" />
              )}
            </button>
          </div>
        </div>

        {showUpload && (
          <UploadPanel
            entries={upload.entries}
            processing={upload.processing}
            onFiles={upload.addFiles}
            onClear={upload.clear}
            managers={managers}
            selectedManagerId={selectedManager}
            onManagerChange={setSelectedManager}
          />
        )}

        <div className="flex items-center gap-1 border-b border-border-subtle -mb-3 -mx-4 sm:-mx-6 px-4 sm:px-6 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-2 text-xs font-medium border-b-2 transition-all -mb-px ${
                activeTab === tab.key
                  ? "border-accent text-fg"
                  : "border-transparent text-fg-muted hover:text-fg-secondary"
              }`}
            >
              {tab.label}
              {tab.count != null && tab.count > 0 && (
                <span className="ml-1.5 text-[10px] opacity-60">({tab.count})</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {loadError && (
        <div className="px-4 sm:px-6 pt-3">
          <ErrorBanner error={loadError} onRetry={load} />
        </div>
      )}

      {activeTab === "documents" && (
        <>
          <div className="shrink-0 px-4 sm:px-6 py-3 flex flex-wrap items-center gap-2 border-b border-border-subtle">
            <div className="relative flex-1 min-w-[180px] max-w-md">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-fg-ghost" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search documents..."
                className="w-full bg-surface border border-border rounded-lg pl-9 pr-3 py-1.5 text-xs text-fg placeholder-fg-ghost focus:outline-none focus:border-accent/40 transition-all"
              />
            </div>

            <div className="flex items-center gap-1">
              {(["", "tabular", "text", "image"] as const).map((k) => {
                const label = k === "" ? "All" : KIND_LABELS[k];
                const count = k === "" ? documents.length : (kindCounts[k] || 0);
                const active = kindFilter === k;
                return (
                  <button
                    key={k}
                    onClick={() => setKindFilter(k)}
                    className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-all ${
                      active
                        ? "bg-accent text-accent-fg"
                        : "bg-surface-raised text-fg-muted hover:text-fg-secondary"
                    }`}
                  >
                    {label} {count > 0 && <span className="opacity-60">({count})</span>}
                  </button>
                );
              })}
            </div>

            {allTags.length > 0 && (
              <select
                value={tagFilter}
                onChange={(e) => setTagFilter(e.target.value)}
                className="bg-surface border border-border rounded-lg px-2 py-1.5 text-[10px] text-fg-secondary focus:outline-none"
              >
                <option value="">All tags</option>
                {allTags.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            )}
          </div>

          <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
            <div className={`flex-1 overflow-y-auto p-4 ${detail ? "hidden lg:block" : ""}`}>
              {loading && <div className="p-8 text-center text-xs text-fg-faint animate-pulse">Loading...</div>}

              {!loading && documents.length === 0 && (
                <div className="flex items-center justify-center h-full">
                  <Empty
                    title="No documents"
                    description="Upload CSV, Excel, PDF, Word, or text files to build your knowledge base"
                  />
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => selectDoc(doc.id)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectDoc(doc.id); } }}
                    className={`rounded-xl border p-4 transition-all cursor-pointer group ${
                      selected === doc.id
                        ? "border-accent/40 bg-accent/5"
                        : "border-border hover:border-fg-faint hover:bg-surface-raised"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 text-fg-faint">
                        <FileIcon kind={doc.kind} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-fg truncate">{doc.filename}</p>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }}
                            className="opacity-0 group-hover:opacity-100 text-fg-faint hover:text-error transition-all shrink-0"
                            aria-label={`Delete ${doc.filename}`}
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                          <Badge variant={KIND_COLORS[doc.kind]}>{KIND_LABELS[doc.kind]}</Badge>
                          {doc.kind === "tabular" && doc.report_type && doc.report_type !== "unknown" && (
                            <Badge variant="blue">{doc.report_type.replace(/_/g, " ")}</Badge>
                          )}
                          {doc.tags.map((t) => (
                            <span key={t} className="text-[9px] px-1.5 py-0.5 rounded bg-surface-sunken text-fg-faint">{t}</span>
                          ))}
                        </div>
                        <div className="flex items-center gap-3 mt-2 text-[10px] text-fg-faint">
                          {doc.kind === "tabular" && <span>{doc.row_count} rows</span>}
                          {doc.kind === "text" && (
                            <>
                              {doc.page_count > 0 && <span>{doc.page_count} pages</span>}
                              <span>{doc.chunk_count} passages</span>
                            </>
                          )}
                          {doc.size_bytes > 0 && <span>{formatBytes(doc.size_bytes)}</span>}
                          <span>{formatDate(doc.uploaded_at)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {detail && (
              <DocumentDetailPanel
                detail={detail}
                rows={rows}
                chunks={chunks}
                editingTags={editingTags}
                editTagValue={editTagValue}
                onEditTagValueChange={setEditTagValue}
                onStartEditTags={() => { setEditTagValue(detail.tags.join(", ")); setEditingTags(true); }}
                onSaveTags={handleSaveTags}
                onCancelEditTags={() => setEditingTags(false)}
                onClose={closeDetail}
              />
            )}

            {!detail && !loading && documents.length > 0 && (
              <div className="hidden lg:flex w-[480px] shrink-0 border-l border-border items-center justify-center">
                <Empty title="Select a document" description="Choose a document to view its contents" />
              </div>
            )}
          </div>
        </>
      )}

      {activeTab === "signals" && (
        <SignalsPanel signals={signals} loading={signalsLoading} />
      )}

      {activeTab === "activity" && (
        <ActivityPanel events={events} loading={eventsLoading} />
      )}
    </div>
  );
}
