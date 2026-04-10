"use client";

interface SupportingStat {
  label: string;
  value: string;
  alert?: boolean;
}

interface Props {
  label: string;
  value: string;
  color?: string;
  sub?: string;
  supporting?: SupportingStat[];
  className?: string;
}

export function StatHero({ label, value, color, sub, supporting, className = "" }: Props) {
  return (
    <div className={`rounded-2xl border border-border bg-surface p-6 ${className}`}>
      <p className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest mb-2">
        {label}
      </p>
      <p
        className="text-4xl font-bold tracking-tight font-mono leading-none"
        style={{ color: color ?? "var(--color-fg)" }}
      >
        {value}
      </p>
      {sub && <p className="text-[11px] text-fg-faint mt-1.5">{sub}</p>}
      {supporting && supporting.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border-subtle flex flex-wrap gap-x-6 gap-y-3">
          {supporting.map((s) => (
            <div key={s.label}>
              <p className="text-[9px] text-fg-faint uppercase tracking-wider mb-0.5">
                {s.label}
              </p>
              <p
                className={`text-sm font-semibold font-mono ${
                  s.alert ? "text-warn-fg" : "text-fg-secondary"
                }`}
              >
                {s.value}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
