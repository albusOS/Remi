"use client";

import type { DashboardCard } from "@/lib/types";

const SEVERITY_COLORS: Record<string, string> = {
  info: "border-badge-blue-fg/30 bg-badge-blue",
  warning: "border-warn/30 bg-warn-soft",
  critical: "border-error/30 bg-error-soft",
};

const TREND_ICONS: Record<string, string> = {
  up: "↑",
  down: "↓",
  flat: "→",
};

export function DashboardCardView({ data }: { data: DashboardCard }) {
  const severity = data.severity ?? "info";
  const colorClass = SEVERITY_COLORS[severity] || SEVERITY_COLORS.info;
  const trend = data.trend_direction ? TREND_ICONS[data.trend_direction] : null;

  return (
    <div
      className={`rounded-xl border p-6 ${colorClass} transition-all hover:scale-[1.02]`}
    >
      <p className="text-sm font-medium text-fg-secondary uppercase tracking-wide">
        {data.title}
      </p>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-4xl font-bold text-fg">
          {typeof data.value === "number" ? data.value.toLocaleString() : data.value}
        </span>
        {data.unit && (
          <span className="text-lg text-fg-secondary">{data.unit}</span>
        )}
        {trend && (
          <span
            className={`text-lg font-semibold ${
              data.trend_direction === "up"
                ? "text-ok"
                : data.trend_direction === "down"
                ? "text-error"
                : "text-fg-secondary"
            }`}
          >
            {trend} {data.trend}
          </span>
        )}
      </div>
    </div>
  );
}
