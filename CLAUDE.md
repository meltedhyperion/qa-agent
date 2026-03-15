# QA Agent

AI-powered QA testing agent that reads test documents (.docx), extracts test cases, and executes them on web applications using Playwright browser automation.

## Tech Stack

- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui, Zustand
- **Backend**: Python 3.12+, FastAPI, Uvicorn
- **AI**: LiteLLM (provider-agnostic), OpenAI GPT-4o (default), extensible to any LLM provider
- **Browser Automation**: Playwright (Python)
- **Document Handling**: python-docx (read + write)
- **MCP Servers**: Custom stdio-based MCP servers using Python `mcp` SDK (FastMCP)
- **LLM Abstraction**: LiteLLM (unified interface to OpenAI, Anthropic, Google, Azure, etc.)
- **Config**: YAML (PyYAML)

## Project Structure

```
qa-agent/
├── frontend/          # Next.js application
├── backend/           # FastAPI application
│   ├── api/           # REST + WebSocket endpoints
│   ├── core/          # Agent, orchestrator, session management
│   └── mcp_servers/   # Document and Playwright MCP servers
├── exports/           # Runtime output (gitignored)
├── uploads/           # Runtime uploads (gitignored)
├── tests/             # Test suite
└── docs/              # Documentation
```

## Documentation

- `docs/ARCHITECTURE.md` - System architecture and key decisions
- `docs/REQUIREMENTS.md` - Functional and non-functional requirements
- `docs/TECHNICAL_DESIGN.md` - Data flow, API design, data models, error handling
- `docs/MCP_SERVERS.md` - MCP server specifications (Document + Playwright)
- `docs/UI_DESIGN.md` - UI screens, user flow, component design
- `docs/AGENT_DESIGN.md` - AI agent reasoning loop, prompt design, selector strategy

## Key Concepts

- **Session**: One test run lifecycle (upload → parse → configure → execute → results)
- **Document MCP**: Parses .docx test docs, generates result reports
- **Playwright MCP**: Browser automation, one instance per test case for isolation
- **Agent Loop**: LLM tool-use loop that interprets test steps and calls MCP tools
- **Accessibility-first**: Agent uses accessibility snapshots (text) as primary observation; screenshots saved to disk for reports
