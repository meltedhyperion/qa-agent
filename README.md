# QA Agent

## Description

AI-powered QA testing agent that reads test documents (.docx), extracts test cases using LLM, and executes them on web applications using Playwright browser automation. It interprets human-written test steps and autonomously drives the browser -- clicking, typing, navigating, and verifying outcomes.

## Key Features

- LLM-powered document parsing (handles any format -- tables, paragraphs, numbered lists, mixed content)
- Parsing hints for unconventional documents
- Multi-browser support (Chromium, Firefox, WebKit, Chrome, Edge, custom/enterprise browsers)
- Pre-flight browser availability checks
- Parallel or sequential test execution
- Real-time execution monitoring with per-test trajectory logs via WebSocket
- Automated report generation (.docx with embedded screenshots)
- Full session export (ZIP with screenshots, videos, downloads)
- LLM-powered config parsing (any YAML format)
- Cross-platform (macOS, Windows, Linux)
- Provider-agnostic LLM support via LiteLLM (OpenAI, Anthropic, Google, Azure, etc.)

## Tech Stack

- **Frontend**: Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Zustand
- **Backend**: Python 3.12+, FastAPI, Uvicorn
- **AI**: LiteLLM (GPT-4o default, any provider)
- **Browser Automation**: Playwright
- **Document Handling**: python-docx
- **MCP Servers**: Custom stdio-based via Python mcp SDK (FastMCP)

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- An LLM API key (OpenAI by default, or any LiteLLM-supported provider)

## Setup Instructions

### macOS

```bash
# Clone the repository
git clone https://github.com/meltedhyperion/qa-tester.git
cd qa-tester

# Backend setup
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install Playwright browsers
playwright install

# Configure environment
cp ../.env.example ../.env
# Edit ../.env and add your OPENAI_API_KEY (or other provider key)

# Start the backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

### Windows

```powershell
# Clone the repository
git clone https://github.com/meltedhyperion/qa-tester.git
cd qa-tester

# Backend setup
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .

# Install Playwright browsers
playwright install

# Configure environment
copy ..\.env.example ..\.env
# Edit ..\.env and add your OPENAI_API_KEY (or other provider key)

# Start the backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

### Linux

```bash
# Clone the repository
git clone https://github.com/meltedhyperion/qa-tester.git
cd qa-tester

# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv nodejs npm

# Backend setup
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install Playwright browsers and system deps
playwright install
playwright install-deps

# Configure environment
cp ../.env.example ../.env
# Edit ../.env and add your OPENAI_API_KEY (or other provider key)

# Start the backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required if using GPT models) | -- |
| `ANTHROPIC_API_KEY` | Anthropic API key (optional, for Claude models) | -- |
| `GEMINI_API_KEY` | Google API key (optional, for Gemini models) | -- |
| `AZURE_API_KEY` | Azure OpenAI key (optional) | -- |
| `AZURE_API_BASE` | Azure OpenAI endpoint (optional) | -- |
| `DEFAULT_MODEL` | Default LLM model identifier | `gpt-4o` |
| `BACKEND_PORT` | Backend server port | `8000` |
| `FRONTEND_PORT` | Frontend dev server port | `3000` |

## Usage

1. Open http://localhost:3000 in your browser
2. Upload a test document (.docx) and optionally a configuration file (.yaml)
3. Optionally provide parsing hints (e.g., "Test cases are in Section 3 tables")
4. Click "Parse & Continue" -- the LLM extracts test cases from your document
5. Review extracted test cases, select browsers, configure execution settings
6. Click "Run Tests" to start execution
7. Monitor real-time progress with per-test trajectory logs
8. Download the results report (.docx) or full session export (ZIP)

## Project Structure

```
qa-agent/
├── frontend/                  # Next.js application
│   └── src/
│       ├── app/               # Pages (upload, review, execute, results)
│       ├── components/ui/     # shadcn/ui components
│       └── lib/               # API client, store, types, websocket
├── backend/                   # FastAPI application
│   ├── api/                   # REST + WebSocket endpoints
│   ├── core/                  # Agent, orchestrator, parsers, models
│   └── mcp_servers/           # Document and Playwright MCP servers
├── tests/fixtures/            # Sample test documents and configs
├── docs/                      # Detailed documentation
├── .env.example               # Environment template
└── .gitignore
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) -- System design and key decisions
- [Technical Design](docs/TECHNICAL_DESIGN.md) -- Data flow, API design, data models
- [MCP Servers](docs/MCP_SERVERS.md) -- Document and Playwright server specs
- [Agent Design](docs/AGENT_DESIGN.md) -- AI agent loop, prompt design, selectors
- [UI Design](docs/UI_DESIGN.md) -- Screens, user flow, state management
- [Requirements](docs/REQUIREMENTS.md) -- Functional and non-functional requirements

## Supported Browsers

| Browser | Type | Notes |
|---------|------|-------|
| Chromium | Bundled | Always available (installed with Playwright) |
| Firefox | Bundled | Always available |
| WebKit | Bundled | Always available |
| Chrome | Branded | Requires Chrome installed on the system |
| Edge | Branded | Requires Edge installed on the system |
| Custom | Enterprise | Any Chromium-based browser via executable path (Brave, Arc, Island, etc.) |

## Sample Files

The `tests/fixtures/` directory contains sample files for testing:

- `sample_test_doc.docx` -- Standard table-based test document
- `sample_test_doc_paragraph_steps.docx` -- Test document with paragraph-style steps
- `sample_test_doc_unstructured.docx` -- Unstructured document with business context + test cases
- `sample_config.yaml` -- Sample YAML configuration
