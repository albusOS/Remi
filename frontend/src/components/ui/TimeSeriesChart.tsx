"use client";

import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

export interface SeriesConfig {
  dataKey: string;
  color: string;
  label: string;
  type?: "area" | "line";
}

interface Props {
  data: Record<string, unknown>[];
  series: SeriesConfig[];
  xKey?: string;
  height?: number;
  yDomain?: [number | "auto", number | "auto"];
  yTickFormatter?: (v: number) => string;
  xTickFormatter?: (v: string) => string;
  title?: string;
}

function defaultXFormat(v: string): string {
  try {
    const d = new Date(v);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return v;
  }
}

export function TimeSeriesChart({
  data,
  series,
  xKey = "timestamp",
  height = 200,
  yDomain,
  yTickFormatter,
  xTickFormatter,
  title,
}: Props) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-border bg-surface" style={{ height }}>
        <p className="text-xs text-fg-faint">No data</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      {title && <p className="text-[10px] font-semibold text-fg-muted uppercase tracking-wide mb-3">{title}</p>}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" vertical={false} />
          <XAxis
            dataKey={xKey}
            tickFormatter={xTickFormatter ?? defaultXFormat}
            tick={{ fontSize: 10, fill: "var(--color-fg-faint)" }}
            axisLine={false}
            tickLine={false}
            dy={6}
          />
          <YAxis
            domain={yDomain ?? ["auto", "auto"]}
            tickFormatter={yTickFormatter}
            tick={{ fontSize: 10, fill: "var(--color-fg-faint)" }}
            axisLine={false}
            tickLine={false}
            width={50}
          />
          <Tooltip
            contentStyle={{
              background: "var(--color-surface-raised)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: 11,
              color: "var(--color-fg-secondary)",
            }}
            labelFormatter={xTickFormatter ?? defaultXFormat}
            formatter={(value: number, name: string) => {
              const s = series.find((c) => c.dataKey === name);
              const formatted = yTickFormatter ? yTickFormatter(value) : value.toLocaleString();
              return [formatted, s?.label ?? name];
            }}
          />
          {series.map((s) =>
            s.type === "line" ? (
              <Line
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                name={s.dataKey}
              />
            ) : (
              <Area
                key={s.dataKey}
                type="monotone"
                dataKey={s.dataKey}
                stroke={s.color}
                fill={s.color}
                fillOpacity={0.1}
                strokeWidth={2}
                dot={false}
                name={s.dataKey}
              />
            ),
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
