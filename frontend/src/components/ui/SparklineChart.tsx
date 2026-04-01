"use client";

import { ResponsiveContainer, AreaChart, Area } from "recharts";

interface Props {
  data: Record<string, unknown>[];
  dataKey: string;
  color: string;
  label: string;
  value: string;
}

export function SparklineChart({ data, dataKey, color, label, value }: Props) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3 min-w-0 flex-1">
      <div className="flex items-baseline justify-between mb-1.5">
        <p className="text-[9px] font-semibold text-fg-faint uppercase tracking-wide">{label}</p>
        <p className="text-sm font-bold text-fg">{value}</p>
      </div>
      <div className="h-10">
        {data.length >= 2 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={color}
                fill={color}
                fillOpacity={0.12}
                strokeWidth={1.5}
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
