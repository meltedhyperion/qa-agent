"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  getSession,
  getReportUrl,
  getExportUrl,
  getScreenshots,
} from "@/lib/api";

interface TestResult {
  test_id: string;
  test_title: string;
  status: string;
  steps: {
    step_index: number;
    step_description: string;
    action: string;
    status: string;
    screenshot_path: string | null;
    error: string | null;
  }[];
  summary: string;
  duration_ms: number;
  video_path: string | null;
  retry_count: number;
  browser?: string;
}

function statusIcon(status: string) {
  switch (status) {
    case "passed":
      return "✓";
    case "failed":
    case "error":
      return "✗";
    case "skipped":
      return "→";
    default:
      return "?";
  }
}

function statusColor(status: string) {
  switch (status) {
    case "passed":
      return "text-green-600";
    case "failed":
    case "error":
      return "text-red-600";
    case "skipped":
      return "text-muted-foreground";
    default:
      return "";
  }
}

export default function ResultsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: sessionId } = use(params);
  const router = useRouter();
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [sessionState, setSessionState] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const session = await getSession(sessionId);
        setResults((session.results as TestResult[]) || []);
        setSessionState((session.state as string) || "");
      } catch (e) {
        console.error("Failed to load session:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  const passed = results.filter((r) => r.status === "passed").length;
  const failed = results.filter(
    (r) => r.status === "failed" || r.status === "error"
  ).length;
  const skipped = results.filter((r) => r.status === "skipped").length;
  const totalDuration = results.reduce((sum, r) => sum + r.duration_ms, 0);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading results...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Test Results</h1>
          <Button variant="outline" onClick={() => router.push("/")}>
            New Session
          </Button>
        </div>

        {/* Summary */}
        <Card>
          <CardContent className="p-4">
            <div className="flex gap-6 text-sm">
              <span>Total: {results.length}</span>
              <span className="text-green-600">Passed: {passed}</span>
              <span className="text-red-600">Failed: {failed}</span>
              <span>Skipped: {skipped}</span>
              <span>
                Duration: {Math.round(totalDuration / 1000)}s
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Export */}
        <Card>
          <CardContent className="p-4 flex gap-3">
            <a href={getReportUrl(sessionId)} download>
              <Button>Download Results Report (.docx)</Button>
            </a>
            <a href={getExportUrl(sessionId)} download>
              <Button variant="outline">Download Full Session (ZIP)</Button>
            </a>
          </CardContent>
        </Card>

        {/* Results */}
        <ScrollArea className="h-[600px]">
          <div className="space-y-4">
            {results.map((result) => (
              <Card key={result.test_id}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{result.test_id}</Badge>
                      {result.browser && result.browser !== "chromium" && (
                        <Badge variant="secondary" className="text-xs">
                          {result.browser}
                        </Badge>
                      )}
                      <CardTitle className="text-base">
                        {result.test_title}
                      </CardTitle>
                    </div>
                    <Badge
                      className={
                        result.status === "passed"
                          ? "bg-green-600"
                          : result.status === "failed" ||
                            result.status === "error"
                          ? "bg-red-600"
                          : ""
                      }
                      variant={
                        result.status === "skipped" ? "secondary" : "default"
                      }
                    >
                      {result.status.toUpperCase()}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  {result.steps.length > 0 && (
                    <div className="space-y-1">
                      {result.steps.map((step) => (
                        <div
                          key={step.step_index}
                          className={`flex items-start gap-2 text-sm ${statusColor(step.status)}`}
                        >
                          <span className="font-mono w-4 shrink-0">
                            {statusIcon(step.status)}
                          </span>
                          <span>
                            {step.step_index}. {step.step_description}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {result.summary && (
                    <>
                      <Separator />
                      <p className="text-xs text-muted-foreground whitespace-pre-wrap">
                        {result.summary.slice(0, 500)}
                      </p>
                    </>
                  )}
                  <div className="text-xs text-muted-foreground">
                    Duration: {Math.round(result.duration_ms / 1000)}s
                    {result.retry_count > 0 &&
                      ` | Retries: ${result.retry_count}`}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
