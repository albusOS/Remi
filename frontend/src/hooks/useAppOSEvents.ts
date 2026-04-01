"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { WsEvent } from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/events";
const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;

export function useAppOSEvents(onEvent?: (event: WsEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const lastEventRef = useRef<WsEvent | null>(null);
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
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(msg.data);
      } catch {
        console.warn("[useAppOSEvents] received malformed JSON from server");
        return;
      }
      if (parsed.type === "ping") {
        try {
          ws.send(JSON.stringify({ type: "pong" }));
        } catch {
          // socket closing — onclose will handle reconnect
        }
        return;
      }
      const event = parsed as unknown as WsEvent;
      lastEventRef.current = event;
      callbackRef.current?.(event);
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

  return { connected, lastEventRef };
}
