# QA Agent

AI-powered QA testing agent that reads test documents (.docx), extracts test cases using LLM-powered parsing, and executes them on web applications using Playwright browser automation.

## Tech Stack

- **Frontend**: Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Zustand
- **Backend**: Python 3.12+, FastAPI, Uvicorn
- **AI**: LiteLLM (provider-agnostic), OpenAI GPT-4o (default), extensible to any LLM provider
- **Browser Automation**: Playwright (Python) — supports Chromium, Firefox, WebKit, Chrome, Edge, and custom browsers
- **Document Handling**: python-docx (read + write)
- **MCP Servers**: Custom stdio-based MCP servers using Python `mcp` SDK (FastMCP)
- **Config**: YAML (PyYAML), with LLM-powered parsing for non-standard formats

## Project Structure

```
qa-agent/
├── frontend/                  # Next.js application
│   └── src/
│       ├── app/               # Pages (upload, review, execute, results)
│       ├── components/ui/     # shadcn/ui components
│       └── lib/               # API client, Zustand store, types, websocket
├── backend/                   # FastAPI application
│   ├── api/                   # REST endpoints + WebSocket hub
│   │   ├── routes/            # upload, sessions, execution, export
│   │   └── websocket.py       # WebSocket connection manager
│   ├── core/                  # Core logic
│   │   ├── agent.py           # AI agent loop with trajectory broadcasting
│   │   ├── orchestrator.py    # Multi-browser execution orchestrator
│   │   ├── llm_parser.py      # LLM-powered document and config parsing
│   │   ├── browser_check.py   # Pre-flight browser availability checks
│   │   ├── prompt_builder.py  # System prompt construction
│   │   ├── config_parser.py   # Rigid YAML config parser (standard format)
│   │   ├── mcp_client.py      # MCP stdio client wrapper
│   │   ├── session.py         # In-memory session store
│   │   └── models.py          # Pydantic models + WS message types
│   └── mcp_servers/           # Custom MCP servers
│       ├── document/          # Document parsing + report generation
│       └── playwright_browser/ # Browser automation
├── tests/fixtures/            # Sample test documents and configs
├── exports/                   # Runtime output (gitignored)
├── uploads/                   # Runtime uploads (gitignored)
└── docs/                      # Detailed documentation
```

## Documentation

- `docs/ARCHITECTURE.md` — System architecture, components, and key decisions
- `docs/REQUIREMENTS.md` — Functional and non-functional requirements
- `docs/TECHNICAL_DESIGN.md` — Data flow, API design, data models, error handling
- `docs/MCP_SERVERS.md` — MCP server specifications (Document + Playwright)
- `docs/UI_DESIGN.md` — UI screens, user flow, state management
- `docs/AGENT_DESIGN.md` — AI agent reasoning loop, prompt design, selector strategy

## Key Concepts

- **Session**: One test run lifecycle (upload -> parse -> configure -> execute -> results)
- **LLM Parser**: Extracts test cases from any document format using LLM intelligence; accepts parsing hints
- **Document MCP**: Generates formatted result reports (.docx with embedded screenshots)
- **Playwright MCP**: Browser automation, one instance per test case for isolation
- **Agent Loop**: LLM tool-use loop that interprets test steps and calls MCP tools, with real-time trajectory broadcasting
- **Accessibility-first**: Agent uses accessibility snapshots (text) as primary observation; screenshots saved to disk for reports
- **Multi-browser**: Tests run across all selected browsers (standard + custom), with pre-flight availability checks
- **BrowserRun**: Orchestrator concept combining browser name, type, and optional executable path
- **Trajectory Tracking**: Per-test step log with executing -> passed/failed state transitions, streamed via WebSocket

## Running

```bash
# Backend
cd backend && uvicorn main:app --port 8000 --reload

# Frontend
cd frontend && npm run dev
```

Requires a `.env` file with at least `OPENAI_API_KEY` set (see `.env.example`).
