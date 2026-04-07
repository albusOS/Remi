"use client";

import { useCallback, useRef, useState, type FormEvent, type ReactNode } from "react";
import { SlidePanel } from "./SlidePanel";

export interface FieldDef {
  name: string;
  label: string;
  type?: "text" | "number" | "date" | "select" | "textarea";
  required?: boolean;
  placeholder?: string;
  options?: { value: string; label: string }[];
  defaultValue?: string | number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  fields: FieldDef[];
  initialValues?: Record<string, string | number | undefined>;
  onSubmit: (values: Record<string, string | number>) => Promise<void>;
  submitLabel?: string;
  children?: ReactNode;
}

const INPUT_BASE =
  "w-full rounded-xl border border-border bg-surface/80 px-3.5 text-sm text-fg placeholder:text-fg-ghost/60 transition-all duration-200 outline-none input-glow focus:border-accent";

export function EntityFormPanel({
  open,
  onClose,
  title,
  fields,
  initialValues,
  onSubmit,
  submitLabel = "Save",
  children,
}: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const handleSubmit = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      setError(null);
      setSaving(true);
      try {
        const fd = new FormData(e.currentTarget);
        const values: Record<string, string | number> = {};
        for (const field of fields) {
          const raw = fd.get(field.name);
          if (raw == null || raw === "") {
            if (field.required) {
              setError(`${field.label} is required`);
              setSaving(false);
              return;
            }
            continue;
          }
          values[field.name] =
            field.type === "number" ? Number(raw) : String(raw);
        }
        await onSubmit(values);
        setSuccess(true);
        setTimeout(() => {
          setSuccess(false);
          onClose();
        }, 500);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong");
      } finally {
        setSaving(false);
      }
    },
    [fields, onSubmit, onClose],
  );

  return (
    <SlidePanel open={open} onClose={onClose} title={title} width="md">
      <form
        ref={formRef}
        onSubmit={handleSubmit}
        className={`flex flex-col gap-5 form-stagger ${success ? "anim-success-flash" : ""}`}
      >
        {/* Error banner with icon */}
        {error && (
          <div className="rounded-xl border border-error/25 bg-error-soft/80 backdrop-blur-sm px-4 py-3 flex items-start gap-3 anim-scale-in">
            <div className="w-7 h-7 rounded-lg bg-error/10 flex items-center justify-center shrink-0 mt-0.5">
              <svg
                className="w-3.5 h-3.5 text-error"
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
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-error-fg">{error}</p>
            </div>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-error-fg/50 hover:text-error-fg transition-colors shrink-0"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Fields with floating labels */}
        {fields.map((f) => (
          <label key={f.name} className="flex flex-col gap-2 group">
            <span className="text-[11px] font-semibold text-fg-muted uppercase tracking-wider group-focus-within:text-accent transition-colors">
              {f.label}
              {f.required && <span className="text-accent ml-1">*</span>}
            </span>
            {f.type === "select" ? (
              <select
                name={f.name}
                defaultValue={
                  initialValues?.[f.name]?.toString() ??
                  f.defaultValue?.toString() ??
                  ""
                }
                className={`${INPUT_BASE} h-10 appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%237a6f66%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_12px_center] pr-8`}
              >
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : f.type === "textarea" ? (
              <textarea
                name={f.name}
                rows={3}
                defaultValue={
                  initialValues?.[f.name]?.toString() ??
                  f.defaultValue?.toString() ??
                  ""
                }
                placeholder={f.placeholder}
                className={`${INPUT_BASE} py-2.5 resize-none`}
              />
            ) : (
              <input
                name={f.name}
                type={f.type ?? "text"}
                defaultValue={
                  initialValues?.[f.name]?.toString() ??
                  f.defaultValue?.toString() ??
                  ""
                }
                placeholder={f.placeholder}
                step={f.type === "number" ? "any" : undefined}
                className={`${INPUT_BASE} h-10`}
              />
            )}
          </label>
        ))}

        {children}

        {/* Action bar */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-border-subtle/60 mt-1">
          <button
            type="button"
            onClick={onClose}
            className="h-10 px-4 rounded-xl text-sm text-fg-muted hover:text-fg hover:bg-surface-sunken transition-all"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || success}
            className="relative h-10 px-6 rounded-xl text-sm font-medium bg-accent text-white transition-all btn-glow disabled:opacity-60 hover:shadow-lg hover:shadow-accent/20"
          >
            {success ? (
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                Done
              </span>
            ) : saving ? (
              <span className="flex items-center gap-2">
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Saving...
              </span>
            ) : (
              submitLabel
            )}
          </button>
        </div>
      </form>
    </SlidePanel>
  );
}
