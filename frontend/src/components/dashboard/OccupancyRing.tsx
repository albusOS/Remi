import { pct } from "@/lib/format";

export function OccupancyRing({ rate, size = 140 }: { rate: number; size?: number }) {
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = circumference * rate;
  const color = rate >= 0.95 ? "stroke-ok" : rate >= 0.9 ? "stroke-warn" : "stroke-error";

  return (
    <div className="relative ring-pulse" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="currentColor" strokeWidth={stroke}
          className="text-border-subtle"
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference - filled}`}
          className={`${color} transition-all duration-1000`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-fg tracking-tight">{pct(rate)}</span>
        <span className="text-[9px] text-fg-faint uppercase tracking-widest">occupied</span>
      </div>
    </div>
  );
}
