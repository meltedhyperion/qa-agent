# QA Agent - UI Design & User Flow

## User Journey

```
Upload -> Review & Configure -> Execute & Monitor -> Results & Export
```

---

## Screen 1: Upload (Landing Page)

**Route**: `/`

### Layout

```
+-------------------------------------------------------------+
|  QA Agent                                                     |
+-------------------------------------------------------------+
|                                                               |
|   +---------------------------------------------+            |
|   |                                             |            |
|   |    Drop your test document here             |            |
|   |       or click to browse                    |            |
|   |                                             |            |
|   |    Accepts: .docx, .doc                     |            |
|   |                                             |            |
|   +---------------------------------------------+            |
|                                                               |
|   +---------------------------------------------+            |
|   |                                             |            |
|   |    Drop your configuration file here        |            |
|   |       or click to browse                    |            |
|   |                                             |            |
|   |    Accepts: .yaml, .yml (optional)          |            |
|   |                                             |            |
|   +---------------------------------------------+            |
|                                                               |
|   Parsing Guidance (optional):                                |
|   +---------------------------------------------+            |
|   | Help the AI find test cases in your document |            |
|   | e.g. "Test cases are in the tables starting  |            |
|   | from Section 3"                              |            |
|   +---------------------------------------------+            |
|   The AI will read your entire document and                   |
|   extract test cases. Add hints if the document               |
|   has an unusual format.                                      |
|                                                               |
|                        [ Parse & Continue ]                    |
|                                                               |
+-------------------------------------------------------------+
```

### Functionality

- Drag-and-drop zones for test document and configuration file
- File type validation (.docx/.doc and .yaml/.yml)
- Shows upload status with green border and file names when files selected
- Click-to-browse fallback for both zones
- **Parsing Guidance textarea**: Optional hints for the LLM on where to find test cases
  - Placeholder examples: "Test cases are in the tables starting from Section 3", "Each row is a test case with columns: S.No, Test Name, Steps, Expected Result", "Ignore the first 2 pages"
- Button shows "Parsing with AI..." during loading
- On submit: uploads document, uploads config (if provided), calls LLM parser with hints, navigates to review page

---

## Screen 2: Review & Configure

**Route**: `/sessions/[id]/review`

### Layout

```
+-----------------------------------------------------------------------+
|  QA Agent > Review                                       [<- Back]     |
+-----------------------------------------------------------------------+
|                                                                        |
|  +--- Configuration Panel ----------------------------------------+   |
|  |                                                                 |   |
|  |  Execution:  (*) Sequential  ( ) Parallel                      |   |
|  |  Concurrency: [3]                                               |   |
|  |  Model: [gpt-4o v]     Max Retries: [0]                        |   |
|  |                                                                 |   |
|  |  System prompt (optional):                                      |   |
|  |  +-----------------------------------------------------------+  |   |
|  |  | Start each test by logging in first...                     |  |   |
|  |  +-----------------------------------------------------------+  |   |
|  |                                                                 |   |
|  |  +--- Browsers -------------------------------------------+    |   |
|  |  |  [x] Chromium  [ ] Firefox  [ ] WebKit                 |    |   |
|  |  |  [ ] Chrome    [ ] Edge                                 |    |   |
|  |  |                                                         |    |   |
|  |  |  Custom Browsers:                                       |    |   |
|  |  |  Name: [Brave    ]  Path: [/Applications/Brave...] [+] |    |   |
|  |  |    Brave (/Applications/Brave Browser.app/...)  [x]     |    |   |
|  |  |                                                         |    |   |
|  |  |  [ Check Availability ]                                 |    |   |
|  |  |    Chromium: Available (bundled)                         |    |   |
|  |  |    Brave: Available                                     |    |   |
|  |  +----------------------------------------------------------+   |   |
|  |                                                                 |   |
|  |  +--- Test Files (for upload steps) ----------------------+    |   |
|  |  |  Drop files here or click to browse                     |    |   |
|  |  |  Uploaded: invoice.pdf, sample_data.csv                 |    |   |
|  |  |                                    [Clear All]          |    |   |
|  |  +----------------------------------------------------------+   |   |
|  |                                                                 |   |
|  |  Global Config:  App URL: https://staging.example.com           |   |
|  |                  Credentials: admin@example.com / ********      |   |
|  +------------------------------------------------------------------+  |
|                                                                        |
|  +--- Test Cases (12 found, 12 selected) --  [Select All] ----------+  |
|  |                                                                    |  |
|  |  +- TC-001 ----------------------------------------- [x] ------+ |  |
|  |  |  Login with valid credentials                                | |  |
|  |  |                                                              | |  |
|  |  |  Steps:                                                      | |  |
|  |  |  1. Navigate to login page                                   | |  |
|  |  |  2. Enter username                                           | |  |
|  |  |  3. Enter password                                           | |  |
|  |  |  4. Click Login button                                       | |  |
|  |  |  5. Verify dashboard is displayed                            | |  |
|  |  |                                                              | |  |
|  |  |  Expected: User is logged in and sees dashboard              | |  |
|  |  |  Config: credentials -> admin@example.com / ********         | |  |
|  |  +--------------------------------------------------------------+ |  |
|  |                                                                    |  |
|  |  (scrollable)                                                      |  |
|  +--------------------------------------------------------------------+  |
|                                                                        |
|            [ Run X Tests on Y Browsers (Z total runs) ]                |
|                                                                        |
+-----------------------------------------------------------------------+
```

### Functionality

- **Execution config**: Sequential/parallel toggle, concurrency (for parallel), model selector, max retries
- **System prompt**: Textarea for custom agent instructions
- **Browser selection**:
  - Checkboxes for standard browsers: chromium, firefox, webkit, chrome, msedge
  - Custom browser inputs: name + executable path with add/remove buttons
  - "Check Availability" button: calls `POST /api/sessions/check-browsers` and shows per-browser status (Available/Not found)
- **Test file upload widget**: Drag-and-drop area for uploading files the agent may need during test execution (e.g., file upload test steps). Shows list of uploaded files with clear button. Files are uploaded to the server and the `upload_folder` path is set automatically.
- **Global config display**: Shows parsed config values from YAML (app URL, credentials masked)
- **Test case cards**: Scrollable list, each card shows:
  - Test ID and title
  - Steps as numbered list
  - Expected result
  - Config values (global + test-specific overrides)
  - Checkbox to include/exclude
- **Select all / deselect all** toggle
- **Run button**: Shows total test count x browser count, triggers execution, navigates to execute page

---

## Screen 3: Execution Monitor

**Route**: `/sessions/[id]/execute`

### Layout

```
+-----------------------------------------------------------------------+
|  QA Agent > Execution                                      [Abort]     |
+-----------------------------------------------------------------------+
|                                                                        |
|  +--- Summary -------------------------------------------------------+|
|  |  Total: 12  |  Passed: 4  |  Failed: 1  |  Running: 3  |  Q: 4   ||
|  |  ================------------- 42%                                 ||
|  +--------------------------------------------------------------------+|
|                                                                        |
|  +--- Test Cases ----------------------------------------------------+|
|  |                                                                    ||
|  |  +- TC-001 (chromium) ----------------------------- PASSED -----+ ||
|  |  |  Login with valid credentials                                 | ||
|  |  |  Steps: 5/5 completed                                        | ||
|  |  |                                                               | ||
|  |  |  Trajectory:                                                  | ||
|  |  |  + navigate(https://www.saucedemo.com/)                       | ||
|  |  |  + type_text(#user-name, "standard_user")                     | ||
|  |  |  + type_text(#password, "secret_sauce")                       | ||
|  |  |  + click(#login-button)                                       | ||
|  |  |  + Verified: Products page is displayed                       | ||
|  |  +---------------------------------------------------------------+ ||
|  |                                                                    ||
|  |  +- TC-002 (chromium) ----------------------------- RUNNING ----+ ||
|  |  |  Create new order                                             | ||
|  |  |  Steps: 3/7                                                   | ||
|  |  |                                                               | ||
|  |  |  Trajectory:                                                  | ||
|  |  |  + navigate(https://app.example.com/orders)                   | ||
|  |  |  + click(text="New Order")                                    | ||
|  |  |  * type_text(#product, "Widget A")                            | ||
|  |  +---------------------------------------------------------------+ ||
|  |                                                                    ||
|  |  +- TC-003 (chromium) ----------------------------- FAILED -----+ ||
|  |  |  Upload invoice document                                      | ||
|  |  |  Steps: 3/5                                                   | ||
|  |  |                                                               | ||
|  |  |  Trajectory:                                                  | ||
|  |  |  + navigate(https://app.example.com/docs)                     | ||
|  |  |  + click(text="Upload")                                       | ||
|  |  |  x upload_file(#file-input, invoice.pdf)                      | ||
|  |  |    Error: File input not found on page                        | ||
|  |  +---------------------------------------------------------------+ ||
|  |                                                                    ||
|  |  +- TC-004 (chromium) ----------------------------- QUEUED -----+ ||
|  |  |  Verify search functionality                                  | ||
|  |  +---------------------------------------------------------------+ ||
|  |                                                                    ||
|  +--------------------------------------------------------------------+|
|                                                                        |
+-----------------------------------------------------------------------+
```

### Functionality

- **Summary bar**: Real-time counts of running/passed/failed/queued + progress bar
- **Test case cards**: Updated via WebSocket in real-time. Each card shows:
  - Test ID, browser name, title, and status badge
  - Step counter (X/Y completed)
  - **Real-time trajectory log**: Scrollable log of agent actions as they happen
    - `+` prefix: passed action
    - `x` prefix: failed action
    - `*` prefix: currently executing action
    - `~` prefix: agent thinking/reasoning
    - Each entry shows: action name with summarized arguments
    - "Executing" entries are replaced with final "passed"/"failed" when complete
    - Auto-scrolls to the latest entry
    - Error messages shown inline for failed actions
- **Abort button**: Stops all running tests
- Test titles resolved from parsed sections data (available even before WebSocket updates arrive)
- Auto-navigation to results page when execution completes

### Trajectory Entry Format

Each trajectory entry in the log contains:
- `action`: The tool/action name (e.g., "navigate", "click", "type_text") or "thinking" for LLM reasoning
- `detail`: Summarized arguments (e.g., `https://example.com` for navigate, `#login-btn` for click)
- `status`: "executing" (in progress), "passed" (succeeded), "failed" (error), "info" (reasoning)
- `timestamp`: ISO timestamp
- `error`: Error message if failed

---

## Screen 4: Results & Export

**Route**: `/sessions/[id]/results`

### Layout

```
+-----------------------------------------------------------------------+
|  QA Agent > Results                                                    |
+-----------------------------------------------------------------------+
|                                                                        |
|  +--- Summary -------------------------------------------------------+|
|  |  Total: 12  |  Passed: 10  |  Failed: 1  |  Skipped: 1            ||
|  |  Duration: 8m 32s  |  Model: GPT-4o                               ||
|  +--------------------------------------------------------------------+|
|                                                                        |
|  +--- Export ---------------------------------------------------------+|
|  |  [ Download Results Report (.docx) ]                               ||
|  |  [ Download Full Session (ZIP) ]                                   ||
|  +--------------------------------------------------------------------+|
|                                                                        |
|  +--- Test Results ---------------------------------------------------+|
|  |                                                                     ||
|  |  +- TC-001 (chromium) ----------------------------- PASSED ------+ ||
|  |  |  Login with valid credentials                                  | ||
|  |  |                                                                | ||
|  |  |  Steps:                                                        | ||
|  |  |  [PASS] 1. Navigate to login page                              | ||
|  |  |  [PASS] 2. Enter username                                      | ||
|  |  |  [PASS] 3. Enter password                                      | ||
|  |  |  [PASS] 4. Click Login button                                  | ||
|  |  |  [PASS] 5. Verify dashboard is displayed                       | ||
|  |  |                                                                | ||
|  |  |  Summary: All steps completed successfully.                    | ||
|  |  |  [View Screenshots]                                            | ||
|  |  +----------------------------------------------------------------+ ||
|  |                                                                     ||
|  |  +- TC-003 (chromium) ----------------------------- FAILED ------+ ||
|  |  |  Upload invoice document                                       | ||
|  |  |                                                                | ||
|  |  |  Steps:                                                        | ||
|  |  |  [PASS] 1. Navigate to documents page                          | ||
|  |  |  [PASS] 2. Click Upload button                                 | ||
|  |  |  [PASS] 3. Select file type                                    | ||
|  |  |  [FAIL] 4. Attach invoice.pdf - Upload button not found        | ||
|  |  |  [SKIP] 5. Verify upload confirmation                          | ||
|  |  |                                                                | ||
|  |  |  Summary: Failed at step 4: could not find file input.         | ||
|  |  |  [View Screenshots]                                            | ||
|  |  +----------------------------------------------------------------+ ||
|  |                                                                     ||
|  +--------------------------------------------------------------------+|
+-----------------------------------------------------------------------+
```

### Functionality

- **Summary**: Final counts (passed/failed/skipped), total duration, model used
- **Export buttons**:
  - Download Results Report: formatted .docx with 4-column table (Test Title | Steps | Screenshots | Verified By)
  - Download Full Session: ZIP containing all folders (screenshots, recordings, downloads)
- **Test result cards**: Each card shows:
  - Test ID, browser, title, status badge
  - Step-by-step results with pass/fail/skip indicators
  - Summary text from the agent
  - View Screenshots button to see captured screenshots
  - Error details for failed steps

---

## UI Component Library

Using **shadcn/ui** for consistent, accessible components:

- `Card` - Test case cards, configuration panels
- `Button` - Actions (Run, Export, Abort, Check Availability)
- `Badge` - Status indicators (Passed, Failed, Running, Queued, Skipped)
- `Progress` - Execution progress bar
- `Select` - Model selector, concurrency selector
- `Textarea` - System prompt editor, parsing hints
- `Input` - Custom browser name and path inputs
- `Dialog` - Screenshot gallery
- `ScrollArea` - Test case list scrolling, trajectory logs
- `Tabs` - Section tabs if multiple sections
- `RadioGroup` - Parallel/sequential toggle
- `Checkbox` - Test case selection, browser selection
- `Separator` - Visual dividers between sections

---

## State Management

Using **Zustand** for client-side state:

```typescript
interface SessionStore {
  // Session data
  sessionId: string | null;
  documentName: string | null;
  configName: string | null;

  // Parsed data
  parsedData: {
    documentTitle: string;
    sections: Section[];
    config: TestConfig | null;
  } | null;

  // Review state
  selectedSections: string[];
  selectedTestIds: string[];
  executionMode: "parallel" | "sequential";
  concurrency: number;
  model: string;
  systemPrompt: string;
  maxRetries: number;
  browsers: string[];

  // Custom browsers
  customBrowsers: CustomBrowser[];   // {name, executable_path}
  addCustomBrowser: (browser: CustomBrowser) => void;
  removeCustomBrowser: (index: number) => void;

  // Test file uploads
  uploadedTestFiles: string[];
  uploadFolder: string | null;
  addUploadedTestFiles: (files: string[]) => void;
  clearUploadedTestFiles: () => void;

  // Execution state
  testStatuses: Record<string, TestStatus>;
  testTrajectories: Record<string, TrajectoryEntry[]>;

  // Results
  results: TestResult[];

  // WebSocket message handler
  handleWSMessage: (msg: WSMessage) => void;
}

interface TrajectoryEntry {
  action: string;
  detail: string;
  status: "executing" | "passed" | "failed" | "info";
  timestamp: string;
  error?: string | null;
}
```

### WebSocket Hook

```typescript
function useExecutionWebSocket(sessionId: string) {
  const handleWSMessage = useSessionStore(s => s.handleWSMessage);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/sessions/${sessionId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleWSMessage(data);
    };

    // Keep-alive ping every 30 seconds
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      ws.close();
    };
  }, [sessionId]);
}
```

### WebSocket Message Handling

The store's `handleWSMessage` processes typed messages:

- `execution_started`: Initializes test status tracking
- `test_status`: Updates per-test status (running/passed/failed/queued), step counters, errors
- `step_update`: Appends to or updates trajectory log entries
  - New "executing" entries are appended
  - When a "passed" or "failed" update arrives, it replaces the matching "executing" entry
- `execution_complete`: Sets final state, stores summary counts
