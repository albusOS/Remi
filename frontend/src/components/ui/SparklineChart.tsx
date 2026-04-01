"use client";

import { useMemo } from "react";
import { ResponsiveContainer, AreaChart, Area, Tooltip } from "recharts";

interface Props {
  data: Record<string, unknown>[];
  dataKey: string;
  color: string;
  label: string;
  /** Current value — displayed large */
  value: string;
  /** Format the tooltip value */
  valueFormatter?: (v: number) => string;
  /** When lower is better (e.g. delinquency), flip the trend logic */
  invertTrend?: boolean;
}

function defaultFormat(v: number): string {
  return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

export function SparklineChart({
  data,
  dataKey,
  color,
  label,
  value,
  valueFormatter,
  invertTrend = false,
}: Props) {
  const fmt = valueFormatter ?? defaultFormat;

  const trend = useMemo(() => {
    if (data.length < 2) return { direction: "flat" as const, delta: 0, pct: 0 };
    const first = Number(data[0][dataKey]) || 0;
    const last = Number(data[data.length - 1][dataKey]) || 0;
    const delta = last - first;
    const pct = first !== 0 ? (delta / first) * 100 : 0;
    const raw = delta > 0.001 ? "up" : delta < -0.001 ? "down" : "flat";
    const direction = invertTrend
      ? raw === "up" ? "down" : raw === "down" ? "up" : "flat"
      : raw;
    return { direction: direction as "up" | "down" | "flat", delta, pct };
  }, [data, dataKey, invertTrend]);

  const trendColor =
    trend.direction === "up"
      ? "var(--color-ok)"
      : trend.direction === "down"
      ? "var(--color-error)"
      : "var(--color-fg-ghost)";

  const trendArrow =
    trend.direction === "up" ? "↑" : trend.direction === "down" ? "↓" : "→";

  const gradientId = `spark-${dataKey}`;

  return (
    <div className="rounded-2xl border border-border bg-surface p-4 min-w-0 flex-1 group hover:border-border/80 transition-all">
      {/* Top row: label + trend badge */}
      <div className="flex items-center justify-between mb-1">
        <p className="text-[10px] font-semibold text-fg-faint uppercase tracking-wide">
          {label}
        </p>
        {trend.direction !== "flat" && (
          <span
            className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
            style={{
              color: trendColor,
              background:
                trend.direction === "up"
                  ? "var(--color-ok-soft)"
                  : "var(--color-error-soft)",
            }}
          >
            {trendArrow} {Math.abs(trend.pct).toFixed(0)}%
          </span>
        )}
      </div>

      {/* Hero value */}
      <p className="text-xl font-bold text-fg tabular-nums mb-2">{value}</p>

      {/* Sparkline */}
      <div style={{ height: 48, minWidth: 0, minHeight: 48 }}>
        {data.length >= 2 ? (
          <ResponsiveContainer width="100%" height={48}>
            <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <Tooltip
                contentStyle={{
                  background: "var(--color-surface-raised)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 10,
                  fontSize: 10,
                  padding: "4px 10px",
                  color: "var(--color-fg-secondary)",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                }}
                labelFormatter={(v) => {
                  try {
                    return new Date(String(v)).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    });
                  } catch {
                    return String(v);
                  }
                }}
                formatter={(v) => [fmt(Number(v) || 0), label]}
                cursor={{ stroke: color, strokeWidth: 1, strokeDasharray: "3 3" }}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                fill={`url(#${gradientId})`}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center">
            <span className="text-[9px] text-fg-ghost">Not enough data</span>
          </div>
        )}
      </div>
    </div>
  );
}
