"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { fmt$, pct } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageContainer } from "@/components/ui/PageContainer";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { StatHero } from "@/components/ui/StatHero";
import { AlertFeed, type AlertItem } from "@/components/ui/AlertFeed";
import { PipelineStrip, type PipelineStage } from "@/components/ui/PipelineStrip";
import { TimelineBuckets, type TimeBucket } from "@/components/ui/TimelineBuckets";
import { TrendsTab } from "./TrendsTab";
import { ReviewPrepTab } from "./ReviewPrepTab";
import { ManagerRentRollTab } from "./ManagerRentRollTab";
import { ManagerLeasesTab } from "./ManagerLeasesTab";
import { PropertyHealthCard, type PropertyHealth } from "@/components/ui/PropertyHealthCard";
import type { ManagerReview, DelinquencyBoard, LeaseCalendar, VacancyTracker } from "@/lib/types";

type Tab = "overview" | "rent_roll" | "leases" | "trends" | "prep";

export function ManagerDetailView({ managerId }: { managerId: string }) {
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
    const scope = { manager_id: managerId };
    const [review, delinquency, leases, vacancies] = await Promise.all([
      api.getManagerReview(managerId).catch(() => null),
      api.delinquencyBoard(scope).catch(() => null),
      api.leasesExpiring(90, scope).catch(() => null),
      api.vacancyTracker(scope).catch(() => null),
    ]);
    return {
      review: review as ManagerReview | null,
      delinquency: delinquency as DelinquencyBoard | null,
      leases: leases as LeaseCalendar | null,
      vacancies: vacancies as VacancyTracker | null,
    };
  }, ["manager_detail", managerId]);

  const review = data?.review ?? null;
  const delinquency = data?.delinquency ?? null;
  const leases = data?.leases ?? null;
  const vacancies = data?.vacancies ?? null;

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
      alert(err instanceof Error ? err.message : "Failed to update");
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
      alert(err instanceof Error ? err.message : "Failed to delete");
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <PageContainer wide>
        <div className="space-y-4">
          <div className="h-8 w-48 rounded-lg bg-surface-raised number-shimmer" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-2xl border border-border bg-surface h-40 number-shimmer" />
            ))}
          </div>
        </div>
      </PageContainer>
    );
  }

  if (!review) {
    return (
      <PageContainer wide>
        <div className="py-16 text-center text-sm text-fg-muted">Manager not found</div>
      </PageContainer>
    );
  }

  const { metrics } = review;

  // Alerts
  const alerts: AlertItem[] = [];
  if (delinquency && delinquency.total_delinquent > 0) {
    alerts.push({ id: "del", label: "Delinquent tenants", sub: fmt$(delinquency.total_balance) + " owed", count: delinquency.total_delinquent, href: "#", severity: "critical", pulse: delinquency.total_delinquent > 3 });
  }
  if (vacancies && vacancies.total_vacant > 0) {
    alerts.push({ id: "vac", label: "Vacant units", sub: fmt$(vacancies.total_market_rent_at_risk) + "/mo at risk", count: vacancies.total_vacant, href: "#", severity: "warn" });
  }
  if (leases && leases.total_expiring > 0) {
    alerts.push({ id: "lse", label: "Leases expiring (90d)", count: leases.total_expiring, href: "#", severity: "info" });
  }

  // Pipeline stages
  const stageCounts: Record<string, { count: number; amount: number }> = {};
  for (const t of delinquency?.tenants ?? []) {
    const s = t.status.toLowerCase();
    const key = s.includes("evict") ? "eviction" : s.includes("filing") ? "filing" : s.includes("demand") ? "demand" : s.includes("notice") ? "notice" : "current";
    if (!stageCounts[key]) stageCounts[key] = { count: 0, amount: 0 };
    stageCounts[key].count++;
    stageCounts[key].amount += t.balance_owed;
  }
  const stages: PipelineStage[] = [
    { id: "current", label: "Current", count: stageCounts["current"]?.count ?? 0, variant: "warn" },
    { id: "notice", label: "Notice", count: stageCounts["notice"]?.count ?? 0, amount: stageCounts["notice"]?.amount, variant: "warn" },
    { id: "demand", label: "Demand", count: stageCounts["demand"]?.count ?? 0, amount: stageCounts["demand"]?.amount, variant: "warn" },
    { id: "filing", label: "Filing", count: stageCounts["filing"]?.count ?? 0, amount: stageCounts["filing"]?.amount, variant: "error" },
    { id: "eviction", label: "Eviction", count: stageCounts["eviction"]?.count ?? 0, amount: stageCounts["eviction"]?.amount, variant: "error" },
  ];

  // Lease timeline
  const leaseBuckets: TimeBucket[] = leases ? [
    { label: "30d", count: leases.leases.filter((l) => !l.is_month_to_month && l.days_left <= 30).length, colorClass: "bg-error" },
    { label: "60d", count: leases.leases.filter((l) => !l.is_month_to_month && l.days_left > 30 && l.days_left <= 60).length, colorClass: "bg-warn" },
    { label: "90d", count: leases.leases.filter((l) => !l.is_month_to_month && l.days_left > 60).length, colorClass: "bg-warn/50" },
    { label: "MTM", count: leases.month_to_month_count, colorClass: "bg-fg-ghost" },
  ] : [];

  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "rent_roll", label: "Rent Roll" },
    { key: "leases", label: "Leases" },
    { key: "trends", label: "Trends" },
    { key: "prep", label: "Meeting Prep" },
  ];

  return (
    <PageContainer wide>
      {/* Header */}
      <div>
        <Link href="/managers" className="text-xs text-fg-faint hover:text-fg-secondary transition-colors">
          ← All Managers
        </Link>

        {editing ? (
          <div className="mt-2 space-y-2 rounded-xl border border-border bg-surface-raised p-4">
            <div className="grid gap-2 sm:grid-cols-3">
              <input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Name" className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-fg placeholder:text-fg-faint focus:outline-none focus:ring-1 focus:ring-accent" />
              <input value={editEmail} onChange={(e) => setEditEmail(e.target.value)} placeholder="Email" className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-fg placeholder:text-fg-faint focus:outline-none focus:ring-1 focus:ring-accent" />
              <input value={editCompany} onChange={(e) => setEditCompany(e.target.value)} placeholder="Company" className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-fg placeholder:text-fg-faint focus:outline-none focus:ring-1 focus:ring-accent" />
            </div>
            <div className="flex items-center gap-2">
              <button onClick={saveEdit} disabled={editSaving || !editName.trim()} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-accent-fg disabled:opacity-50">{editSaving ? "Saving..." : "Save"}</button>
              <button onClick={() => setEditing(false)} disabled={editSaving} className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-fg-secondary hover:text-fg disabled:opacity-50">Cancel</button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <h1 className="text-2xl font-bold text-fg">{review.name}</h1>
            <button
              onClick={() => router.push(`/?q=${encodeURIComponent(`Give me a full briefing on ${review.name}`)}`)}
              className="flex items-center gap-1.5 rounded-lg border border-accent/20 bg-accent-soft px-2.5 py-1 text-[11px] font-medium text-accent hover:bg-accent/15 hover:border-accent/40 transition-all"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              Ask REMI
            </button>
            <button onClick={() => { setEditName(review.name); setEditEmail(review.email || ""); setEditCompany(review.company || ""); setEditing(true); }} className="rounded-lg border border-border px-2.5 py-1 text-[10px] font-medium text-fg-muted hover:text-fg hover:border-fg-muted transition-colors">Edit</button>
            <button onClick={() => setShowDeleteConfirm(true)} disabled={deleting} className="rounded-lg border border-error/20 px-2.5 py-1 text-[10px] font-medium text-error hover:bg-error-soft transition-all disabled:opacity-50">{deleting ? "Deleting..." : "Delete"}</button>
          </div>
        )}

        <div className="flex items-center gap-3 mt-1">
          {review.company && <span className="text-xs text-fg-muted">{review.company}</span>}
          <span className="text-xs text-fg-faint">{review.property_count} properties · {metrics.total_units} units</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0 border-b border-border overflow-x-auto scrollbar-none -mt-1">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-all whitespace-nowrap shrink-0 ${tab === key ? "border-accent text-fg" : "border-transparent text-fg-muted hover:text-fg-secondary"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {tab === "overview" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <StatHero
              label="Occupancy"
              value={pct(metrics.occupancy_rate)}
              color={metrics.occupancy_rate >= 0.95 ? "var(--color-ok)" : metrics.occupancy_rate >= 0.9 ? "var(--color-warn)" : "var(--color-error)"}
              supporting={[
                { label: "Revenue", value: fmt$(metrics.total_actual_rent) },
                { label: "Units", value: String(metrics.total_units) },
                { label: "LTL", value: fmt$(metrics.loss_to_lease), alert: metrics.loss_to_lease > 0 },
                { label: "Maint", value: String(metrics.open_maintenance) },
              ]}
            />
            <div className="lg:col-span-2">
              {alerts.length > 0 ? (
                <AlertFeed alerts={alerts} title="Needs Attention" />
              ) : (
                <div className="rounded-2xl border border-border bg-surface p-6 h-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="w-10 h-10 rounded-xl bg-ok/10 flex items-center justify-center mb-2 mx-auto">
                      <svg className="w-5 h-5 text-ok" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    </div>
                    <p className="text-sm font-medium text-fg-muted">No urgent issues</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {delinquency && delinquency.total_delinquent > 0 && (
            <PipelineStrip stages={stages} title="Collections Pipeline" />
          )}

          {leases && leaseBuckets.some((b) => b.count > 0) && (
            <TimelineBuckets buckets={leaseBuckets} title="Lease Expirations" total={leases.total_expiring} />
          )}

          {/* Properties grid */}
          {review.properties.length > 0 && (
            <div className="space-y-2">
              <h2 className="text-[10px] font-semibold text-fg-muted uppercase tracking-widest">
                Properties ({review.properties.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {review.properties.map((p) => {
                  const ph: PropertyHealth = {
                    id: p.property_id,
                    name: p.property_name,
                    total_units: p.total_units,
                    occupied: p.occupied,
                    occupancy_rate: p.occupancy_rate,
                    monthly_actual: p.monthly_actual,
                    loss_to_lease: p.loss_to_lease,
                    open_maintenance: p.open_maintenance,
                    issue_count: p.issue_count,
                  };
                  return <PropertyHealthCard key={p.property_id} property={ph} />;
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "rent_roll" && (
        <ManagerRentRollTab managerId={managerId} properties={review.properties} />
      )}

      {tab === "leases" && (
        <ManagerLeasesTab managerId={managerId} />
      )}

      {tab === "trends" && <TrendsTab managerId={managerId} />}
      {tab === "prep" && <ReviewPrepTab managerId={managerId} />}

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
