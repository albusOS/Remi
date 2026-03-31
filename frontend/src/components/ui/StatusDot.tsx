"use client";

const COLORS: Record<string, string> = {
  idle: "var(--color-fg-faint)",
  running: "var(--color-warn)",
  done: "var(--color-ok)",
  completed: "var(--color-ok)",
  error: "var(--color-error)",
  failed: "var(--color-error)",
  pending: "var(--color-fg-muted)",
  skipped: "var(--color-fg-muted)",
  calling: "var(--color-warn)",
  connected: "var(--color-ok)",
  disconnected: "var(--color-error)",
};

export function StatusDot({
  status,
  size = 8,
  pulse = false,
}: {
  status: string;
  size?: number;
  pulse?: boolean;
}) {
  const color = COLORS[status] ?? COLORS.idle;
  const shouldPulse = pulse || status === "running" || status === "calling";

  return (
    <span className="relative inline-flex" style={{ width: size, height: size }}>
      {shouldPulse && (
        <span
          className="absolute inset-0 rounded-full animate-ping opacity-40"
          style={{ backgroundColor: color }}
        />
      )}
      <span
        className="relative inline-flex rounded-full w-full h-full"
        style={{ backgroundColor: color }}
      />
    </span>
  );
}
