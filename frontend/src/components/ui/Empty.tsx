"use client";

export function Empty({
  icon,
  title,
  description,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      {icon && <div className="mb-4 text-fg-ghost">{icon}</div>}
      <h3 className="text-sm font-medium text-fg-muted mb-1">{title}</h3>
      {description && (
        <p className="text-xs text-fg-faint max-w-xs">{description}</p>
      )}
    </div>
  );
}
