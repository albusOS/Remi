"use client";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  trend?: "up" | "down" | "flat";
  alert?: boolean;
}

export function MetricCard({ label, value, sub, trend, alert }: Props) {
  return (
    <div
      className={`rounded-xl border px-5 py-4 ${
        alert
          ? "border-warn/30 bg-warn-soft"
          : "border-border bg-surface"
      }`}
    >
      <p className="text-[11px] font-medium text-fg-muted uppercase tracking-wide mb-1">
        {label}
      </p>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-fg">
          {typeof value === "number" ? value.toLocaleString() : value}
        </span>
        {trend && (
          <span
            className={`text-xs font-semibold ${
              trend === "up"
                ? "text-ok"
                : trend === "down"
                ? "text-error"
                : "text-fg-muted"
            }`}
          >
            {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"}
          </span>
        )}
      </div>
      {sub && <p className="text-[11px] text-fg-faint mt-1">{sub}</p>}
    </div>
  );
}
