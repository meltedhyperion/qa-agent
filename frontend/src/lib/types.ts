export interface TestCase {
  id: string;
  title: string;
  description: string;
  steps: string[];
  expected_result?: string;
  raw_text?: string;
}

export interface Section {
  name: string;
  test_case_count: number;
  test_cases: TestCase[];
}

export interface ParseResult {
  session_id: string;
  document_title: string;
  total_sections: number;
  total_test_cases: number;
  sections: Section[];
  config: TestConfig | null;
}

export interface TestConfig {
  app_url: string;
  credentials: Record<string, string>;
  timeout_ms: number;
  model: string;
  extra: Record<string, unknown>;
  test_specific: Record<string, Record<string, unknown>>;
}

export interface CustomBrowser {
  name: string;
  executable_path: string;
}

export interface ExecutionConfig {
  selected_sections: string[];
  selected_test_ids: string[];
  execution_mode: "parallel" | "sequential";
  concurrency: number;
  model: string;
  browsers: string[];
  custom_browsers: CustomBrowser[];
  system_prompt: string;
  upload_folder: string | null;
  max_retries: number;
}

export interface StepResult {
  step_index: number;
  step_description: string;
  action: string;
  status: "passed" | "failed" | "skipped";
  screenshot_path: string | null;
  error: string | null;
  duration_ms: number;
}

export interface TestResult {
  test_id: string;
  test_title: string;
  status: "passed" | "failed" | "skipped" | "error";
  steps: StepResult[];
  summary: string;
  duration_ms: number;
  video_path: string | null;
  retry_count: number;
  browser: string;
}

export interface SessionSummary {
  id: string;
  state: string;
  created_at: string;
  document: string | null;
  has_config: boolean;
  test_case_count: number;
}

export interface ExecutionStatus {
  session_id: string;
  state: string;
  total: number;
  completed: number;
  passed: number;
  failed: number;
  skipped: number;
  is_running: boolean;
}

// WebSocket message types
export interface WSTestStatus {
  type: "test_status";
  test_id: string;
  test_title: string;
  status: string;
  current_step: number;
  total_steps: number;
  last_action: string;
  screenshot_url: string | null;
  error: string | null;
  timestamp: string;
}

export interface WSStepUpdate {
  type: "step_update";
  test_id: string;
  step_index: number;
  step_description: string;
  action: string;
  action_detail: string;
  status: string;
  screenshot_url: string | null;
  error: string | null;
  timestamp: string;
}

export interface WSExecutionComplete {
  type: "execution_complete";
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  report_url: string;
  timestamp: string;
}

export type WSMessage =
  | { type: "execution_started"; total_tests: number; execution_mode: string }
  | WSTestStatus
  | WSStepUpdate
  | WSExecutionComplete;
