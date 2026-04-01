"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { SearchHit } from "@/lib/types";

const QUESTION_PREFIXES = [
  "who", "what", "how", "which", "show", "find", "compare",
  "why", "where", "when", "list", "tell", "give", "are", "is",
];

function looksLikeQuestion(q: string): boolean {
  if (q.includes("?")) return true;
  const first = q.trim().split(/\s/)[0]?.toLowerCase() ?? "";
  return QUESTION_PREFIXES.includes(first);
}

function entityHref(hit: SearchHit): string {
  switch (hit.entity_type) {
    case "PropertyManager":
      return `/managers/${hit.entity_id}`;
    case "Property":
      return `/properties/${hit.entity_id}`;
    case "Tenant":
    case "Unit": {
      const pid = hit.metadata.property_id as string | undefined;
      return pid ? `/properties/${pid}` : "/";
    }
    default:
      return "/";
  }
}

const TYPE_ORDER: Record<string, number> = {
  PropertyManager: 0,
  Property: 1,
  Tenant: 2,
  Unit: 3,
  MaintenanceRequest: 4,
  DocumentRow: 5,
};

function groupResults(results: SearchHit[]): [string, SearchHit[]][] {
  const groups = new Map<string, SearchHit[]>();
  for (const r of results) {
    const arr = groups.get(r.label) || [];
    arr.push(r);
    groups.set(r.label, arr);
  }
  return [...groups.entries()].sort(
    (a, b) => (TYPE_ORDER[a[1][0]?.entity_type] ?? 99) - (TYPE_ORDER[b[1][0]?.entity_type] ?? 99),
  );
}

export function SearchBar() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await api.search(query.trim(), 8);
        setResults(res.results);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (!query.trim()) return;

      if (looksLikeQuestion(query) || results.length === 0) {
        router.push(`/ask?q=${encodeURIComponent(query.trim())}`);
        setOpen(false);
        setQuery("");
        return;
      }

      router.push(entityHref(results[0]));
      setOpen(false);
      setQuery("");
    }
  }

  const grouped = groupResults(results);

  return (
    <div ref={containerRef} className="relative w-full max-w-xl">
      <div className="relative">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-ghost"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => { if (results.length > 0) setOpen(true); }}
          onKeyDown={handleKeyDown}
          placeholder="Search managers, properties, tenants... or ask a question"
          className="w-full bg-surface border border-border rounded-xl pl-10 pr-4 py-2.5 text-sm text-fg placeholder-fg-ghost focus:outline-none focus:border-accent/40 focus:shadow-sm transition-all"
        />
        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 border-2 border-fg-ghost border-t-accent rounded-full animate-spin" />
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-30 top-full mt-1.5 w-full rounded-xl border border-border bg-surface-raised shadow-xl overflow-hidden">
          {grouped.map(([label, hits]) => (
            <div key={label}>
              <div className="px-3 py-1.5 text-[9px] font-semibold text-fg-faint uppercase tracking-wide bg-surface-sunken">
                {label}
              </div>
              {hits.map((hit) => (
                <Link
                  key={hit.entity_id}
                  href={entityHref(hit)}
                  onClick={() => { setOpen(false); setQuery(""); }}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-surface-sunken transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-fg truncate">{hit.title}</p>
                    {hit.subtitle && (
                      <p className="text-[11px] text-fg-faint truncate">{hit.subtitle}</p>
                    )}
                  </div>
                  <svg className="w-3.5 h-3.5 text-fg-ghost shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                </Link>
              ))}
            </div>
          ))}
          {query.trim() && (
            <Link
              href={`/ask?q=${encodeURIComponent(query.trim())}`}
              onClick={() => { setOpen(false); setQuery(""); }}
              className="flex items-center gap-2 px-3 py-2.5 border-t border-border-subtle hover:bg-surface-sunken transition-colors"
            >
              <svg className="w-3.5 h-3.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              <span className="text-xs text-accent">Ask REMI: &quot;{query.trim()}&quot;</span>
            </Link>
          )}
        </div>
      )}

      {open && results.length === 0 && query.trim().length >= 2 && !loading && (
        <div className="absolute z-30 top-full mt-1.5 w-full rounded-xl border border-border bg-surface-raised shadow-xl overflow-hidden">
          <div className="px-3 py-4 text-center">
            <p className="text-xs text-fg-faint">No results for &quot;{query}&quot;</p>
          </div>
          <Link
            href={`/ask?q=${encodeURIComponent(query.trim())}`}
            onClick={() => { setOpen(false); setQuery(""); }}
            className="flex items-center gap-2 px-3 py-2.5 border-t border-border-subtle hover:bg-surface-sunken transition-colors"
          >
            <svg className="w-3.5 h-3.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
            <span className="text-xs text-accent">Ask REMI instead</span>
          </Link>
        </div>
      )}
    </div>
  );
}
