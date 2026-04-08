"use client";

import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from "recharts";
import type { ResearchArtifact as ResearchArtifactType } from "@/lib/types";

// ---------------------------------------------------------------------------
// ResearchArtifact — full-panel render of a researcher __artifact__ payload.
// Shown in the right pane of the split AskView.
// ---------------------------------------------------------------------------

const SEVERITY_STYLES = {
  info: {
    dot: "bg-accent",
    label: "text-fg-muted",
    border: "border-accent/20",
    bg: "bg-accent-soft",
  },
  warn: {
    dot: "bg-warn",
    label: "text-warn-fg",
    border: "border-warn/20",
    bg: "bg-warn-soft",
  },
  critical: {
    dot: "bg-error animate-pulse",
    label: "text-error-fg",
    border: "border-error/20",
    bg: "bg-error-soft",
  },
};

function ArtifactChart({
  chart,
}: {
  chart: ResearchArtifactType["charts"][0];
}) {
  const data = chart.data.map((d) => ({ name: d.label, value: d.value }));
  const tickStyle = { fill: "var(--color-fg-faint)", fontSize: 10 };
  const accentColor = "var(--color-accent)";
  const okColor = "var(--color-ok)";

  return (
    <div className="rounded-xl border border-border bg-surface-raised p-4">
      <p className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest mb-3">
        {chart.title}
      </p>
      <ResponsiveContainer width="100%" height={160}>
        {chart.kind === "line" ? (
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
            <XAxis dataKey="name" tick={tickStyle} axisLine={false} tickLine={false} />
            <YAxis tick={tickStyle} axisLine={false} tickLine={false} width={36} />
            <Tooltip
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                fontSize: 11,
                color: "var(--color-fg)",
              }}
              cursor={{ stroke: "var(--color-border)" }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={accentColor}
              strokeWidth={1.5}
              dot={{ fill: accentColor, r: 3 }}
              activeDot={{ r: 5, fill: accentColor }}
            />
          </LineChart>
        ) : (
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" vertical={false} />
            <XAxis dataKey="name" tick={tickStyle} axisLine={false} tickLine={false} />
            <YAxis tick={tickStyle} axisLine={false} tickLine={false} width={36} />
            <Tooltip
              contentStyle={{
                background: "var(--color-surface-raised)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                fontSize: 11,
                color: "var(--color-fg)",
              }}
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
            />
            <Bar dataKey="value" fill={okColor} radius={[3, 3, 0, 0]} maxBarSize={32} />
          </BarChart>
        )}
      </ResponsiveContainer>
      {(chart.x_label || chart.y_label) && (
        <p className="text-[9px] text-fg-ghost mt-1 text-center">
          {chart.x_label}{chart.x_label && chart.y_label ? " · " : ""}{chart.y_label}
        </p>
      )}
    </div>
  );
}

export function ResearchArtifact({
  artifact,
  onClose,
}: {
  artifact: ResearchArtifactType;
  onClose?: () => void;
}) {
  const [tab, setTab] = useState<"findings" | "charts" | "recs">("findings");

  const hasCharts = artifact.charts.length > 0;
  const hasFindings = artifact.findings.length > 0;
  const hasRecs = artifact.recommendations.length > 0;

  return (
    <div className="h-full flex flex-col bg-surface artifact-panel mesh-bg">
      {/* Header */}
      <div className="shrink-0 px-5 pt-5 pb-3 border-b border-border-subtle panel-glow">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[9px] font-semibold text-accent uppercase tracking-widest">Research Report</span>
            </div>
            <h2 className="text-sm font-semibold text-fg leading-snug truncate">{artifact.title}</h2>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="shrink-0 p-1.5 rounded-lg text-fg-faint hover:text-fg hover:bg-surface-raised transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Summary bullets */}
        {artifact.summary.length > 0 && (
          <ul className="mt-3 space-y-1">
            {artifact.summary.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-[11px] text-fg-secondary leading-relaxed">
                <span className="w-1 h-1 rounded-full bg-accent mt-1.5 shrink-0" />
                {s}
              </li>
            ))}
          </ul>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mt-4">
          {hasFindings && (
            <button
              onClick={() => setTab("findings")}
              className={`px-3 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                tab === "findings"
                  ? "bg-accent-soft text-accent border border-accent/20"
                  : "text-fg-muted hover:text-fg border border-transparent"
              }`}
            >
              Findings
            </button>
          )}
          {hasCharts && (
            <button
              onClick={() => setTab("charts")}
              className={`px-3 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                tab === "charts"
                  ? "bg-accent-soft text-accent border border-accent/20"
                  : "text-fg-muted hover:text-fg border border-transparent"
              }`}
            >
              Charts
            </button>
          )}
          {hasRecs && (
            <button
              onClick={() => setTab("recs")}
              className={`px-3 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                tab === "recs"
                  ? "bg-accent-soft text-accent border border-accent/20"
                  : "text-fg-muted hover:text-fg border border-transparent"
              }`}
            >
              Actions
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
        {tab === "findings" && hasFindings && (
          <div className="stagger space-y-2">
            {artifact.findings.map((f, i) => {
              const s = SEVERITY_STYLES[f.severity] ?? SEVERITY_STYLES.info;
              return (
                <div
                  key={i}
                  className={`rounded-xl border ${s.border} ${s.bg} px-4 py-3`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${s.dot}`} />
                    <p className={`text-[11px] font-semibold ${s.label}`}>{f.title}</p>
                  </div>
                  <p className="text-[11px] text-fg-secondary leading-relaxed pl-3.5">{f.detail}</p>
                </div>
              );
            })}
          </div>
        )}

        {tab === "charts" && hasCharts && (
          <div className="space-y-3">
            {artifact.charts.map((chart, i) => (
              <ArtifactChart key={i} chart={chart} />
            ))}
          </div>
        )}

        {tab === "recs" && hasRecs && (
          <div className="stagger space-y-2">
            {artifact.recommendations.map((r, i) => (
              <div
                key={i}
                className="rounded-xl border border-border bg-surface-raised px-4 py-3 flex items-start gap-3"
              >
                <span className="text-[10px] font-mono text-fg-faint mt-0.5 w-4 shrink-0">{i + 1}.</span>
                <p className="text-[11px] text-fg-secondary leading-relaxed">{r}</p>
              </div>
            ))}
          </div>
        )}

        {tab === "findings" && !hasFindings && (
          <p className="text-[11px] text-fg-faint text-center py-8">No findings in this report.</p>
        )}
      </div>
    </div>
  );
}
