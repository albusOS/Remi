"use client";

const VARIANTS: Record<string, string> = {
  default: "bg-badge-default text-badge-default-fg",
  blue: "bg-badge-blue text-badge-blue-fg",
  violet: "bg-badge-purple text-badge-purple-fg",
  amber: "bg-badge-amber text-badge-amber-fg",
  emerald: "bg-badge-emerald text-badge-emerald-fg",
  red: "bg-badge-red text-badge-red-fg",
  cyan: "bg-badge-cyan text-badge-cyan-fg",
};

export function Badge({
  children,
  variant = "default",
  className = "",
}: {
  children: React.ReactNode;
  variant?: keyof typeof VARIANTS;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-medium ${VARIANTS[variant] ?? VARIANTS.default} ${className}`}
    >
      {children}
    </span>
  );
}
