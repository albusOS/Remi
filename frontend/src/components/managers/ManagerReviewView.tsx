"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageContainer } from "@/components/ui/PageContainer";

function AskRemiButton({ managerName }: { managerName: string }) {
  const router = useRouter();
  return (
    <button
      onClick={() => router.push(`/?q=${encodeURIComponent(`Give me a full briefing on ${managerName}`)}`)}
      className="flex items-center gap-1.5 rounded-lg border border-accent/20 bg-accent-soft px-2.5 py-1 text-[11px] font-medium text-accent hover:bg-accent/15 hover:border-accent/40 transition-all"
      title={`Ask REMI about ${managerName}`}
    >
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
      </svg>
      Ask REMI
    </button>
  );
}
import { OverviewTab } from "./OverviewTab";
import { TrendsTab } from "./TrendsTab";
import { DelinquencyTab } from "./DelinquencyTab";
import { ManagerLeasesTab } from "./ManagerLeasesTab";
import { VacanciesTab } from "./VacanciesTab";
import { MaintenanceTab } from "./MaintenanceTab";
import { ReviewPrepTab } from "./ReviewPrepTab";
import type {
  ManagerReview,
  DelinquencyBoard,
  LeaseCalendar,
  VacancyTracker,
} from "@/lib/types";

type Tab = "overview" | "trends" | "delinquency" | "leases" | "vacancies" | "maintenance" | "review";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "trends", label: "Trends" },
  { key: "delinquency", label: "Delinquency" },
  { key: "leases", label: "Leases" },
  { key: "vacancies", label: "Vacancies" },
  { key: "maintenance", label: "Maintenance" },
  { key: "review", label: "Meeting Prep" },
];

export function ManagerReviewView({ managerId }: { managerId: string }) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("overview");

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editCompany, setEditCompany] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data, loading, refetch } = useApiQuery(async () => {
    const [review, delinquency, leases, vacancies] = await Promise.all([
      api.getManagerReview(managerId).catch(() => null),
      api.delinquencyBoard({ manager_id: managerId }).catch(() => null),
      api.leasesExpiring(90, { manager_id: managerId }).catch(() => null),
      api.vacancyTracker({ manager_id: managerId }).catch(() => null),
    ]);

    return {
      review: review as ManagerReview | null,
      delinquency: delinquency as DelinquencyBoard | null,
      leases: leases as LeaseCalendar | null,
      vacancies: vacancies as VacancyTracker | null,
    };
  }, [managerId]);

  const review = data?.review ?? null;
  const delinquency = data?.delinquency ?? null;
  const leases = data?.leases ?? null;
  const vacancies = data?.vacancies ?? null;

  function startEdit() {
    if (!review) return;
    setEditName(review.name);
    setEditEmail(review.email || "");
    setEditCompany(review.company || "");
    setEditing(true);
  }

  async function saveEdit() {
    setEditSaving(true);
    try {
      await api.updateManager(managerId, {
        name: editName.trim(),
        email: editEmail.trim() || undefined,
        company: editCompany.trim() || undefined,
      });
      setEditing(false);
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update manager");
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.deleteManager(managerId);
      router.push("/managers");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete manager");
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-fg-faint animate-pulse">Loading...</div>
      </div>
    );
  }

  if (!review) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-fg-muted">Manager not found</div>
      </div>
    );
  }

  const delCount = delinquency?.total_delinquent ?? 0;
  const leaseCount = leases?.total_expiring ?? 0;
  const vacCount = (vacancies?.total_vacant ?? 0) + (vacancies?.total_notice ?? 0);
  const maintCount = review.metrics.open_maintenance;

  return (
    <PageContainer wide>
      <div>
        <Link href="/managers" className="text-xs text-fg-faint hover:text-fg-secondary transition-colors">
          &larr; All Managers
        </Link>

        {editing ? (
          <div className="mt-2 space-y-2 rounded-lg border border-border bg-surface-raised p-4">
            <div className="grid gap-2 sm:grid-cols-3">
              <input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Name" className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-fg placeholder:text-fg-faint focus:outline-none focus:ring-1 focus:ring-accent" />
              <input value={editEmail} onChange={(e) => setEditEmail(e.target.value)} placeholder="Email" className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-fg placeholder:text-fg-faint focus:outline-none focus:ring-1 focus:ring-accent" />
              <input value={editCompany} onChange={(e) => setEditCompany(e.target.value)} placeholder="Company" className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-fg placeholder:text-fg-faint focus:outline-none focus:ring-1 focus:ring-accent" />
            </div>
            <div className="flex items-center gap-2">
              <button onClick={saveEdit} disabled={editSaving || !editName.trim()} className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-fg disabled:opacity-50">{editSaving ? "Saving..." : "Save"}</button>
              <button onClick={() => setEditing(false)} disabled={editSaving} className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-fg-secondary hover:text-fg disabled:opacity-50">Cancel</button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 mt-2">
            <h1 className="text-xl font-bold text-fg">{review.name}</h1>
            <AskRemiButton managerName={review.name} />
            <button onClick={startEdit} className="rounded-md border border-border px-2 py-1 text-[10px] font-medium text-fg-muted hover:text-fg hover:border-fg-muted transition-colors">Edit</button>
            <button onClick={() => setShowDeleteConfirm(true)} disabled={deleting} className="rounded-xl border border-error/20 px-2.5 py-1 text-[10px] font-medium text-error hover:bg-error-soft transition-all btn-glow btn-glow-danger disabled:opacity-50">{deleting ? "Deleting..." : "Delete"}</button>
          </div>
        )}

        <div className="flex items-center gap-3 mt-1">
          {review.company && <span className="text-xs text-fg-muted">{review.company}</span>}
          <span className="text-xs text-fg-faint">{review.property_count} properties · {review.metrics.total_units} units</span>
        </div>
      </div>

      <div className="flex items-center gap-1 border-b border-border overflow-x-auto scrollbar-none">
        {TABS.map(({ key, label }) => {
          const count = key === "delinquency" ? delCount : key === "leases" ? leaseCount : key === "vacancies" ? vacCount : key === "maintenance" ? maintCount : 0;
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-3 sm:px-4 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap shrink-0 ${
                tab === key ? "border-accent text-fg" : "border-transparent text-fg-muted hover:text-fg-secondary"
              }`}
            >
              {label}
              {count > 0 && key !== "overview" && (
                <span className={`ml-1.5 text-[9px] px-1.5 py-0.5 rounded-full ${
                  key === "delinquency" || key === "vacancies" ? "bg-error-soft text-error" : key === "leases" ? "bg-warn-soft text-warn" : key === "maintenance" ? "bg-sky-500/20 text-sky-400" : "bg-surface-sunken text-fg-faint"
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {tab === "overview" && <OverviewTab review={review} />}
      {tab === "trends" && <TrendsTab managerId={managerId} />}
      {tab === "delinquency" && <DelinquencyTab data={delinquency} />}
      {tab === "leases" && <ManagerLeasesTab data={leases} />}
      {tab === "vacancies" && <VacanciesTab data={vacancies} />}
      {tab === "maintenance" && <MaintenanceTab properties={review.properties} />}
      {tab === "review" && <ReviewPrepTab managerId={managerId} />}

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete Manager"
        description="Delete this manager? All property associations will be unlinked. This action cannot be undone."
        confirmLabel="Delete Manager"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </PageContainer>
  );
}
