import Link from "next/link";

export function AlertChip({
  href, count, label, sub, color, pulse,
}: {
  href: string; count: number; label: string; sub?: string;
  color: "error" | "warn" | "orange" | "sky" | "violet"; pulse?: boolean;
}) {
  const colors = {
    error: "border-error/20 bg-error-soft text-error hover:border-error/40 hover:shadow-[0_0_20px_-4px_rgba(201,92,92,0.15)]",
    warn: "border-warn/20 bg-warn-soft text-warn hover:border-warn/40 hover:shadow-[0_0_20px_-4px_rgba(212,151,78,0.15)]",
    orange: "border-orange-500/20 bg-orange-500/5 text-orange-400 hover:border-orange-500/40 hover:shadow-[0_0_20px_-4px_rgba(249,115,22,0.15)]",
    sky: "border-sky-500/20 bg-sky-500/5 text-sky-400 hover:border-sky-500/40 hover:shadow-[0_0_20px_-4px_rgba(14,165,233,0.15)]",
    violet: "border-violet-500/20 bg-violet-500/5 text-violet-400 hover:border-violet-500/40 hover:shadow-[0_0_20px_-4px_rgba(139,92,246,0.15)]",
  };

  return (
    <Link
      href={href}
      className={`flex-1 sm:flex-initial shrink-0 min-w-[140px] rounded-2xl border px-5 py-3.5 transition-all group card-hover ${colors[color]}`}
    >
      <div className="flex items-center gap-2">
        {pulse && (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-current" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-current" />
          </span>
        )}
        <span className="text-2xl font-bold leading-none tracking-tight">{count}</span>
      </div>
      <p className="text-[11px] opacity-80 mt-1 font-medium">{label}</p>
      {sub && <p className="text-[9px] opacity-50">{sub}</p>}
    </Link>
  );
}
