"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { FeedEvent } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = API_BASE.replace(/^http/, "ws") + "/api/v1/feed/ws";
const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;

/**
 * Subscribe to the event bus feed via WebSocket.
 *
 * Connects to ``WS /api/v1/feed/ws`` and pushes every bus event
 * matching the requested topic globs to the ``onEvent`` callback.
 * Today that means ``domain.*`` events (``ingestion.complete``,
 * ``entity.updated``, etc.).  When multi-agent orchestration lands,
 * ``agent.*`` lifecycle events will flow here too.
 *
 * Returns connection state for the "Live" indicator.
 */
export function useAppOSEvents(onEvent?: (event: FeedEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const callbackRef = useRef(onEvent);
  callbackRef.current = onEvent;
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef(RECONNECT_BASE_MS);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimer.current !== null) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
  }, []);

  const teardownSocket = useCallback(() => {
    const prev = wsRef.current;
    if (prev) {
      prev.onopen = null;
      prev.onmessage = null;
      prev.onclose = null;
      prev.onerror = null;
      if (prev.readyState === WebSocket.OPEN || prev.readyState === WebSocket.CONNECTING) {
        prev.close();
      }
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(function connectSocket() {
    clearReconnectTimer();
    teardownSocket();

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectDelay.current = RECONNECT_BASE_MS;
    };
    ws.onmessage = (msg) => {
      let parsed: FeedEvent;
      try {
        parsed = JSON.parse(msg.data);
      } catch {
        return;
      }
      callbackRef.current?.(parsed);
    };
    ws.onclose = () => {
      setConnected(false);
      const delay = reconnectDelay.current;
      const jitter = delay * 0.3 * Math.random();
      reconnectDelay.current = Math.min(delay * 2, RECONNECT_MAX_MS);
      reconnectTimer.current = setTimeout(connectSocket, delay + jitter);
    };
    ws.onerror = () => {
      if (ws.readyState !== WebSocket.CLOSED) {
        ws.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearReconnectTimer();
      teardownSocket();
    };
  }, [connect, clearReconnectTimer, teardownSocket]);

  return { connected };
}
