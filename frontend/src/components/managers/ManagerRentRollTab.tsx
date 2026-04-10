"use client";

import { api } from "@/lib/api";
import { useApiQuery } from "@/hooks/useApiQuery";
import { fmt$ } from "@/lib/format";
import { RentRollTab } from "@/components/properties/RentRollTab";
import type { RentRollResponse, ManagerPropertySummary } from "@/lib/types";

export function ManagerRentRollTab({
  managerId,
  properties,
}: {
  managerId: string;
  properties: ManagerPropertySummary[];
}) {
  const { data: rolls, loading } = useApiQuery(async () => {
    if (properties.length === 0) return [];
    return Promise.all(
      properties.map((p) => api.getRentRoll(p.property_id).catch(() => null)),
    );
  }, ["manager_rent_roll", managerId]);

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="rounded-2xl border border-border bg-surface h-64 number-shimmer" />
        ))}
      </div>
    );
  }

  if (!rolls || properties.length === 0) {
    return <div className="py-16 text-center text-sm text-fg-muted">No properties in this portfolio</div>;
  }

  const pairs = properties
    .map((p, i) => ({ property: p, roll: rolls[i] }))
    .filter((x): x is { property: ManagerPropertySummary; roll: RentRollResponse } => x.roll != null);

  if (pairs.length === 0) {
    return <div className="py-16 text-center text-sm text-fg-muted">No rent roll data available</div>;
  }

  const totalUnits = pairs.reduce((s, { roll }) => s + roll.total_units, 0);
  const totalOccupied = pairs.reduce((s, { roll }) => s + roll.occupied, 0);
  const totalActual = pairs.reduce((s, { roll }) => s + roll.total_actual_rent, 0);
  const totalLTL = pairs.reduce((s, { roll }) => s + roll.total_loss_to_lease, 0);

  return (
    <div className="space-y-6">
      {/* Portfolio summary strip */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-fg-muted">
        <span><span className="text-fg font-semibold">{pairs.length}</span> properties</span>
        <span className="text-fg-ghost">·</span>
        <span><span className="text-fg font-semibold font-mono">{totalOccupied}/{totalUnits}</span> occupied</span>
        <span className="text-fg-ghost">·</span>
        <span className="font-mono"><span className="text-fg font-semibold">{fmt$(totalActual)}</span>/mo actual</span>
        {totalLTL > 0 && (
          <>
            <span className="text-fg-ghost">·</span>
            <span className="text-warn font-mono font-semibold">{fmt$(totalLTL)} loss to lease</span>
          </>
        )}
      </div>

      {/* Per-property rent rolls */}
      {pairs.map(({ property, roll }) => (
        <div key={property.property_id} className="space-y-2">
          <div className="flex items-baseline gap-3 flex-wrap">
            <h3 className="text-xs font-semibold text-fg">{property.property_name}</h3>
            <span className="text-[11px] text-fg-muted">
              {roll.occupied}/{roll.total_units} occupied
              <span className="mx-1.5 text-fg-ghost">·</span>
              <span className="font-mono">{fmt$(roll.total_actual_rent)}/mo</span>
              {roll.total_loss_to_lease > 0 && (
                <span className="text-warn ml-1.5 font-mono">· {fmt$(roll.total_loss_to_lease)} LTL</span>
              )}
            </span>
          </div>
          <RentRollTab rentRoll={roll} propertyId={property.property_id} />
        </div>
      ))}
    </div>
  );
}
