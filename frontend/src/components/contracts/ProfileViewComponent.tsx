"use client";

import type { ProfileView } from "@/lib/types";

export function ProfileViewComponent({ data }: { data: ProfileView }) {
  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="px-6 py-4 border-b border-border">
        <p className="text-xs font-medium text-fg-muted uppercase tracking-wide">
          {data.entity_type}
        </p>
        <h3 className="text-xl font-bold text-fg mt-1">{data.title}</h3>
        <p className="text-sm text-fg-secondary">{data.entity_id}</p>
      </div>
      <div className="divide-y divide-border-subtle">
        {data.sections.map((section, i) => (
          <div key={i} className="px-6 py-4">
            <h4 className="text-sm font-semibold text-fg-secondary mb-3">
              {section.heading}
            </h4>
            <dl className="grid grid-cols-2 gap-x-8 gap-y-2">
              {section.fields.map((field, j) => (
                <div key={j}>
                  <dt className="text-xs text-fg-muted">{field.label}</dt>
                  <dd className="text-sm text-fg">
                    {String(field.value ?? "—")}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
