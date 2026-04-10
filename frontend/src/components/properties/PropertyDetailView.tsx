"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { fmt$ } from "@/lib/format";
import { useApiQuery } from "@/hooks/useApiQuery";
import { PageContainer } from "@/components/ui/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { EntityFormPanel, type FieldDef } from "@/components/ui/EntityFormPanel";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ManagerPicker } from "@/components/ui/ManagerPicker";
import { RentRollTab } from "./RentRollTab";
import { LeasesTab } from "./LeasesTab";
import { PropertyMaintenanceTab } from "./PropertyMaintenanceTab";
import { ActivityTab } from "./ActivityTab";
import { NotesTab } from "./NotesTab";
import type { PropertyDetail, RentRollResponse, ManagerListItem } from "@/lib/types";

type Tab = "rent_roll" | "leases" | "maintenance" | "activity" | "notes";

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "rent_roll", label: "Rent Roll", icon: "M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" },
  { key: "leases", label: "Leases", icon: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" },
  { key: "maintenance", label: "Maintenance", icon: "M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l5.653-4.655a.685.685 0 00-.17-.896l-2.21-1.59a.676.676 0 01.16-1.18l6.096-2.198a.5.5 0 01.618.618L11.3 13.5a.676.676 0 01-1.18.16l-1.59-2.21a.685.685 0 00-.896-.17z" },
  { key: "activity", label: "Activity", icon: "M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" },
  { key: "notes", label: "Notes", icon: "M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" },
];

const MAINT_FIELDS: FieldDef[] = [
  { name: "title", label: "Title", required: true, placeholder: "Leaky faucet in kitchen" },
  { name: "description", label: "Description", type: "textarea", placeholder: "Details..." },
  { name: "category", label: "Category", type: "select", defaultValue: "general", options: [
    { value: "plumbing", label: "Plumbing" }, { value: "electrical", label: "Electrical" },
    { value: "hvac", label: "HVAC" }, { value: "appliance", label: "Appliance" },
    { value: "structural", label: "Structural" }, { value: "general", label: "General" },
    { value: "other", label: "Other" },
  ]},
  { name: "priority", label: "Priority", type: "select", defaultValue: "medium", options: [
    { value: "low", label: "Low" }, { value: "medium", label: "Medium" },
    { value: "high", label: "High" }, { value: "emergency", label: "Emergency" },
  ]},
];

export function PropertyDetailView({ propertyId }: { propertyId: string }) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("rent_roll");
  const [showEditProperty, setShowEditProperty] = useState(false);
  const [showAddMaint, setShowAddMaint] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data, loading, refetch } = useApiQuery<{ property: PropertyDetail; rentRoll: RentRollResponse; managers: ManagerListItem[] }>(async () => {
    const [property, rentRoll, managers] = await Promise.all([
      api.getProperty(propertyId),
      api.getRentRoll(propertyId),
      api.listManagers(),
    ]);
    return { property, rentRoll, managers };
  }, [propertyId]);

  const property = data?.property ?? null;
  const rentRoll = data?.rentRoll ?? null;
  const managers = data?.managers ?? [];

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-fg-faint animate-pulse">Loading property...</div>
      </div>
    );
  }

  if (!property || !rentRoll) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-sm text-fg-muted">Property not found</div>
      </div>
    );
  }

  return (
    <PageContainer wide>
      <div className="anim-fade-up">
        <div className="flex items-center gap-1.5 text-xs text-fg-faint">
          <Link href="/properties" className="hover:text-fg-secondary transition-colors">Properties</Link>
          {property.manager_id && property.manager_name && (
            <>
              <span>/</span>
              <Link href={`/managers/${property.manager_id}`} className="hover:text-fg-secondary transition-colors">{property.manager_name}</Link>
            </>
          )}
        </div>
        <div className="flex items-start justify-between">
          <h1 className="text-2xl font-bold text-fg mt-3">{property.name}</h1>
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={() => setShowEditProperty(true)}
              className="h-8 px-3.5 rounded-xl border border-border text-xs font-medium text-fg-muted hover:text-accent hover:border-accent/40 transition-all btn-glow flex items-center gap-1.5"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
              </svg>
              Edit
            </button>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="h-8 px-3 rounded-xl border border-error/20 text-xs font-medium text-error hover:bg-error-soft transition-all btn-glow btn-glow-danger"
            >
              Delete
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
          <Badge variant={property.property_type === "commercial" ? "cyan" : "blue"}>{property.property_type}</Badge>
          {property.address && (
            <span className="text-sm text-fg-muted">{property.address.street}, {property.address.city}{property.address.state ? `, ${property.address.state}` : ""}</span>
          )}
          {property.year_built > 0 && <span className="text-xs text-fg-ghost">Built {property.year_built}</span>}
          <span className="text-fg-ghost">·</span>
          <ManagerPicker
            currentManagerId={property.manager_id}
            currentManagerName={property.manager_name}
            onAssign={async (managerId) => {
              await api.updateProperty(propertyId, { manager_id: managerId ?? "" });
              refetch();
            }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 stagger">
        {[
          {
            label: "Occupancy",
            value: `${rentRoll.total_units > 0 ? Math.round((rentRoll.occupied / rentRoll.total_units) * 100) : 0}%`,
            sub: `${rentRoll.occupied}/${rentRoll.total_units} units`,
            alert: false,
          },
          { label: "Actual Rent", value: fmt$(rentRoll.total_actual_rent), sub: undefined, alert: false },
          { label: "Market Rent", value: fmt$(rentRoll.total_market_rent), sub: undefined, alert: false },
          {
            label: "Loss to Lease",
            value: fmt$(rentRoll.total_loss_to_lease),
            sub: rentRoll.total_market_rent > 0 ? `${((rentRoll.total_loss_to_lease / rentRoll.total_market_rent) * 100).toFixed(1)}% of market` : undefined,
            alert: rentRoll.total_loss_to_lease > 0,
          },
          { label: "Vacancy Loss", value: fmt$(rentRoll.total_vacancy_loss), sub: `${rentRoll.vacant} vacant`, alert: rentRoll.total_vacancy_loss > 0 },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-border bg-surface px-4 py-3">
            <p className="text-[9px] font-semibold text-fg-muted uppercase tracking-widest mb-1">{stat.label}</p>
            <p className={`text-sm font-bold font-mono ${stat.alert ? "text-warn-fg" : "text-fg"}`}>{stat.value}</p>
            {stat.sub && <p className="text-[10px] text-fg-faint mt-0.5">{stat.sub}</p>}
          </div>
        ))}
      </div>

      <div className="border-b border-border-subtle flex gap-0 overflow-x-auto anim-fade-in scrollbar-none" style={{ animationDelay: "200ms" }}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 sm:px-4 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap shrink-0 ${
              activeTab === tab.key ? "border-accent text-fg" : "border-transparent text-fg-muted hover:text-fg-secondary"
            }`}
          >
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
              <path strokeLinecap="round" strokeLinejoin="round" d={tab.icon} />
            </svg>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex gap-2.5 flex-wrap">
        <button onClick={() => setShowAddMaint(true)} className="h-9 flex items-center gap-2 px-4 rounded-xl border border-dashed border-border bg-surface hover:border-accent/40 hover:text-accent hover:shadow-md hover:shadow-accent/5 text-xs font-medium text-fg-muted transition-all btn-glow">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
          Add Maintenance
        </button>
      </div>

      {activeTab === "rent_roll" && <RentRollTab rentRoll={rentRoll} propertyId={propertyId} />}
      {activeTab === "leases" && <LeasesTab propertyId={propertyId} />}
      {activeTab === "maintenance" && <PropertyMaintenanceTab propertyId={propertyId} />}
      {activeTab === "activity" && <ActivityTab propertyId={propertyId} />}
      {activeTab === "notes" && <NotesTab entityType="Property" entityId={propertyId} />}

      <EntityFormPanel
        open={showEditProperty}
        onClose={() => setShowEditProperty(false)}
        title="Edit Property"
        fields={[
          { name: "name", label: "Name", placeholder: property.name },
          { name: "manager_id", label: "Manager", type: "select", options: [
            { value: "", label: "— None —" },
            ...managers.map((m) => ({ value: m.id, label: m.name })),
          ]},
          { name: "street", label: "Street", placeholder: property.address?.street },
          { name: "city", label: "City", placeholder: property.address?.city },
          { name: "state", label: "State", placeholder: property.address?.state },
          { name: "zip_code", label: "ZIP Code", placeholder: property.address?.zip_code },
        ]}
        initialValues={{
          name: property.name,
          manager_id: property.manager_id ?? "",
          street: property.address?.street,
          city: property.address?.city,
          state: property.address?.state,
          zip_code: property.address?.zip_code,
        }}
        submitLabel="Update Property"
        onSubmit={async (values) => {
          await api.updateProperty(propertyId, values as Record<string, string>);
          refetch();
        }}
      />

      <EntityFormPanel
        open={showAddMaint}
        onClose={() => setShowAddMaint(false)}
        title="Add Maintenance Request"
        fields={[
          { name: "unit_id", label: "Unit", type: "select", required: true, options: (rentRoll?.rows ?? []).map((r) => ({ value: r.unit_id, label: `${r.unit_number}${r.tenant ? ` — ${r.tenant.name}` : ""}` })) },
          ...MAINT_FIELDS,
        ]}
        submitLabel="Create Request"
        onSubmit={async (values) => {
          await api.createMaintenance({ property_id: propertyId, ...values } as Parameters<typeof api.createMaintenance>[0]);
          refetch();
        }}
      />

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete Property"
        description={`Delete "${property.name}"? This will also remove all associated units and leases. This action cannot be undone.`}
        confirmLabel="Delete Property"
        variant="danger"
        onConfirm={async () => {
          await api.deleteProperty(propertyId);
          router.push("/");
        }}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </PageContainer>
  );
}
