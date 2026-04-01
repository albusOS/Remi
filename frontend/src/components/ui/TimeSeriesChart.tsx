"use client";

import { useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
} from "recharts";

/* ------------------------------------------------------------------ */
/* Public types                                                        */
/* ------------------------------------------------------------------ */

export interface SeriesConfig {
  dataKey: string;
  color: string;
  label: string;
  type?: "area" | "line";
  /** Override fill opacity for area series (default 0.25) */
  fillOpacity?: number;
}

export interface ReferenceLineConfig {
  y: number;
  label?: string;
  color?: string;
  dashed?: boolean;
}

export interface ZoneConfig {
  /** y-axis lower bound */
  y1: number;
  /** y-axis upper bound */
  y2: number;
  color: string;
  opacity?: number;
  label?: string;
}

interface Props {
  data: Record<string, unknown>[];
  series: SeriesConfig[];
  xKey?: string;
  height?: number;
  yDomain?: [number | "auto", number | "auto"];
  yTickFormatter?: (v: number) => string;
  xTickFormatter?: (v: string) => string;
  /** Big headline above the chart */
  title?: string;
  /** Large value displayed next to the title */
  heroValue?: string;
  /** Color for the hero value */
  heroColor?: string;
  /** Short prose summary displayed below the title row */
  summary?: string;
  summaryColor?: string;
  referenceLines?: ReferenceLineConfig[];
  /** Colored horizontal bands that shade regions of the chart */
  zones?: ZoneConfig[];
  /** Use gradient fills derived from series colors */
  gradient?: boolean;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function shortDate(v: string): string {
  try {
    const d = new Date(v);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return v;
  }
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export function TimeSeriesChart({
  data,
  series,
  xKey = "timestamp",
  height = 220,
  yDomain,
  yTickFormatter,
  xTickFormatter,
  title,
  heroValue,
  heroColor,
  summary,
  summaryColor,
  referenceLines,
  zones,
  gradient = true,
}: Props) {
  const gradientDefs = useMemo(
    () =>
      series
        .filter((s) => s.type !== "line")
        .map((s) => ({
          id: `grad-${s.dataKey}`,
          color: s.color,
        })),
    [series],
  );

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-2xl border border-border bg-surface"
        style={{ height: height + 60 }}
      >
        <p className="text-xs text-fg-faint">No data yet</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-surface overflow-hidden">
      {/* Header */}
      {(title || heroValue) && (
        <div className="px-5 pt-4 pb-1">
          <div className="flex items-baseline justify-between gap-3">
            {title && (
              <p className="text-[11px] font-semibold text-fg-muted uppercase tracking-wide">
                {title}
              </p>
            )}
            {heroValue && (
              <p
                className="text-lg font-bold tabular-nums"
                style={{ color: heroColor ?? "var(--color-fg)" }}
              >
                {heroValue}
              </p>
            )}
          </div>
          {summary && (
            <p
              className="text-[11px] mt-0.5 leading-relaxed"
              style={{ color: summaryColor ?? "var(--color-fg-faint)" }}
            >
              {summary}
            </p>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="px-2 pb-3" style={{ minWidth: 0, minHeight: height }}>
        <ResponsiveContainer width="100%" height={height} minWidth={1} minHeight={1}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            {/* Gradient definitions */}
            {gradient && (
              <defs>
                {gradientDefs.map((g) => (
                  <linearGradient key={g.id} id={g.id} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={g.color} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={g.color} stopOpacity={0.02} />
                  </linearGradient>
                ))}
              </defs>
            )}

            {/* Zone shading — colored horizontal bands */}
            {zones?.map((z, i) => (
              <ReferenceArea
                key={`zone-${i}`}
                y1={z.y1}
                y2={z.y2}
                fill={z.color}
                fillOpacity={z.opacity ?? 0.06}
                stroke="none"
                label={
                  z.label
                    ? {
                        value: z.label,
                        position: "insideTopLeft",
                        fill: z.color,
                        fontSize: 9,
                        fontWeight: 600,
                        opacity: 0.7,
                      }
                    : undefined
                }
              />
            ))}

            <XAxis
              dataKey={xKey}
              tickFormatter={xTickFormatter ?? shortDate}
              tick={{ fontSize: 10, fill: "var(--color-fg-ghost)" }}
              axisLine={false}
              tickLine={false}
              dy={6}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={yDomain ?? ["auto", "auto"]}
              tickFormatter={yTickFormatter}
              tick={{ fontSize: 10, fill: "var(--color-fg-ghost)" }}
              axisLine={false}
              tickLine={false}
              width={48}
            />
            <Tooltip
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: 12,
                fontSize: 11,
                padding: "8px 12px",
                color: "var(--color-fg-secondary)",
                boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
              }}
              labelFormatter={(v) => (xTickFormatter ?? shortDate)(String(v))}
              formatter={(value, name) => {
                const n = Number(value) || 0;
                const s = series.find((c) => c.dataKey === name);
                const formatted = yTickFormatter ? yTickFormatter(n) : n.toLocaleString();
                return [formatted, s?.label ?? String(name)];
              }}
              cursor={{ stroke: "var(--color-fg-ghost)", strokeWidth: 1 }}
            />

            {/* Reference lines */}
            {referenceLines?.map((rl, i) => (
              <ReferenceLine
                key={`ref-${i}`}
                y={rl.y}
                stroke={rl.color ?? "var(--color-fg-ghost)"}
                strokeDasharray={rl.dashed !== false ? "6 3" : undefined}
                strokeWidth={1}
                label={
                  rl.label
                    ? {
                        value: rl.label,
                        position: "insideTopRight",
                        fill: rl.color ?? "var(--color-fg-ghost)",
                        fontSize: 9,
                        fontWeight: 600,
                      }
                    : undefined
                }
              />
            ))}

            {/* Data series */}
            {series.map((s) =>
              s.type === "line" ? (
                <Line
                  key={s.dataKey}
                  type="monotone"
                  dataKey={s.dataKey}
                  stroke={s.color}
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={false}
                  name={s.dataKey}
                />
              ) : (
                <Area
                  key={s.dataKey}
                  type="monotone"
                  dataKey={s.dataKey}
                  stroke={s.color}
                  fill={
                    gradient
                      ? `url(#grad-${s.dataKey})`
                      : s.color
                  }
                  fillOpacity={gradient ? 1 : (s.fillOpacity ?? 0.15)}
                  strokeWidth={2}
                  dot={false}
                  name={s.dataKey}
                />
              ),
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
