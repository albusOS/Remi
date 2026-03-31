"use client";

import type { ModuleOutput } from "@/lib/types";
import { DashboardCardView } from "./DashboardCardView";
import { TableViewComponent } from "./TableViewComponent";
import { ProfileViewComponent } from "./ProfileViewComponent";
import { LLMResponseView } from "./LLMResponseView";
import { RawOutputView } from "./RawOutputView";

export function ContractRenderer({ module }: { module: ModuleOutput }) {
  const { output, contract } = module;

  if (!output || module.status !== "completed") {
    return <ModuleStatusBadge module={module} />;
  }

  switch (contract) {
    case "dashboard_card":
      return <DashboardCardView data={output as never} />;
    case "table_view":
      return <TableViewComponent data={output as never} />;
    case "profile_view":
      return <ProfileViewComponent data={output as never} />;
    case "llm_response":
      return <LLMResponseView data={output} />;
    case "list[record]":
      return (
        <TableViewComponent
          data={{
            title: module.module_id,
            columns: [],
            rows: (output as Record<string, unknown>[]) ?? [],
            total_count: Array.isArray(output) ? output.length : 0,
            page: 1,
            page_size: 50,
          }}
        />
      );
    default:
      return <RawOutputView data={output} contract={contract} />;
  }
}

function ModuleStatusBadge({ module }: { module: ModuleOutput }) {
  const colors: Record<string, string> = {
    pending: "bg-surface-sunken text-fg-secondary",
    running: "bg-badge-blue text-badge-blue-fg animate-pulse",
    completed: "bg-badge-emerald text-badge-emerald-fg",
    failed: "bg-badge-red text-badge-red-fg",
    skipped: "bg-surface-sunken text-fg-muted",
  };

  return (
    <div className="rounded-xl border border-border p-4 flex items-center gap-3">
      <div
        className={`px-2.5 py-1 rounded-full text-xs font-medium ${
          colors[module.status] || colors.pending
        }`}
      >
        {module.status}
      </div>
      <span className="text-sm text-fg-secondary font-mono">{module.module_id}</span>
    </div>
  );
}
