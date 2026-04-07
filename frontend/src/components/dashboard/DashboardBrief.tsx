"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { fmt$ } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import type { DashboardOverview } from "@/lib/types";

function getTimeOfDay(): "morning" | "afternoon" | "evening" {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}

function formatDate(): string {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function buildOneLiner(ov: DashboardOverview): { text: string; tone: "good" | "neutral" | "warn" } | null {
  if (ov.total_units === 0) return null;

  const occPct = (ov.occupancy_rate * 100).toFixed(1);
  const vacant = ov.total_units - ov.occupied;
  const flags: string[] = [];

  if (vacant > 3) flags.push(`${vacant} vacancies`);
  if (ov.total_loss_to_lease > 5000) flags.push(`${fmt$(ov.total_loss_to_lease)}/mo in lost rent`);

  if (flags.length === 0) {
    return {
      text: `${occPct}% occupied across ${ov.total_units.toLocaleString()} units. Nothing urgent.`,
      tone: "good",
    };
  }

  if (flags.length === 1) {
    return {
      text: `${occPct}% occupied — but ${flags[0]}.`,
      tone: "warn",
    };
  }

  return {
    text: `${occPct}% occupied. Heads up: ${flags.slice(0, 2).join(" and ")}.`,
    tone: "warn",
  };
}

const TONE_DOT: Record<string, string> = {
  good: "bg-ok",
  neutral: "bg-fg-faint",
  warn: "bg-warn",
};

export function DashboardBrief() {
  const { data, loading } = useApiQuery<DashboardOverview | null>(
    () => api.dashboardOverview().catch(() => null),
    []
  );

  const timeOfDay = getTimeOfDay();
  const brief = data ? buildOneLiner(data) : null;

  return (
    <div className="h-full flex items-center justify-center">
      <div className="max-w-md w-full px-6">
        <div className="w-8 h-0.5 rounded-full bg-accent/30 mb-6" />

        <p className="text-xs text-fg-faint tracking-wide">{formatDate()}</p>

        <h1 className="text-xl font-medium text-fg mt-1 tracking-tight">
          {timeOfDay === "morning" ? "Good morning." : timeOfDay === "afternoon" ? "Good afternoon." : "Good evening."}
        </h1>

        {loading && (
          <div className="mt-5">
            <div className="h-4 w-3/4 bg-surface-sunken rounded animate-pulse" />
          </div>
        )}

        {!loading && brief && (
          <div className="mt-5 flex items-start gap-2.5">
            <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${TONE_DOT[brief.tone]}`} />
            <p className="text-sm text-fg-secondary leading-relaxed">{brief.text}</p>
          </div>
        )}

        {!loading && !brief && (
          <p className="mt-5 text-sm text-fg-faint">No data yet. Upload some reports to get started.</p>
        )}

        <div className="mt-8 flex gap-3">
          <Link
            href="/ask"
            className="text-xs text-accent hover:text-accent-hover transition-colors"
          >
            Ask REMI
          </Link>
          <Link
            href="/"
            className="text-xs text-fg-faint hover:text-fg-secondary transition-colors"
          >
            View dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
