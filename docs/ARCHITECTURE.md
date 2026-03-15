# QA Agent - System Architecture

## Overview

QA Agent is an AI-powered application that reads QA test documents (.docx), extracts test cases, and executes them on web applications using Playwright browser automation — mimicking human QA testing. It uses LLM models (OpenAI GPT-4o by default, extensible to any provider via LiteLLM) as the reasoning engine to interpret test steps and drive browser actions.

## High-Level Architecture

```
                     +-----------------------+
                     |      Frontend (UI)    |
                     |    Next.js / React    |
                     +----------+------------+
                                |
                     HTTP REST + WebSocket
                                |
                     +----------v------------+
                     |    Backend (API)      |
                     |      FastAPI          |
                     |                       |
                     |  - File Upload        |
                     |  - Session Mgmt       |
                     |  - Execution Orch.    |
                     |  - WebSocket Hub      |
                     +-----+-------+--------+
                           |       |
              +------------+       +-------------+
              |                                  |
   +----------v-----------+         +------------v----------+
   |   Document MCP       |         |   Playwright MCP      |
   |   Server (stdio)     |         |   Server (stdio)      |
   |                      |         |                       |
   | - Parse .docx        |         | - Browser launch      |
   | - Extract sections   |         | - Navigate/click/type |
   | - Extract test cases |         | - Screenshots         |
   | - Generate reports   |         | - Video recording     |
   +----------------------+         | - File upload/download|
                                    +-----------------------+
              +-------------------------------------------+
              |        AI Agent (LiteLLM / GPT-4o)        |
              |                                           |
              |  - Interprets test steps                  |
              |  - Plans browser actions                  |
              |  - Calls MCP tools                        |
              |  - Handles retries                        |
              |  - Reports status                         |
              +-------------------------------------------+
```

## Component Responsibilities

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| **Frontend** | Upload, configure, review, monitor, export | Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| **Backend API** | Orchestration, file management, session lifecycle | Python 3.12+, FastAPI, Uvicorn |
| **AI Agent** | Test interpretation, action planning, MCP tool invocation | LiteLLM, OpenAI GPT-4o (default), any LLM provider |
| **Document MCP Server** | .docx parsing, test case extraction, report generation | Python, `mcp` SDK (FastMCP), `python-docx` |
| **Playwright MCP Server** | Browser automation, screenshots, video, downloads | Python, `mcp` SDK (FastMCP), `playwright` |
| **WebSocket Hub** | Real-time status streaming to frontend | FastAPI WebSocket, `asyncio` |

## Key Architectural Decisions

### 1. Custom MCP Servers vs. Microsoft's Playwright MCP

**Decision**: Build custom Playwright MCP server.

**Why**: Microsoft's Playwright MCP is a Node.js server designed for Claude Desktop. We need: automatic screenshot saving per action, video recording per test case, file upload from configured folder, download saving to test-specific folder, and tight integration with our session/folder structure. A custom Python MCP server gives us full control and keeps the entire backend in one language.

### 2. LiteLLM for Provider-Agnostic Model Access

**Decision**: Use LiteLLM as the model abstraction layer instead of any single provider's SDK.

**Why**: LiteLLM provides a unified OpenAI-compatible interface to 100+ LLM providers (OpenAI, Anthropic, Google, Azure, etc.). This lets us default to OpenAI GPT-4o today while allowing users to switch to any model (Claude, Gemini, Llama, etc.) by changing a config value. LiteLLM handles the provider-specific API translation, so our agent loop code stays the same regardless of the underlying model. We get fine-grained control over the message loop for token budget management, selective screenshot inclusion, WebSocket status broadcasting, retry logic, and context window management.

### 3. One MCP Server Process Per Test Case

**Decision**: Spawn a new Playwright MCP server process for each parallel test case.

**Why**: Complete browser isolation (separate contexts, cookies, state). A crash in one test doesn't affect others. Video recording is cleanly scoped per test case. Kill the process and artifacts are in their folder.

### 4. Accessibility Snapshots as Primary Observation

**Decision**: Agent primarily uses text-based accessibility snapshots to understand page state; screenshots saved for the report.

**Why**: Accessibility snapshots are ~2-5KB text vs. ~100KB+ for base64 images. Including images in every LLM API call would 10-50x the token cost. The accessibility tree provides structured, reliable data for element identification. Screenshots are still captured and saved for every action — they go into the final report document. For tests requiring visual verification, the agent can explicitly request a screenshot in its context.

### 5. Separate YAML Config from Test Document

**Decision**: Keep credentials and inputs in a separate YAML file.

**Why**: Security (credentials should never be in shared test documents), flexibility (same test doc runs against different environments by swapping configs), and the YAML structure can be flexibly parsed by the agent.

### 6. Model Selection

**Decision**: Default to OpenAI GPT-4o for test execution, configurable to any LiteLLM-supported model.

**Why**: GPT-4o offers strong tool-use capabilities, good vision support, and competitive pricing. Most QA steps are straightforward. Users can switch to more capable models (GPT-4o, Claude Opus, Gemini Pro) for complex test suites or cheaper models (GPT-4o-mini) for simple ones — all by changing the `model` config value. The model name is recorded in the "Verified By" column of the report.
