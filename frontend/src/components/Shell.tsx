"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAppOSEvents } from "@/hooks/useAppOSEvents";
import { CommandMenu, useCommandMenu } from "@/components/ui/CommandMenu";
import { useTheme } from "@/lib/theme";
import type { FeedEvent } from "@/lib/types";

function NavLink({
  href, label, icon, active, collapsed, onClick,
}: {
  href: string; label: string; icon: ReactNode; active: boolean; collapsed?: boolean; onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      title={collapsed ? label : undefined}
      className={`
        flex items-center rounded-lg text-[13px] transition-all
        ${collapsed ? "justify-center px-2 py-2" : "gap-3 px-3 py-2"}
        ${active
          ? "bg-accent-soft text-fg font-medium border border-accent/20"
          : "text-fg-muted hover:text-fg-secondary hover:bg-surface-raised border border-transparent"
        }
      `}
    >
      {icon}
      {!collapsed && <span>{label}</span>}
    </Link>
  );
}

function HamburgerButton({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="md:hidden flex items-center justify-center w-9 h-9 rounded-lg text-fg-muted hover:text-fg hover:bg-surface-raised transition-colors"
      aria-label={open ? "Close menu" : "Open menu"}
    >
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        {open ? (
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        ) : (
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        )}
      </svg>
    </button>
  );
}

const NAV_ITEMS = [
  {
    href: "/",
    label: "REMI",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
      </svg>
    ),
  },
  {
    href: "/managers",
    label: "Managers",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
      </svg>
    ),
  },
  {
    href: "/documents",
    label: "Documents",
    icon: (
      <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
      </svg>
    ),
  },
];

const INVALIDATION_MAP: Record<string, string[][]> = {
  "ingestion.complete": [["api", "documents"], ["api", "dashboard"], ["api", "properties"], ["api", "managers"]],
  "assertion.created": [["api", "events"], ["api", "properties"], ["api", "managers"]],
};

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const queryClient = useQueryClient();

  const onEvent = useCallback((event: FeedEvent) => {
    const keys = INVALIDATION_MAP[event.topic];
    if (keys) {
      for (const key of keys) {
        queryClient.invalidateQueries({ queryKey: key });
      }
    }
  }, [queryClient]);

  const { connected } = useAppOSEvents(onEvent);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const cmd = useCommandMenu();
  const { theme, toggle: toggleTheme } = useTheme();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/" || pathname === "/ask";
    if (href === "/managers")
      return pathname.startsWith("/managers") || pathname.startsWith("/properties");
    return pathname.startsWith(href);
  };

  const closeMobile = () => setMobileOpen(false);

  const sidebarContent = (isCollapsed: boolean) => (
    <>
      <div className={`border-b border-border-subtle ${isCollapsed ? "px-2 py-4 flex justify-center" : "px-4 py-4"}`}>
        <div className={`flex items-center ${isCollapsed ? "" : "gap-2.5"}`}>
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center shrink-0">
            <span className="text-accent-fg text-[11px] font-bold tracking-tight">R</span>
          </div>
          {!isCollapsed && (
            <div className="min-w-0">
              <h1 className="text-sm font-semibold text-fg tracking-tight">REMI</h1>
              <p className="text-[9px] text-fg-faint -mt-0.5 truncate">portfolio intelligence</p>
            </div>
          )}
        </div>
      </div>

      <div className="px-2 pt-2">
        <button
          onClick={() => { closeMobile(); cmd.setOpen(true); }}
          title={isCollapsed ? "Search (⌘K)" : undefined}
          className={`
            flex items-center rounded-lg border border-border bg-surface text-[11px] text-fg-faint hover:text-fg-muted hover:border-fg-ghost transition-all
            ${isCollapsed ? "w-full justify-center px-2 py-1.5" : "w-full gap-2 px-2.5 py-1.5"}
          `}
        >
          <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          {!isCollapsed && (
            <>
              <span className="flex-1 text-left truncate">Search...</span>
              <kbd className="font-mono text-[9px] opacity-40">⌘K</kbd>
            </>
          )}
        </button>
      </div>

      <div className="flex-1 py-2 px-2 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} {...item} active={isActive(item.href)} collapsed={isCollapsed} onClick={closeMobile} />
        ))}
      </div>

      <div className={`border-t border-border-subtle ${isCollapsed ? "px-2 py-3 flex flex-col items-center gap-2" : "px-3 py-3 flex items-center justify-between gap-2"}`}>
        <div className="flex items-center gap-2">
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 transition-colors ${connected ? "bg-ok" : "bg-error"}`} />
          {!isCollapsed && (
            <span className="text-[10px] text-fg-faint">
              {connected ? "Live" : "Offline"}
            </span>
          )}
        </div>
        <div className={`flex items-center ${isCollapsed ? "flex-col gap-1" : "gap-1"}`}>
          <button
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-fg-faint hover:text-fg hover:bg-surface-raised transition-all"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? (
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
              </svg>
            )}
          </button>
          {/* Collapse toggle — desktop only */}
          <button
            onClick={() => setCollapsed((c) => !c)}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden md:flex w-7 h-7 rounded-lg items-center justify-center text-fg-faint hover:text-fg hover:bg-surface-raised transition-all"
            aria-label="Toggle sidebar"
          >
            <svg
              className={`w-3.5 h-3.5 transition-transform duration-200 ${isCollapsed ? "rotate-180" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
            </svg>
          </button>
        </div>
      </div>
    </>
  );

  return (
    <div className="h-screen flex overflow-hidden">
      <nav
        className={`hidden md:flex shrink-0 border-r border-border bg-surface-sunken flex-col transition-[width] duration-200 ease-out overflow-hidden ${collapsed ? "w-14" : "w-52"}`}
      >
        {sidebarContent(collapsed)}
      </nav>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-fg/20 drawer-overlay" onClick={closeMobile} />
          <nav className="absolute left-0 top-0 bottom-0 w-64 bg-surface-raised border-r border-border flex flex-col drawer-panel" style={{ animationName: "drawerSlideLeft" }}>
            {sidebarContent(false)}
          </nav>
        </div>
      )}

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <div className="md:hidden shrink-0 flex items-center gap-2 px-3 py-2 border-b border-border-subtle bg-surface">
          <HamburgerButton open={mobileOpen} onClick={() => setMobileOpen(!mobileOpen)} />
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-6 h-6 rounded-md bg-accent flex items-center justify-center shrink-0">
              <span className="text-accent-fg text-[9px] font-bold">R</span>
            </div>
            <span className="text-sm font-semibold text-fg truncate">REMI</span>
          </div>
          <div className="ml-auto flex items-center gap-1">
            <button
              onClick={() => cmd.setOpen(true)}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-fg-muted hover:text-fg hover:bg-surface-raised transition-colors"
              aria-label="Search"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </button>
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${connected ? "bg-ok" : "bg-error"}`} />
          </div>
        </div>

        <main className="flex-1 overflow-hidden">{children}</main>
      </div>

      <CommandMenu open={cmd.open} onOpenChange={cmd.setOpen} />
    </div>
  );
}
