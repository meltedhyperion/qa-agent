"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { abortExecution, getExecutionStatus } from "@/lib/api";
import { useSessionStore, type TrajectoryEntry } from "@/lib/store";
import { useExecutionWebSocket } from "@/lib/websocket";

function statusBadge(status: string) {
  switch (status) {
    case "passed":
      return <Badge className="bg-green-600">PASSED</Badge>;
    case "failed":
    case "error":
      return <Badge variant="destructive">FAILED</Badge>;
    case "running":
      return <Badge className="bg-blue-600">RUNNING</Badge>;
    case "retrying":
      return <Badge className="bg-yellow-600">RETRYING</Badge>;
    case "queued":
      return <Badge variant="secondary">QUEUED</Badge>;
    case "skipped":
      return <Badge variant="outline">SKIPPED</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function stepIcon(status: string) {
  switch (status) {
    case "passed":
      return <span className="text-green-600 font-mono">+</span>;
    case "failed":
      return <span className="text-red-500 font-mono">x</span>;
    case "executing":
      return <span className="text-blue-500 font-mono animate-pulse">*</span>;
    case "info":
      return <span className="text-muted-foreground font-mono">~</span>;
    default:
      return <span className="font-mono">.</span>;
  }
}

function formatAction(entry: TrajectoryEntry) {
  if (entry.action === "thinking") {
    return entry.detail;
  }
  const name = entry.action.replace(/_/g, " ");
  if (entry.detail) {
    return `${name}(${entry.detail})`;
  }
  return name;
}

function TrajectoryLog({ entries }: { entries: TrajectoryEntry[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries.length]);

  if (entries.length === 0) return null;

  return (
    <div className="mt-2 bg-muted/50 rounded p-2 max-h-48 overflow-y-auto text-xs font-mono space-y-0.5">
      {entries.map((entry, i) => (
        <div key={i} className="flex gap-2 items-start leading-tight">
          <span className="shrink-0 w-3 text-center">{stepIcon(entry.status)}</span>
          <span
            className={
              entry.status === "failed"
                ? "text-red-500"
                : entry.status === "info"
                ? "text-muted-foreground italic"
                : ""
            }
          >
            {formatAction(entry)}
            {entry.error && entry.status === "failed" && (
              <span className="text-red-400 ml-1">- {entry.error.slice(0, 120)}</span>
            )}
          </span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

export default function ExecutePage({ params }: { params: Promise<{ id: string }> }) {
  const { id: sessionId } = use(params);
  const router = useRouter();
  const store = useSessionStore();
  const [aborting, setAborting] = useState(false);

  // Connect WebSocket
  useExecutionWebSocket(sessionId);

  // Poll status as fallback
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const status = await getExecutionStatus(sessionId);
        if (status.state === "completed" || status.state === "failed" || status.state === "aborted") {
          store.setExecutionStatus(status.state === "completed" ? "completed" : "aborted");
          clearInterval(interval);
        }
      } catch {
        // Ignore polling errors
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [sessionId, store]);

  const {
    testStatuses,
    testTrajectories,
    executionStatus,
    selectedTestIds,
    totalTests,
    sections,
  } = store;

  // Build a testId → title lookup from sections (covers queued tests)
  const testTitleMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const section of sections) {
      for (const tc of section.test_cases) {
        map[tc.id] = tc.title;
      }
    }
    return map;
  }, [sections]);

  const statusEntries = Object.values(testStatuses);
  const completed = statusEntries.filter(
    (s) => s.status === "passed" || s.status === "failed" || s.status === "error" || s.status === "skipped"
  ).length;
  const passed = statusEntries.filter((s) => s.status === "passed").length;
  const failed = statusEntries.filter(
    (s) => s.status === "failed" || s.status === "error"
  ).length;
  const running = statusEntries.filter((s) => s.status === "running").length;
  const total = totalTests || selectedTestIds.length;
  const progress = total > 0 ? (completed / total) * 100 : 0;

  const handleAbort = async () => {
    setAborting(true);
    try {
      await abortExecution(sessionId);
      store.setExecutionStatus("aborted");
    } catch {
      // Ignore
    }
    setAborting(false);
  };

  const isDone = executionStatus === "completed" || executionStatus === "aborted";

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Execution Monitor</h1>
          <div className="flex gap-2">
            {isDone && (
              <Button onClick={() => router.push(`/sessions/${sessionId}/results`)}>
                View Results
              </Button>
            )}
            {!isDone && (
              <Button
                variant="destructive"
                onClick={handleAbort}
                disabled={aborting}
              >
                {aborting ? "Aborting..." : "Abort"}
              </Button>
            )}
          </div>
        </div>

        {/* Summary */}
        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="flex gap-6 text-sm">
              <span>Total: {total}</span>
              <span>Running: {running}</span>
              <span className="text-green-600">Passed: {passed}</span>
              <span className="text-red-600">Failed: {failed}</span>
              <span>Completed: {completed}/{total}</span>
            </div>
            <Progress value={progress} className="h-2" />
            <p className="text-xs text-muted-foreground">
              {Math.round(progress)}% complete
            </p>
          </CardContent>
        </Card>

        {/* Test cases */}
        <ScrollArea className="h-[600px]">
          <div className="space-y-3">
            {selectedTestIds.map((testId) => {
              const status = testStatuses[testId];
              const currentStatus = status?.status || "queued";
              const trajectory = testTrajectories[testId] || [];
              const title =
                status?.test_title || testTitleMap[testId] || testId;

              return (
                <Card key={testId}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 min-w-0">
                        <Badge variant="outline" className="text-xs shrink-0">
                          {testId}
                        </Badge>
                        <span className="font-medium text-sm truncate">
                          {title}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {status && currentStatus === "running" && (
                          <span className="text-xs text-muted-foreground">
                            Step {status.current_step}/{status.total_steps}
                          </span>
                        )}
                        {statusBadge(currentStatus)}
                      </div>
                    </div>

                    {/* Trajectory log */}
                    <TrajectoryLog entries={trajectory} />

                    {/* Error display for final errors */}
                    {status?.error && currentStatus !== "running" && (
                      <p className="mt-2 text-xs text-red-500 font-mono">
                        {status.error}
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
