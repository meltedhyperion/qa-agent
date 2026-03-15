"use client";

import { useEffect, useRef } from "react";
import { useSessionStore } from "./store";
import type { WSMessage } from "./types";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function useExecutionWebSocket(sessionId: string | null) {
  const handleWSMessage = useSessionStore((s) => s.handleWSMessage);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sessionId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);
        handleWSMessage(data);
      } catch {
        // Ignore non-JSON messages (like "pong")
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    // Ping to keep alive
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      ws.close();
    };
  }, [sessionId, handleWSMessage]);

  return wsRef;
}
