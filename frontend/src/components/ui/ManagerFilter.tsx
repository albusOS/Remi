"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ManagerListItem } from "@/lib/types";

interface Props {
  value: string;
  onChange: (managerId: string) => void;
  managers?: ManagerListItem[];
}

export function ManagerFilter({ value, onChange, managers: externalManagers }: Props) {
  const [fetched, setFetched] = useState<ManagerListItem[]>([]);

  useEffect(() => {
    if (!externalManagers) {
      api.listManagers().then(setFetched).catch(() => {});
    }
  }, [externalManagers]);

  const raw = externalManagers ?? fetched;
  const managers = raw.filter((m) => m.total_units > 0 || m.property_count > 0);

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-surface border border-border rounded-lg px-3 py-1.5 text-xs text-fg-secondary focus:outline-none focus:border-fg-faint"
    >
      <option value="">All Managers</option>
      {managers.map((m) => (
        <option key={m.id} value={m.id}>
          {m.name} ({m.property_count} props, {m.total_units} units)
        </option>
      ))}
    </select>
  );
}
