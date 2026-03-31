"use client";

export function Skeleton({
  className = "",
  width,
  height,
}: {
  className?: string;
  width?: string;
  height?: string;
}) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-border/40 ${className}`}
      style={{ width, height }}
    />
  );
}

export function MessageSkeleton({ align = "left" }: { align?: "left" | "right" }) {
  if (align === "right") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[55%]">
          <div className="rounded-2xl rounded-br-md px-4 py-3 bg-surface-sunken">
            <Skeleton className="h-3 w-44 mb-2" />
            <Skeleton className="h-3 w-28" />
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[70%] space-y-2">
        <Skeleton className="h-3 w-64" />
        <Skeleton className="h-3 w-48" />
        <Skeleton className="h-3 w-56" />
      </div>
    </div>
  );
}

export function ThreadSkeleton() {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        <MessageSkeleton align="right" />
        <MessageSkeleton align="left" />
        <MessageSkeleton align="right" />
        <MessageSkeleton align="left" />
      </div>
    </div>
  );
}
