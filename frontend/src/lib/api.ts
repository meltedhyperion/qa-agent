const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Upload ──────────────────────────────────────────────────────────────────

export async function uploadDocument(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ session_id: string; filename: string }>(
    "/api/upload/document",
    { method: "POST", body: form }
  );
}

export async function uploadConfig(sessionId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ session_id: string; filename: string }>(
    `/api/upload/config/${sessionId}`,
    { method: "POST", body: form }
  );
}

export async function uploadTestFiles(sessionId: string, files: File[]) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return request<{ session_id: string; filenames: string[]; upload_folder: string }>(
    `/api/upload/files/${sessionId}`,
    { method: "POST", body: form }
  );
}

// ── Sessions ────────────────────────────────────────────────────────────────

export async function listSessions() {
  return request<
    {
      id: string;
      state: string;
      created_at: string;
      document: string | null;
      has_config: boolean;
      test_case_count: number;
    }[]
  >("/api/sessions");
}

export async function getSession(sessionId: string) {
  return request<Record<string, unknown>>(`/api/sessions/${sessionId}`);
}

export async function parseDocument(
  sessionId: string,
  parsingHint: string = "",
  model: string = "gpt-4o"
) {
  return request<{
    session_id: string;
    document_title: string;
    total_sections: number;
    total_test_cases: number;
    sections: {
      name: string;
      test_case_count: number;
      test_cases: {
        id: string;
        title: string;
        description: string;
        steps: string[];
        expected_result: string;
      }[];
    }[];
    config: Record<string, unknown> | null;
  }>(`/api/sessions/${sessionId}/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parsing_hint: parsingHint, model }),
  });
}

export async function configureSession(
  sessionId: string,
  config: {
    selected_sections: string[];
    selected_test_ids: string[];
    execution_mode: "parallel" | "sequential";
    concurrency: number;
    model: string;
    browsers?: string[];
    custom_browsers?: { name: string; executable_path: string }[];
    system_prompt: string;
    upload_folder: string | null;
    max_retries: number;
  }
) {
  return request<Record<string, unknown>>(
    `/api/sessions/${sessionId}/configure`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }
  );
}

export async function checkBrowsers(
  browsers: string[],
  customBrowsers: { name: string; executable_path: string }[] = []
) {
  return request<{
    results: {
      name: string;
      available: boolean;
      message: string;
      path: string;
    }[];
  }>("/api/sessions/check-browsers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ browsers, custom_browsers: customBrowsers }),
  });
}

export async function deleteSession(sessionId: string) {
  return request<{ deleted: boolean }>(`/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

// ── Execution ───────────────────────────────────────────────────────────────

export async function startExecution(sessionId: string) {
  return request<{
    session_id: string;
    status: string;
    execution_mode: string;
    total_tests: number;
  }>(`/api/sessions/${sessionId}/run`, { method: "POST" });
}

export async function getExecutionStatus(sessionId: string) {
  return request<{
    session_id: string;
    state: string;
    total: number;
    completed: number;
    passed: number;
    failed: number;
    skipped: number;
    is_running: boolean;
  }>(`/api/sessions/${sessionId}/status`);
}

export async function abortExecution(sessionId: string) {
  return request<{ session_id: string; status: string }>(
    `/api/sessions/${sessionId}/abort`,
    { method: "POST" }
  );
}

// ── Export ───────────────────────────────────────────────────────────────────

export function getReportUrl(sessionId: string) {
  return `${API_BASE}/api/sessions/${sessionId}/report`;
}

export function getExportUrl(sessionId: string) {
  return `${API_BASE}/api/sessions/${sessionId}/export`;
}

export function getScreenshotUrl(
  sessionId: string,
  testId: string,
  filename: string
) {
  return `${API_BASE}/api/sessions/${sessionId}/screenshot-file/${testId}/${filename}`;
}

export async function getScreenshots(sessionId: string, testId: string) {
  return request<{
    test_id: string;
    screenshots: { filename: string; path: string; url: string }[];
  }>(`/api/sessions/${sessionId}/screenshots/${testId}`);
}
