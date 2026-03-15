"use client";

import { create } from "zustand";
import type { TestCase, Section, TestConfig, CustomBrowser, WSMessage } from "./types";

interface TestStatus {
  test_id: string;
  test_title: string;
  status: string;
  current_step: number;
  total_steps: number;
  last_action: string;
  error: string | null;
}

export interface TrajectoryEntry {
  action: string;
  detail: string;
  status: "executing" | "passed" | "failed" | "info";
  timestamp: string;
  error?: string | null;
}

interface SessionStore {
  // Session
  sessionId: string | null;
  documentFilename: string | null;
  configFilename: string | null;

  // Parsed data
  documentTitle: string;
  sections: Section[];
  testConfig: TestConfig | null;

  // Review config
  selectedSections: string[];
  selectedTestIds: string[];
  executionMode: "parallel" | "sequential";
  concurrency: number;
  model: string;
  browsers: string[];
  customBrowsers: CustomBrowser[];
  systemPrompt: string;
  uploadFolder: string;
  uploadedTestFiles: string[];

  // Execution state
  executionStatus: "idle" | "running" | "completed" | "aborted";
  testStatuses: Record<string, TestStatus>;
  testTrajectories: Record<string, TrajectoryEntry[]>;
  totalTests: number;

  // Results summary
  passedCount: number;
  failedCount: number;
  skippedCount: number;

  // Actions
  setSession: (id: string) => void;
  setDocumentUploaded: (filename: string) => void;
  setConfigUploaded: (filename: string) => void;
  setParsedData: (data: {
    documentTitle: string;
    sections: Section[];
    config: TestConfig | null;
  }) => void;
  setSelectedSections: (sections: string[]) => void;
  toggleTestCase: (testId: string) => void;
  selectAllTestCases: () => void;
  deselectAllTestCases: () => void;
  setExecutionMode: (mode: "parallel" | "sequential") => void;
  setConcurrency: (n: number) => void;
  setModel: (model: string) => void;
  setBrowsers: (browsers: string[]) => void;
  toggleBrowser: (browser: string) => void;
  addCustomBrowser: (browser: CustomBrowser) => void;
  removeCustomBrowser: (name: string) => void;
  setSystemPrompt: (prompt: string) => void;
  setUploadFolder: (folder: string) => void;
  addUploadedTestFiles: (filenames: string[]) => void;
  clearUploadedTestFiles: () => void;
  setExecutionStatus: (status: "idle" | "running" | "completed" | "aborted") => void;
  handleWSMessage: (msg: WSMessage) => void;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  documentFilename: null,
  configFilename: null,
  documentTitle: "",
  sections: [],
  testConfig: null,
  selectedSections: [],
  selectedTestIds: [],
  executionMode: "sequential" as const,
  concurrency: 3,
  model: "gpt-4o",
  browsers: ["chromium"],
  customBrowsers: [] as CustomBrowser[],
  systemPrompt: "",
  uploadFolder: "",
  uploadedTestFiles: [] as string[],
  executionStatus: "idle" as const,
  testStatuses: {},
  testTrajectories: {} as Record<string, TrajectoryEntry[]>,
  totalTests: 0,
  passedCount: 0,
  failedCount: 0,
  skippedCount: 0,
};

export const useSessionStore = create<SessionStore>((set, get) => ({
  ...initialState,

  setSession: (id) => set({ sessionId: id }),

  setDocumentUploaded: (filename) => set({ documentFilename: filename }),

  setConfigUploaded: (filename) => set({ configFilename: filename }),

  setParsedData: (data) => {
    const allTestIds = data.sections.flatMap((s) =>
      s.test_cases.map((tc) => tc.id)
    );
    const allSections = data.sections.map((s) => s.name);
    set({
      documentTitle: data.documentTitle,
      sections: data.sections,
      testConfig: data.config,
      selectedSections: allSections,
      selectedTestIds: allTestIds,
      model: data.config?.model || "gpt-4o",
    });
  },

  setSelectedSections: (sections) => {
    const store = get();
    const testIds = store.sections
      .filter((s) => sections.includes(s.name))
      .flatMap((s) => s.test_cases.map((tc) => tc.id));
    set({ selectedSections: sections, selectedTestIds: testIds });
  },

  toggleTestCase: (testId) => {
    const ids = get().selectedTestIds;
    if (ids.includes(testId)) {
      set({ selectedTestIds: ids.filter((id) => id !== testId) });
    } else {
      set({ selectedTestIds: [...ids, testId] });
    }
  },

  selectAllTestCases: () => {
    const allIds = get().sections.flatMap((s) =>
      s.test_cases.map((tc) => tc.id)
    );
    set({ selectedTestIds: allIds });
  },

  deselectAllTestCases: () => set({ selectedTestIds: [] }),

  setExecutionMode: (mode) => set({ executionMode: mode }),
  setConcurrency: (n) => set({ concurrency: n }),
  setModel: (model) => set({ model }),
  setBrowsers: (browsers) => set({ browsers }),
  toggleBrowser: (browser) => {
    const current = get().browsers;
    if (current.includes(browser)) {
      // Don't allow deselecting the last browser
      if (current.length > 1) {
        set({ browsers: current.filter((b) => b !== browser) });
      }
    } else {
      set({ browsers: [...current, browser] });
    }
  },
  addCustomBrowser: (browser) => {
    const current = get().customBrowsers;
    if (!current.some((b) => b.name === browser.name)) {
      set({ customBrowsers: [...current, browser] });
    }
  },
  removeCustomBrowser: (name) => {
    set({ customBrowsers: get().customBrowsers.filter((b) => b.name !== name) });
  },
  setSystemPrompt: (prompt) => set({ systemPrompt: prompt }),
  setUploadFolder: (folder) => set({ uploadFolder: folder }),
  addUploadedTestFiles: (filenames) =>
    set((state) => ({
      uploadedTestFiles: [...state.uploadedTestFiles, ...filenames],
    })),
  clearUploadedTestFiles: () => set({ uploadedTestFiles: [], uploadFolder: "" }),

  setExecutionStatus: (status) => set({ executionStatus: status }),

  handleWSMessage: (msg) => {
    switch (msg.type) {
      case "execution_started":
        set({
          executionStatus: "running",
          totalTests: msg.total_tests,
        });
        break;
      case "test_status":
        set((state) => ({
          testStatuses: {
            ...state.testStatuses,
            [msg.test_id]: {
              test_id: msg.test_id,
              test_title: msg.test_title,
              status: msg.status,
              current_step: msg.current_step || 0,
              total_steps: msg.total_steps || 0,
              last_action: msg.last_action || "",
              error: msg.error || null,
            },
          },
        }));
        break;
      case "step_update": {
        const entry: TrajectoryEntry = {
          action: msg.action,
          detail: msg.action_detail,
          status: msg.status as TrajectoryEntry["status"],
          timestamp: msg.timestamp,
          error: msg.error || undefined,
        };
        set((state) => {
          const prev = state.testTrajectories[msg.test_id] || [];
          // If the new entry is passed/failed and the last entry was
          // "executing" for the same action, replace it instead of appending.
          let updated: TrajectoryEntry[];
          const last = prev[prev.length - 1];
          if (
            last &&
            last.status === "executing" &&
            last.action === entry.action &&
            (entry.status === "passed" || entry.status === "failed")
          ) {
            updated = [...prev.slice(0, -1), entry];
          } else {
            updated = [...prev, entry];
          }
          return {
            testTrajectories: {
              ...state.testTrajectories,
              [msg.test_id]: updated,
            },
          };
        });
        break;
      }
      case "execution_complete":
        set({
          executionStatus: "completed",
          passedCount: msg.passed,
          failedCount: msg.failed,
          skippedCount: msg.skipped,
        });
        break;
    }
  },

  reset: () => set(initialState),
}));
