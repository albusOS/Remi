"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  trend?: "up" | "down" | "flat";
  alert?: boolean;
  loading?: boolean;
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);
  const startValRef = useRef(0);
  const duration = 600;

  useEffect(() => {
    startRef.current = null;
    startValRef.current = display;

    const animate = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const elapsed = ts - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(startValRef.current + (value - startValRef.current) * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return <>{display.toLocaleString()}</>;
}

export function MetricCard({ label, value, sub, trend, alert, loading }: Props) {
  const isNumber = typeof value === "number";
  const displayString = isNumber ? null : String(value);

  return (
    <div
      className={`
        rounded-2xl border min-w-0 overflow-hidden px-4 py-3.5 sm:px-5 sm:py-4
        card-hover relative
        ${alert
          ? "border-warn/25 bg-warn-soft card-alert-glow"
          : "border-border bg-surface-raised"
        }
      `}
    >
      {/* Top-edge accent glow on alert */}
      {alert && (
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-warn/50 to-transparent" />
      )}

      <p className="text-[10px] sm:text-[11px] font-semibold text-fg-muted uppercase tracking-widest mb-1.5 truncate">
        {label}
      </p>

      <div className="flex items-baseline gap-1.5 min-w-0">
        {loading ? (
          <span className="text-lg sm:text-2xl font-bold text-fg-ghost number-shimmer tracking-tight">—</span>
        ) : (
          <span className="text-lg sm:text-2xl font-bold tracking-tight truncate number-reveal font-mono"
            style={{ color: alert ? "var(--color-warn-fg)" : "var(--color-fg)" }}
          >
            {isNumber ? <AnimatedNumber value={value as number} /> : displayString}
          </span>
        )}
        {trend && !loading && (
          <span
            className={`text-xs font-semibold shrink-0 ${
              trend === "up" ? "text-ok" : trend === "down" ? "text-error" : "text-fg-muted"
            }`}
          >
            {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"}
          </span>
        )}
      </div>

      {sub && !loading && (
        <p className="text-[10px] sm:text-[11px] text-fg-faint mt-0.5 truncate">{sub}</p>
      )}
      {loading && (
        <p className="text-[10px] sm:text-[11px] text-fg-ghost mt-0.5 number-shimmer">—</p>
      )}
    </div>
  );
}
