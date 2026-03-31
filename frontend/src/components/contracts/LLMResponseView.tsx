"use client";

export function LLMResponseView({ data }: { data: unknown }) {
  const text = typeof data === "string" ? data : JSON.stringify(data, null, 2);

  return (
    <div className="rounded-xl border border-border p-6 bg-surface-raised">
      <div className="flex items-center gap-2 mb-3">
        <div className="h-2 w-2 rounded-full bg-badge-purple-fg" />
        <span className="text-xs font-medium text-badge-purple-fg uppercase tracking-wide">
          Agent Response
        </span>
      </div>
      <div className="prose prose-sm max-w-none">
        <pre className="whitespace-pre-wrap text-fg text-sm leading-relaxed font-sans">
          {text}
        </pre>
      </div>
    </div>
  );
}
