"use client";

export function ErrorBanner({
  error,
  onRetry,
}: {
  error: Error | null;
  onRetry?: () => void;
}) {
  if (!error) return null;

  return (
    <div className="rounded-xl border border-error/20 bg-error-soft px-4 py-3 flex items-center gap-3">
      <svg
        className="w-4 h-4 text-error shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
        />
      </svg>
      <p className="text-xs text-error flex-1">{error.message || "Something went wrong"}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-[10px] font-medium text-error hover:underline shrink-0"
        >
          Retry
        </button>
      )}
    </div>
  );
}
