"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useSessions } from "@/hooks/useSessions";
import { SessionThread } from "./SessionThread";
import { SessionInput } from "./SessionInput";
import { SessionSidebar } from "./SessionSidebar";
import { SessionEmptyState } from "./SessionEmptyState";
import { ThreadSkeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import type { ManagerListItem } from "@/lib/types";

export function AskView() {
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("claude-sonnet-4-20250514");
  const [managers, setManagers] = useState<ManagerListItem[]>([]);
  const [managerId, setManagerId] = useState("");
  const [showWorkDetails, setShowWorkDetails] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const lastSendRef = useRef<string | null>(null);

  useEffect(() => {
    api.listModels().then((cfg) => {
      setProvider(cfg.default_provider);
      setModel(cfg.default_model);
    }).catch(() => {});

    api.listManagers().then(setManagers).catch(() => {});
  }, []);

  const {
    connected,
    sessions,
    activeSessionId,
    activeSession,
    createSession,
    selectSession,
    send,
    deleteSession: _deleteSession,
    dismissError,
    stopGenerating,
  } = useSessions("director");

  const handleSend = (text: string) => {
    lastSendRef.current = text;
    send(text, "ask", { provider, model, managerId: managerId || undefined });
  };

  const handleRetry = () => {
    if (!lastSendRef.current) {
      const session = activeSession;
      if (!session) return;
      const lastUser = [...session.messages].reverse().find((m) => m.role === "user");
      if (lastUser) {
        send(lastUser.content, "ask", { provider, model, managerId: managerId || undefined });
      }
      return;
    }
    send(lastSendRef.current, "ask", { provider, model, managerId: managerId || undefined });
  };

  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  const session = activeSession;
  const hasMessages = (session?.messages.length ?? 0) > 0;

  return (
    <div className="h-full flex flex-col relative bg-surface">
      {/* Top bar */}
      <div className="shrink-0 h-11 flex items-center px-4 gap-3 border-b border-border-subtle">
        <button
          onClick={() => setSidebarOpen(true)}
          className="p-1.5 rounded-lg text-fg-faint hover:text-fg-secondary hover:bg-surface-sunken transition-all"
          title="History"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>

        <div className="flex-1" />

        {activeSessionId && (
          <button
            onClick={createSession}
            className="p-1.5 rounded-lg text-fg-faint hover:text-fg-secondary hover:bg-surface-sunken transition-all"
            title="New conversation"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          </button>
        )}

        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-ok" : "bg-error"}`} />
          <span className="text-[10px] text-fg-faint">{connected ? "Live" : "Offline"}</span>
        </div>
      </div>

      {/* Error banner */}
      {session?.error && !hasMessages && (
        <div className="shrink-0 mx-4 mt-3 px-4 py-2.5 rounded-xl bg-error-soft border border-error/20 flex items-center justify-between">
          <span className="text-sm text-error-fg">{session.error}</span>
          <button onClick={dismissError} className="text-[10px] text-error/60 hover:text-error ml-4 shrink-0">
            dismiss
          </button>
        </div>
      )}

      {/* Content */}
      {activeSessionId && session && !session.loaded ? (
        <ThreadSkeleton />
      ) : !activeSession || !hasMessages ? (
        <SessionEmptyState
          onSend={handleSend}
          connected={connected}
          streaming={session?.streaming ?? false}
          mode="ask"
          managerName={managers.find((m) => m.id === managerId)?.name}
        />
      ) : (
        <SessionThread
          messages={session!.messages}
          liveContent={session!.liveContent}
          liveTools={session!.liveTools}
          streaming={session!.streaming}
          showWorkDetails={showWorkDetails}
          onRetry={handleRetry}
        />
      )}

      {/* Input */}
      <SessionInput
        onSend={handleSend}
        streaming={session?.streaming ?? false}
        connected={connected}
        hasMessages={hasMessages}
        showWorkDetails={showWorkDetails}
        onToggleWorkDetails={() => setShowWorkDetails((v) => !v)}
        onStop={stopGenerating}
        managers={managers}
        managerId={managerId}
        onManagerChange={setManagerId}
      />

      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={selectSession}
        onCreate={createSession}
        open={sidebarOpen}
        onClose={closeSidebar}
      />
    </div>
  );
}
