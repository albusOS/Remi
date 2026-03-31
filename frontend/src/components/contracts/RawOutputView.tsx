"use client";

export function RawOutputView({
  data,
  contract,
}: {
  data: unknown;
  contract: string | null;
}) {
  const text =
    typeof data === "string" ? data : JSON.stringify(data, null, 2);

  return (
    <div className="rounded-xl border border-border p-6 bg-surface-raised">
      {contract && (
        <span className="inline-block px-2 py-0.5 text-xs font-mono rounded bg-surface-sunken text-fg-secondary mb-3">
          {contract}
        </span>
      )}
      <pre className="text-sm text-fg-secondary whitespace-pre-wrap overflow-x-auto font-mono">
        {text}
      </pre>
    </div>
  );
}
