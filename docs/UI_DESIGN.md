# QA Agent - UI Design & User Flow

## User Journey

```
Upload → Review → Configure → Execute → Monitor → Results → Export
```

---

## Screen 1: Upload (Landing Page)

**Route**: `/`

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  QA Agent                                            [logo] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────────────────────────────────┐           │
│   │                                             │           │
│   │    📄 Drop your test document here          │           │
│   │       or click to browse                    │           │
│   │                                             │           │
│   │    Accepts: .docx, .doc                     │           │
│   │                                             │           │
│   └─────────────────────────────────────────────┘           │
│                                                             │
│   ┌─────────────────────────────────────────────┐           │
│   │                                             │           │
│   │    ⚙️  Drop your configuration file here     │           │
│   │       or click to browse                    │           │
│   │                                             │           │
│   │    Accepts: .yaml, .yml                     │           │
│   │                                             │           │
│   └─────────────────────────────────────────────┘           │
│                                                             │
│   Both files uploaded: ✓ test_suite.docx  ✓ config.yaml    │
│                                                             │
│                              [ Parse & Continue → ]         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Functionality
- Drag-and-drop zones for test document and config file
- File type validation (.docx/.doc and .yaml/.yml)
- Shows upload status with file names
- "Parse & Continue" button triggers document parsing and navigates to review

---

## Screen 2: Review & Configure

**Route**: `/sessions/[id]/review`

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  QA Agent  >  Session #abc123                          [← Back]     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─── Configuration Panel ────────────────────────────────────────┐ │
│  │                                                                │ │
│  │  Section to run: [Progressive Tests ▼]                         │ │
│  │                                                                │ │
│  │  Execution:  ○ Sequential  ● Parallel                         │ │
│  │  Concurrency: [3 ▼]                                           │ │
│  │                                                                │ │
│  │  Upload folder: [/Users/user/test-files    ] [Browse]          │ │
│  │                                                                │ │
│  │  System prompt (optional):                                     │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │ Start each test by logging in first. Use slow typing...  │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                │ │
│  │  Global config:  App URL: https://staging.example.com          │ │
│  │                  Credentials: admin@example.com / ••••••••     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─── Test Cases (12 found, 12 selected) ─────────────────────────┐│
│  │                                                                 ││
│  │  ┌─ TC-001 ──────────────────────────────────────── [☑] ────┐  ││
│  │  │  Login with valid credentials                             │  ││
│  │  │                                                           │  ││
│  │  │  Steps:                                                   │  ││
│  │  │  1. Navigate to login page                                │  ││
│  │  │  2. Enter username                                        │  ││
│  │  │  3. Enter password                                        │  ││
│  │  │  4. Click Login button                                    │  ││
│  │  │  5. Verify dashboard is displayed                         │  ││
│  │  │                                                           │  ││
│  │  │  Config: credentials → admin@example.com / ••••••••       │  ││
│  │  └───────────────────────────────────────────────────────────┘  ││
│  │                                                                 ││
│  │  ┌─ TC-002 ──────────────────────────────────────── [☑] ────┐  ││
│  │  │  Create new order                                         │  ││
│  │  │  ...                                                      │  ││
│  │  └───────────────────────────────────────────────────────────┘  ││
│  │                                                                 ││
│  │  (scrollable)                                                   ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│                                    [ ▶ Run Tests ]                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Functionality
- **Section selector**: Dropdown to pick which section(s) of the test doc to run
- **Execution config**: Parallel/sequential toggle, concurrency slider
- **Upload folder**: Path input with browse button for selecting the folder with test files
- **System prompt**: Textarea for custom agent instructions
- **Global config display**: Shows parsed config values (credentials masked)
- **Test case cards**: Scrollable list, each card shows:
  - Test ID and title
  - Steps as numbered list
  - Config values that will be used (global + test-specific overrides)
  - Checkbox to include/exclude
- **Select all / deselect all** toggle
- **Run Tests** button: triggers execution, navigates to monitor screen

---

## Screen 3: Execution Monitor

**Route**: `/sessions/[id]/execute`

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  QA Agent  >  Session #abc123  >  Execution              [Abort ■] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─── Summary ─────────────────────────────────────────────────┐   │
│  │  Total: 12  │  Running: 3  │  Passed: 4  │  Failed: 1  │  Q: 4│  │
│  │  ████████████████████░░░░░░░░░░░░░░░░░░░  42%                │  │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── Test Cases ──────────────────────────────────────────────────┐│
│  │                                                                  ││
│  │  ┌─ TC-001 ─────────────────────────────────── ✅ PASSED ────┐ ││
│  │  │  Login with valid credentials                              │ ││
│  │  │  Steps: 5/5 completed  │  Duration: 45s                   │ ││
│  │  └────────────────────────────────────────────────────────────┘ ││
│  │                                                                  ││
│  │  ┌─ TC-002 ─────────────────────────────────── 🔄 RUNNING ───┐ ││
│  │  │  Create new order                                          │ ││
│  │  │  Step 3/7: Filling in order form...                        │ ││
│  │  │  Last action: type_text → "Widget A" into product field    │ ││
│  │  │  ┌────────────────────────────────────────────────────┐    │ ││
│  │  │  │                                                    │    │ ││
│  │  │  │         [Latest screenshot preview]                │    │ ││
│  │  │  │                                                    │    │ ││
│  │  │  └────────────────────────────────────────────────────┘    │ ││
│  │  └────────────────────────────────────────────────────────────┘ ││
│  │                                                                  ││
│  │  ┌─ TC-003 ─────────────────────────────────── ❌ FAILED ────┐ ││
│  │  │  Upload invoice document                                   │ ││
│  │  │  Failed at step 4: Could not find upload button            │ ││
│  │  │  Retries: 3/3 exhausted                                    │ ││
│  │  └────────────────────────────────────────────────────────────┘ ││
│  │                                                                  ││
│  │  ┌─ TC-004 ─────────────────────────────────── ⏳ QUEUED ────┐ ││
│  │  │  Verify search functionality                               │ ││
│  │  └────────────────────────────────────────────────────────────┘ ││
│  │                                                                  ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Functionality
- **Summary bar**: Real-time counts of running/passed/failed/queued + progress bar
- **Test case cards**: Updated via WebSocket in real-time
  - Running tests show: current step, last action, latest screenshot preview
  - Passed tests show: completion time, step count
  - Failed tests show: failure step, error message, retry count
  - Queued tests show: waiting indicator
- **Abort button**: Stops all running tests
- **Auto-scrolls** to show running tests
- Cards are expandable to show full step-by-step timeline

---

## Screen 4: Results & Export

**Route**: `/sessions/[id]/results`

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  QA Agent  >  Session #abc123  >  Results                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─── Summary ─────────────────────────────────────────────────┐   │
│  │  Total: 12  │  Passed: 10  │  Failed: 1  │  Skipped: 1       │  │
│  │  Duration: 8m 32s  │  Model: GPT-4o                           │  │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── Export Options ──────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  [ 📄 Download Results Report (.docx) ]                     │    │
│  │  [ 📦 Download Full Session (ZIP) ]                         │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─── Test Results ───────────────────────────────────────────────┐ │
│  │                                                                 │ │
│  │  ┌─ TC-001 ─────────────────────────────────── ✅ PASSED ────┐│ │
│  │  │  Login with valid credentials                              ││ │
│  │  │                                                            ││ │
│  │  │  Steps:                                                    ││ │
│  │  │  ✅ 1. Navigate to login page                              ││ │
│  │  │  ✅ 2. Enter username                                      ││ │
│  │  │  ✅ 3. Enter password                                      ││ │
│  │  │  ✅ 4. Click Login button                                  ││ │
│  │  │  ✅ 5. Verify dashboard is displayed                       ││ │
│  │  │                                                            ││ │
│  │  │  [View Screenshots]  [Watch Recording]  [Downloads (0)]    ││ │
│  │  └────────────────────────────────────────────────────────────┘│ │
│  │                                                                 │ │
│  │  ┌─ TC-003 ─────────────────────────────────── ❌ FAILED ────┐│ │
│  │  │  Upload invoice document                                   ││ │
│  │  │                                                            ││ │
│  │  │  Steps:                                                    ││ │
│  │  │  ✅ 1. Navigate to documents page                          ││ │
│  │  │  ✅ 2. Click Upload button                                 ││ │
│  │  │  ✅ 3. Select file type                                    ││ │
│  │  │  ❌ 4. Attach invoice.pdf - FAILED: Upload button not found││ │
│  │  │  ⏭️ 5. Verify upload confirmation - SKIPPED                ││ │
│  │  │                                                            ││ │
│  │  │  [View Screenshots]  [Watch Recording]  [Downloads (0)]    ││ │
│  │  └────────────────────────────────────────────────────────────┘│ │
│  │                                                                 │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Functionality
- **Summary**: Final counts, total duration, model used
- **Export buttons**:
  - Download Results Report: the formatted .docx with the 4-column table
  - Download Full Session: ZIP containing all folders (recordings, screenshots, downloads)
- **Test result cards**: Expandable, showing:
  - Step-by-step results with pass/fail/skip indicators
  - View Screenshots: opens a lightbox/gallery of all screenshots for this test
  - Watch Recording: opens video player with the test run recording
  - Downloads: lists any files downloaded during the test

---

## UI Component Library

Using **shadcn/ui** for consistent, accessible components:

- `Card` - Test case cards
- `Button` - Actions (Run, Export, Abort)
- `Badge` - Status indicators (Passed, Failed, Running)
- `Progress` - Execution progress bar
- `Select` - Section selector, concurrency selector
- `Textarea` - System prompt editor
- `Dialog` - Screenshot gallery, video player
- `ScrollArea` - Test case list scrolling
- `Tabs` - Section tabs if multiple sections
- `RadioGroup` - Parallel/sequential toggle
- `Checkbox` - Test case selection
- `DropZone` - File upload areas (custom component)

---

## State Management

Using **Zustand** for client-side state:

```typescript
interface SessionStore {
  // Session data
  sessionId: string | null;
  document: ParsedDocument | null;
  config: TestConfig | null;

  // Review state
  selectedSections: string[];
  selectedTestIds: string[];
  executionMode: 'parallel' | 'sequential';
  concurrency: number;
  systemPrompt: string;
  uploadFolder: string;

  // Execution state
  executionStatus: 'idle' | 'running' | 'completed' | 'aborted';
  testStatuses: Record<string, TestStatus>;

  // Results
  results: TestResult[];

  // Actions
  setDocument: (doc: ParsedDocument) => void;
  toggleTestCase: (testId: string) => void;
  updateTestStatus: (testId: string, status: TestStatus) => void;
  // ...
}
```

### WebSocket Hook

```typescript
function useExecutionWebSocket(sessionId: string) {
  const updateTestStatus = useSessionStore(s => s.updateTestStatus);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/sessions/${sessionId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'test_status':
          updateTestStatus(data.test_id, data);
          break;
        case 'step_update':
          // Update step-level detail
          break;
        case 'execution_complete':
          // Navigate to results or update UI
          break;
      }
    };

    return () => ws.close();
  }, [sessionId]);
}
```
