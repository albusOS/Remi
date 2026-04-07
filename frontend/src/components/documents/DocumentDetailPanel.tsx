import { Badge } from "@/components/ui/Badge";
import { FileIcon, KIND_LABELS, KIND_COLORS, formatBytes, formatDate } from "@/components/documents/DocumentHelpers";
import type { DocumentKind } from "@/lib/types";

type DetailDoc = {
  id: string;
  filename: string;
  kind: DocumentKind;
  report_type: string;
  size_bytes: number;
  uploaded_at: string;
  columns: string[];
  tags: string[];
  preview: Record<string, unknown>[];
};

interface DocumentDetailPanelProps {
  detail: DetailDoc;
  rows: Record<string, unknown>[];
  chunks: { index: number; text: string; page: number | null }[];
  editingTags: boolean;
  editTagValue: string;
  onEditTagValueChange: (value: string) => void;
  onStartEditTags: () => void;
  onSaveTags: () => void;
  onCancelEditTags: () => void;
  onClose: () => void;
}

export function DocumentDetailPanel({
  detail,
  rows,
  chunks,
  editingTags,
  editTagValue,
  onEditTagValueChange,
  onStartEditTags,
  onSaveTags,
  onCancelEditTags,
  onClose,
}: DocumentDetailPanelProps) {
  return (
    <div className="w-full lg:w-[480px] shrink-0 border-t lg:border-t-0 lg:border-l border-border flex flex-col overflow-hidden">
      <div className="shrink-0 px-4 sm:px-5 py-4 border-b border-border-subtle">
        <div className="flex items-center gap-2">
          <button
            onClick={onClose}
            className="lg:hidden shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-fg-muted hover:text-fg hover:bg-surface-sunken transition-colors"
            aria-label="Back to documents"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <FileIcon kind={detail.kind} className="w-4 h-4 text-fg-muted shrink-0" />
          <h2 className="text-sm font-bold text-fg truncate">{detail.filename}</h2>
        </div>
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          <Badge variant={KIND_COLORS[detail.kind]}>{KIND_LABELS[detail.kind]}</Badge>
          {detail.kind === "tabular" && detail.report_type !== "unknown" && (
            <Badge variant="blue">{detail.report_type.replace(/_/g, " ")}</Badge>
          )}
          {detail.size_bytes > 0 && (
            <span className="text-[10px] text-fg-faint">{formatBytes(detail.size_bytes)}</span>
          )}
          <span className="text-[10px] text-fg-faint">{formatDate(detail.uploaded_at)}</span>
        </div>

        <div className="mt-2">
          {editingTags ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={editTagValue}
                onChange={(e) => onEditTagValueChange(e.target.value)}
                placeholder="tag1, tag2, tag3"
                className="flex-1 bg-surface border border-border rounded px-2 py-1 text-[10px] text-fg focus:outline-none focus:border-accent/40"
                onKeyDown={(e) => { if (e.key === "Enter") onSaveTags(); if (e.key === "Escape") onCancelEditTags(); }}
                autoFocus
              />
              <button onClick={onSaveTags} className="text-[10px] text-accent hover:underline">Save</button>
              <button onClick={onCancelEditTags} className="text-[10px] text-fg-faint hover:text-fg-secondary">Cancel</button>
            </div>
          ) : (
            <div className="flex items-center gap-1 flex-wrap">
              {detail.tags.length > 0 ? (
                detail.tags.map((t) => (
                  <span key={t} className="text-[9px] px-1.5 py-0.5 rounded bg-surface-sunken text-fg-faint">{t}</span>
                ))
              ) : (
                <span className="text-[9px] text-fg-ghost">No tags</span>
              )}
              <button
                onClick={onStartEditTags}
                className="text-[9px] text-accent/70 hover:text-accent ml-1"
              >
                edit
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {detail.kind === "tabular" && rows.length > 0 && (
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
        )}

        {detail.kind === "text" && chunks.length > 0 && (
          <div className="p-4 space-y-3">
            {chunks.map((chunk) => (
              <div key={chunk.index} className="rounded-lg border border-border-subtle p-3">
                {chunk.page != null && (
                  <p className="text-[9px] text-fg-ghost uppercase tracking-wide font-medium mb-1.5">
                    Page {chunk.page + 1}
                  </p>
                )}
                <p className="text-xs text-fg-secondary leading-relaxed whitespace-pre-wrap">
                  {chunk.text}
                </p>
              </div>
            ))}
          </div>
        )}

        {detail.kind === "image" && (
          <div className="flex items-center justify-center h-full p-8">
            <div className="text-center">
              <FileIcon kind="image" className="w-12 h-12 text-fg-ghost mx-auto mb-3" />
              <p className="text-xs text-fg-faint">Image preview not available</p>
              <p className="text-[10px] text-fg-ghost mt-1">{detail.filename}</p>
            </div>
          </div>
        )}

        {detail.kind === "tabular" && rows.length === 0 && (
          <div className="p-8 text-center text-xs text-fg-faint">No rows</div>
        )}
        {detail.kind === "text" && chunks.length === 0 && (
          <div className="p-8 text-center text-xs text-fg-faint">No text content extracted</div>
        )}
      </div>

      <div className="shrink-0 px-4 sm:px-5 py-3 border-t border-border-subtle">
        <a
          href={`/ask?q=${encodeURIComponent(`Tell me about the document "${detail.filename}"`)}`}
          className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-lg border border-border text-xs text-fg-muted hover:text-fg-secondary hover:border-fg-faint transition-all"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
          Ask REMI about this document
        </a>
      </div>
    </div>
  );
}
