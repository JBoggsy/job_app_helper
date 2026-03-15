# Development Guide

This document provides comprehensive technical documentation for developers and contributors working on the Shortlist project.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Development Setup](#development-setup)
- [API Reference](#api-reference)
- [Database Models](#database-models)
- [LLM Provider System](#llm-provider-system)
- [Agent System](#agent-system)
- [Development Conventions](#development-conventions)
- [Telemetry System](#telemetry-system)
- [Testing](#testing)
- [Deployment](#deployment)

## Architecture Overview

The Shortlist is built as a full-stack web application with a clear separation between frontend and backend:

- **Backend (Flask)**: Provides REST API and Server-Sent Events (SSE) streaming for real-time AI responses. Handles data persistence via SQLAlchemy/SQLite and orchestrates the AI agent system.
- **Frontend (React + Vite)**: Single-page application that consumes the backend API. Uses Tailwind CSS for styling and includes real-time chat with SSE streaming.
- **Desktop (Tauri v2, Optional)**: Native desktop wrapper using the sidecar approach — Tauri renders the React frontend in a native webview and launches Flask as a child process. The existing browser-based workflow is preserved as a fallback.
- **AI Agent**: Tool-calling agent that can search the web, scrape URLs, search job boards, and manage job records. Supports multiple LLM providers (Anthropic, OpenAI, Gemini, Ollama).
- **User Profile System**: Markdown-based user profile with YAML frontmatter. Includes onboarding flow with a dedicated agent that interviews users to build their profile.
- **Data Directory Abstraction**: All data files (app.db, config.json, logs/, user_profile.md) are resolved via `backend/data_dir.get_data_dir()`. Defaults to `user_data/`; overridden by the `DATA_DIR` environment variable (set automatically by Tauri to its appDataDir).

## Tech Stack

### Backend
- **Python 3.12+**: Core language
- **Flask**: Web framework with blueprints for route organization
- **Flask-SQLAlchemy**: ORM for database interactions
- **SQLite**: Development database (easily swappable for PostgreSQL/MySQL in production)
- **LiteLLM**: Unified LLM interface — single `litellm.completion()` call works across all providers (Anthropic, OpenAI, Gemini, Ollama, and 100+ more)
- **uv**: Fast Python package manager

### LLM Providers
- **Anthropic Claude**: Default provider (`claude-sonnet-4-5-20250929`)
- **OpenAI GPT**: Alternative provider (`gpt-4o`)
- **Google Gemini**: Alternative provider (`gemini-2.0-flash`)
- **Ollama**: Local model provider (default: `llama3.1`)

### Agent Tools
- **Tavily API**: Web search integration
- **RapidAPI** (JSearch, Active Jobs DB, LinkedIn Job Search): Job board search (optional)
- **cloudscraper + BeautifulSoup**: Web scraping with Cloudflare bypass and HTML parsing (falls back to Tavily Extract API on failure)

### Frontend
- **React 19**: UI library with functional components and hooks
- **Vite**: Build tool and dev server with HMR
- **Tailwind CSS 4**: Utility-first CSS framework
- **npm**: Package manager

### Desktop (Optional)
- **Tauri v2**: Native desktop wrapper with webview
- **tauri-plugin-shell**: Sidecar process management for Flask backend
- **tauri-plugin-updater**: Auto-update checking and installation
- **tauri-plugin-process**: Process restart after update
- **PyInstaller**: Bundles Flask backend as standalone binary for distribution

## Project Structure

```
shortlist/
├── backend/
│   ├── app.py                      # Flask app factory (create_app)
│   ├── config.py                   # Configuration class with config file + env vars
│   ├── config_manager.py           # Config file read/write utilities
│   ├── data_dir.py                 # Centralized data directory resolver (DATA_DIR)
│   ├── database.py                 # SQLAlchemy db instance
│   ├── models/
│   │   ├── __init__.py            # Model exports
│   │   ├── job.py                 # Job model with CRUD methods
│   │   ├── chat.py                # Conversation and Message models
│   │   ├── search_result.py       # SearchResult model (per-conversation job search results)
│   │   ├── job_document.py        # JobDocument model (versioned cover letters/resumes per job)
│   │   └── application_todo.py    # ApplicationTodo model (per-job application steps)
│   ├── resume_parser.py           # Resume parsing (PDF via PyMuPDF, DOCX via python-docx), parsed JSON storage
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── jobs.py                # CRUD endpoints for jobs and application todos
│   │   ├── chat.py                # Chat endpoints with SSE streaming
│   │   ├── profile.py             # User profile endpoints
│   │   ├── resume.py              # Resume upload, fetch, delete, LLM parse endpoints
│   │   ├── config.py              # Config and health check endpoints
│   │   └── job_documents.py       # Per-job document version endpoints
│   ├── llm/
│   │   ├── llm_factory.py         # create_llm_config() — returns LLMConfig for litellm.completion()
│   │   └── model_listing.py       # list_models() per provider, MODEL_LISTERS registry
│   ├── telemetry/
│   │   ├── __init__.py            # Package exports (init/get/shutdown collector)
│   │   ├── collector.py           # TelemetryCollector singleton with background writer
│   │   ├── context.py             # contextvars propagation (run_id, trace_id), telemetry_run()
│   │   ├── traced_module.py       # TracedModule mixin for DSPy modules
│   │   ├── decorators.py          # @traced_workflow decorator (auto-applied to workflows)
│   │   ├── litellm_hook.py        # LiteLLM callback for token/cost/latency capture
│   │   ├── schema.py              # SQLite schema (6 tables), init_db(), migrations
│   │   └── export.py              # Export utilities (full, anonymized, DSPy examples, JSONL)
│   └── agent/
│       ├── __init__.py            # Agent design selector, hot-swap, get_agent_classes()
│       ├── base.py                # ABCs: Agent, OnboardingAgent, ResumeParser
│       ├── event_bus.py           # Thread-safe EventBus for SSE event streaming
│       ├── user_profile.py        # User profile file management
│       ├── tools/                 # Agent tool implementations
│       │   ├── __init__.py        # Tool registry exports
│       │   ├── _registry.py       # @agent_tool decorator and registry
│       │   ├── web_search.py      # web_search, web_research tools
│       │   ├── job_search.py      # job_search tool (JSearch, Active Jobs, LinkedIn)
│       │   ├── scrape_url.py      # scrape_url tool
│       │   ├── jobs.py            # create_job, list_jobs, edit_job, remove_job, todo tools
│       │   ├── profile.py         # read_user_profile, update_user_profile tools
│       │   ├── resume.py          # read_resume tool
│       │   ├── search_results.py  # add_search_result, list_search_results tools
│       │   └── job_documents.py   # save_job_document, get_job_document tools
│       ├── default/               # Default agent design (freeform ReAct loop)
│       └── micro_agents_v1/       # Micro Agents v1 design (orchestrated pipeline)
├── frontend/
│   ├── vite.config.js             # Vite config (React, Tailwind CSS plugin, proxy)
│   ├── package.json
│   └── src/
│       ├── main.jsx               # React entry point
│       ├── index.css              # Tailwind imports, chat bubble styles, Tiptap editor styles
│       ├── App.jsx                # App shell with React Router, setup wizard, onboarding
│       ├── api.js                 # Centralized API client
│       ├── contexts/
│       │   └── AppContext.jsx     # Central shared state (chat, onboarding, jobs, toasts, document events)
│       ├── pages/
│       │   ├── HomePage.jsx       # Dashboard with stats, recent jobs, quick actions
│       │   ├── JobTrackerPage.jsx # Full job table with sort, filter, status badges
│       │   ├── JobDetailPage.jsx  # Single job view: todos, requirements, notes, documents
│       │   ├── DocumentEditorPage.jsx  # Side-by-side document editor with version history
│       │   ├── SettingsPage.jsx   # LLM provider, API keys, agent mode configuration
│       │   ├── ProfilePage.jsx    # User profile viewer/editor with resume upload
│       │   └── HelpPage.jsx       # Getting started, guides, and troubleshooting
│       ├── components/
│       │   ├── NavigationBar.jsx  # Top nav with route links and AI Assistant button
│       │   ├── ChatPanel.jsx      # Slide-out AI assistant chat panel with SSE streaming
│       │   ├── SearchResultsPanel.jsx  # Slide-out job search results panel
│       │   ├── JobForm.jsx        # Create/edit job form
│       │   ├── DocumentEditor.jsx # Tiptap rich text editor wrapper with toolbar
│       │   ├── SetupWizard.jsx    # First-time setup wizard (5-step modal)
│       │   ├── ModelCombobox.jsx  # Searchable model selection combobox
│       │   ├── Toast.jsx          # Toast notification system (useToast hook, ToastContainer)
│       │   └── UpdateBanner.jsx   # Auto-update notification banner (Tauri desktop only)
│       └── utils/
│           └── errorClassifier.js # Maps LLM/network errors to user-friendly messages
├── src-tauri/                     # Tauri desktop wrapper
│   ├── tauri.conf.json            # Tauri configuration
│   ├── Cargo.toml                 # Rust dependencies
│   ├── build.rs                   # Tauri build script
│   ├── capabilities/
│   │   └── default.json           # Shell permissions for sidecar
│   └── src/
│       ├── main.rs                # Rust entry point
│       └── lib.rs                 # Sidecar launch logic
├── logs/
│   └── app.log                    # Application logs (auto-created, gitignored)
├── start.sh                       # Unified startup script (Mac/Linux)
├── start.bat                      # Unified startup script (Windows)
├── build_sidecar.sh               # PyInstaller build script for Tauri sidecar (Mac/Linux)
├── build_sidecar.ps1              # PyInstaller build script for Tauri sidecar (Windows)
├── .github/
│   ├── workflows/
│   │   ├── release.yml            # Build + release workflow (triggered by v* tags)
│   │   └── ci.yml                 # CI build check (triggered on PRs to main)
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── PULL_REQUEST_TEMPLATE.md
├── docs/
│   ├── INSTALLATION.md            # User-facing installation guide
│   ├── DEVELOPMENT.md             # Developer guide (this file)
│   ├── CONTRIBUTING.md            # Contribution guidelines
│   ├── CHANGELOG.md               # Release changelog
│   ├── TODO.md                    # Roadmap and planned features
│   ├── config.example.json        # Example configuration template
│   └── screenshots/               # App screenshots for README
├── main.py                        # Backend entry point (supports --data-dir and --port)
├── pyproject.toml                 # Python dependencies (uv)
├── config.json                    # User configuration (gitignored)
├── app.db                         # SQLite database (gitignored)
├── telemetry.db                   # Telemetry database for DSPy optimization (gitignored)
├── user_profile.md                # User profile file (gitignored)
└── CLAUDE.md                      # Claude Code instructions
```

### Key Files and Their Responsibilities

#### Backend

**`main.py`**: Entry point that calls `create_app()` and runs the Flask development server. Accepts `--data-dir` (sets `DATA_DIR` env var for custom data file location) and `--port` (default 5000) CLI arguments.

**`backend/data_dir.py`**: Centralized data directory resolver. `get_data_dir()` returns the directory where all runtime data files (app.db, config.json, logs/, user_profile.md) are stored. Uses `DATA_DIR` env var if set, otherwise defaults to `user_data/`.

**`backend/app.py`**: App factory that creates and configures the Flask app, registers blueprints, initializes the database, and starts the telemetry collector (if enabled).

**`backend/config.py`**: Centralized configuration loading from config.json file with environment variable fallback. Includes LLM provider settings, API keys, and logging configuration. Uses `get_data_dir()` for the database path.

**`backend/config_manager.py`**: Configuration file management utilities. Provides functions to read/write config.json, get/set individual config values, and mask sensitive data. Environment variables override file-based config. Config file path is resolved lazily via `get_data_dir()` to respect `DATA_DIR` set after import.

**`backend/database.py`**: SQLAlchemy instance shared across the app.

**`backend/models/job.py`**: Job model with fields for company, title, URL, status, salary range, location, remote type, tags, contact info, applied date, source, job fit rating, requirements, and nice-to-haves. Includes `to_dict()` for JSON serialization.

**`backend/models/chat.py`**: Conversation and Message models for chat persistence. Messages store role (user/assistant) and content.

**`backend/routes/jobs.py`**: CRUD blueprint for job management. Mounted at `/api/jobs`.

**`backend/routes/chat.py`**: Chat blueprint with SSE streaming. Mounted at `/api/chat`. Handles conversation creation, message sending, and agent response streaming.

**`backend/routes/profile.py`**: Profile blueprint for user profile CRUD and onboarding status. Mounted at `/api/profile`.

**`backend/routes/config.py`**: Configuration blueprint for settings management. Provides endpoints for getting/updating config, testing LLM connections, listing providers, health checks, and telemetry stats/export. Mounted at `/api/config` and `/api/telemetry`.

**`backend/routes/resume.py`**: Resume upload blueprint. Handles file upload (multipart/form-data), parsing, storage, retrieval, and deletion. Supports PDF and DOCX files up to 10 MB. Also provides an LLM-powered parsing endpoint (`POST /api/resume/parse`) that uses `ResumeParser` to clean up raw extracted text and structure it into JSON. Mounted at `/api/resume`.

**`backend/routes/job_documents.py`**: Job documents blueprint for versioned per-job documents (cover letters, resumes). Mounted at `/api/jobs/:id/documents`.

**`backend/resume_parser.py`**: Resume parsing utilities. Extracts plain text from PDF files (via PyMuPDF) and DOCX files (via python-docx, including table content). Provides file save/load/delete helpers with resume files stored in a `resumes/` subdirectory under the data dir. Also stores LLM-parsed structured JSON (`save_parsed_resume`, `get_parsed_resume`, `delete_parsed_resume`).

**`backend/llm/llm_factory.py`**: `create_llm_config(provider_name, api_key, model)` factory function that returns an `LLMConfig` dataclass used by `litellm.completion()` for any supported provider (Anthropic, OpenAI, Gemini, Ollama).

**`backend/llm/model_listing.py`**: `list_models(provider_name, api_key)` functions for each provider (uses raw SDKs to query available models). Includes `MODEL_LISTERS` registry mapping provider names to their listing functions.

**`backend/agent/base.py`**: Abstract base classes defining the agent interfaces: `Agent` (main chat agent), `OnboardingAgent` (profile interview), `ResumeParser` (non-streaming resume JSON extraction). These ABCs use a combined metaclass to inherit from both `ABC` and `dspy.Module`. The constructor signatures and abstract methods (`run()` for agents, `parse()` for resume parser) that concrete implementations must satisfy.

**`backend/agent/__init__.py`**: Agent design selector and hot-swap support. Provides `get_agent_classes(design_name=None)` which resolves the active design at call time from `agent.design` in config. Supports both raw design names (`default`, `micro_agents_v1`) and mode aliases (`freeform`, `orchestrated`). Also exports `DESIGN_MODES` and `MODE_TO_DESIGN` mappings.

**`backend/agent/event_bus.py`**: Thread-safe `EventBus` class (backed by `queue.Queue`) used by all agents to stream SSE events. Methods: `emit(event_type, data)`, `drain_blocking()`, `close()`.

**`backend/agent/tools/`**: Agent tool implementations split across multiple modules. Each tool is decorated with `@agent_tool` and has a colocated Pydantic input schema. The `_registry.py` module provides the decorator and `get_tool_definitions()` / `execute()` dispatch. Tools auto-emit `tool_start`/`tool_result`/`tool_error` events to the `EventBus`.

**`backend/agent/user_profile.py`**: User profile file management with YAML frontmatter parsing. Handles reading, writing, and onboarding status checking.

**`backend/agent/default/`**: Default agent design (freeform mode): monolithic ReAct loop using `litellm.completion()` with streaming and OpenAI-format tool calling.

**`backend/agent/micro_agents_v1/`**: Micro Agents v1 design (orchestrated mode): workflow-orchestrated pipeline using DSPy modules. Decomposes user requests into outcomes → maps to workflows → executes in dependency order → collates results. Extensible workflow system with 12+ registered workflows.

#### Frontend

**`frontend/src/main.jsx`**: React entry point that mounts `App` inside `BrowserRouter` and `AppProvider`.

**`frontend/src/App.jsx`**: App shell with React Router routes (`/`, `/jobs`, `/jobs/:id`, `/jobs/:id/documents/:type`, `/settings`, `/profile`, `/help`), `NavigationBar`, setup wizard management, and onboarding auto-start logic. Only `ChatPanel` remains as an overlay panel; all other views are dedicated pages.

**`frontend/src/contexts/AppContext.jsx`**: Central shared state context (`AppProvider`, `useAppContext`). Provides: `chatOpen`/`setChatOpen`, `onboarding`/`setOnboarding`, `jobsVersion`/`bumpJobsVersion`, `toasts`/`addToast`/`removeToast`, `handleChatError`, `notifyDocumentSaved`/`onDocumentSaved` (pub/sub for agent document save events).

**`frontend/src/api.js`**: Centralized API client with helper functions for all backend endpoints. All fetch calls go through this module. Includes `getApiBase()` which detects Tauri (via `window.__TAURI_INTERNALS__`) and returns absolute URLs to reach Flask directly, bypassing the Vite proxy.

**`frontend/src/pages/HomePage.jsx`**: Dashboard with job stats cards (total, applied, interviewing, offers), AI config status, recent jobs list, and quick action buttons.

**`frontend/src/pages/JobTrackerPage.jsx`**: Full job table with status badges, sortable columns, "Add Job" button. Row click navigates to `/jobs/:id`.

**`frontend/src/pages/JobDetailPage.jsx`**: Full page for a single job: application todos, requirements, nice-to-haves, notes, tags, contact info, salary, and a Documents section with links to cover letter/resume editors.

**`frontend/src/pages/DocumentEditorPage.jsx`**: Side-by-side document editor page with Tiptap rich text editor, formatting toolbar, version history sidebar, save/copy/AI assistant buttons, and Ctrl+S shortcut. Subscribes to agent `document_saved` events via `onDocumentSaved` for real-time refresh.

**`frontend/src/pages/SettingsPage.jsx`**: Full page for configuring LLM provider, API keys, agent mode, and optional integrations (Tavily, RapidAPI). Includes "Test Connection" and inline "How do I get this key?" guides.

**`frontend/src/pages/ProfilePage.jsx`**: Full page for user profile viewer/editor with resume upload section (PDF/DOCX). Users can upload, preview (Structured/Raw toggle), replace, or remove their resume. Auto-triggers LLM parsing on upload. Also supports manual profile markdown editing.

**`frontend/src/pages/HelpPage.jsx`**: Full page with Getting Started, Job Tracking, AI Chat, API Key Guides, and Troubleshooting sections.

**`frontend/src/components/NavigationBar.jsx`**: Top nav bar with `NavLink` route links (Home, Jobs, Profile, Settings, Help) and an "AI Assistant" chat toggle button. Active page indicated via NavLink styling.

**`frontend/src/components/ChatPanel.jsx`**: Slide-out AI assistant panel with SSE streaming, markdown rendering, and tool execution visibility. Manages search results state and renders `SearchResultsPanel` alongside chat when results exist. Includes `JOB_MUTATING_TOOLS` set for live job list refresh. Handles `document_saved` SSE events and forwards them via `notifyDocumentSaved` to AppContext.

**`frontend/src/components/SearchResultsPanel.jsx`**: Slide-out panel displaying job search results with collapsible cards, star ratings, fit reasons, and "Add to Tracker" buttons. Appears alongside ChatPanel during/after job searches.

**`frontend/src/components/JobForm.jsx`**: Reusable form component for creating and editing jobs. Handles all job fields including requirements and nice-to-haves.

**`frontend/src/components/DocumentEditor.jsx`**: Tiptap rich text editor wrapper with formatting toolbar (bold, italic, H1-H3, bullet/ordered lists, blockquote, horizontal rule, undo/redo). Accepts `content` prop and `onUpdate` callback.

**`frontend/src/components/SetupWizard.jsx`**: Centered modal wizard for first-time setup. Five steps: welcome, provider selection (card grid), API key entry with inline how-to guide and test connection, optional integrations (Tavily + RapidAPI), and a done screen that launches onboarding. Requires a successful connection test before allowing the user to continue (Ollama skips the key requirement). Calls `onComplete()` to open onboarding chat or `onClose()` to dismiss.

**`frontend/src/components/ModelCombobox.jsx`**: Searchable combobox for selecting an LLM model. Fetches available models from the provider's API with a client-side cache (5-minute TTL). Falls back to free-text input if the API call fails or no API key is entered yet.

**`frontend/src/components/Toast.jsx`**: Toast notification system (`useToast` hook and `ToastContainer` component). Supports error, warning, and info types with collapsible technical details. Error toasts require manual dismissal; others auto-dismiss after 5 seconds.

**`frontend/src/utils/errorClassifier.js`**: Maps raw LLM/network error strings to user-friendly toast messages with actionable guidance. Uses regex matchers to classify errors (invalid API key, quota exhaustion, rate limiting, timeouts, model not found, etc.) and returns structured `{ type, title, message, detail }` objects for the toast system.

## Development Setup

### Prerequisites

- **Python 3.12+**: Check with `python --version`
- **Node.js 18+**: Check with `node --version`
- **uv**: Install via [standalone installer](https://docs.astral.sh/uv/getting-started/installation/)
- **npm**: Comes with Node.js

### Quick Start (Recommended for First-Time Setup)

The fastest way to get the development environment running:

**Mac/Linux:**
```bash
./start.sh
```

**Windows:**
```bash
start.bat
```

The startup script will:
- Check and guide installation of prerequisites
- Install all dependencies (backend and frontend)
- Start both servers concurrently
- Open your browser to http://localhost:3000

Once the app is running, configure your LLM API key through the Settings page (click "Settings" in the navigation bar).

### Manual Setup (For Development Workflow)

For developers who prefer manual control over each component:

#### Backend Setup

1. **Install Python dependencies:**

```bash
uv sync
```

This creates a virtual environment and installs all dependencies from `pyproject.toml`.

2. **Configure the application:**

Configuration is managed through `config.json` (auto-created on first run). You can:

- **Use the Settings UI** (recommended): Start the app and configure via the Settings panel
- **Edit config.json manually**: Copy `docs/config.example.json` to `config.json` and edit
- **Use environment variables** (overrides config.json): Export in your shell

**Example config.json** (see [`docs/config.example.json`](config.example.json) for the full template):
```json
{
  "llm": {
    "provider": "anthropic",
    "api_key": "your-api-key-here",
    "model": ""
  },
  "onboarding_llm": {
    "provider": "",
    "api_key": "",
    "model": ""
  },
  "search_llm": {
    "provider": "",
    "api_key": "",
    "model": ""
  },
  "agent": {
    "design": "default"
  },
  "integrations": {
    "search_api_key": "",
    "rapidapi_key": ""
  },
  "logging": {
    "level": "INFO"
  },
  "telemetry": {
    "enabled": true,
    "retention_days": 90
  }
}
```

**Environment variable override (optional):**
```bash
export LLM_PROVIDER=anthropic
export LLM_API_KEY=your-api-key-here
export INTEGRATIONS_SEARCH_API_KEY=your-tavily-key
export LOG_LEVEL=DEBUG
```

Environment variables take precedence over `config.json` values.

3. **Run the Flask server:**

```bash
uv run python main.py
```

The API will be available at `http://localhost:5000`.

#### Frontend Setup

1. **Install Node dependencies:**

```bash
cd frontend
npm install
```

2. **Run the Vite dev server:**

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`. The Vite dev server proxies `/api` requests to the Flask backend at `localhost:5000`.

#### Production Build

To verify frontend changes compile correctly:

```bash
cd frontend
npm run build
```

This creates an optimized production build in `frontend/dist`.

#### Desktop Development (Tauri)

The app can optionally run as a native desktop application using Tauri v2. Tauri renders the React frontend in a native webview and launches the Flask backend as a sidecar child process.

**Prerequisites** (in addition to standard prerequisites):
- **Rust toolchain**: Install via [rustup.rs](https://rustup.rs/)
- **Tauri system dependencies**: See [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)

**Development workflow:**

```bash
# Terminal 1: Start Flask backend manually
uv run python main.py

# Terminal 2: Launch Tauri dev window (starts Vite automatically)
npm run tauri:dev
```

In debug mode, Tauri does not spawn the Flask sidecar — you start it manually. The Tauri webview loads from `http://localhost:3000` (Vite dev server), which proxies API requests to Flask at `localhost:5000`.

**Custom data directory** (simulates Tauri production behavior):

```bash
uv run python main.py --data-dir /tmp/test-data --port 5000
```

This stores all data files (app.db, config.json, logs/, user_profile.md) in the specified directory instead of the default `user_data/`.

**Production build:**

```bash
# 1. Bundle Flask backend as standalone binary
./build_sidecar.sh

# 2. Build the desktop app
npm run tauri:build
```

In production mode, Tauri spawns the Flask binary as a sidecar with `--data-dir` set to the platform-standard app data directory.

### Configuration Priority

The application loads configuration in this order (later sources override earlier ones):

1. **Default values** (hardcoded in `backend/config_manager.py`)
2. **config.json** (persistent user configuration)
3. **Environment variables** (highest priority)

This allows flexibility for different deployment scenarios while maintaining a simple user experience.

## API Reference

### Jobs API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/jobs` | List all jobs (newest first) | — | `[{job}, ...]` |
| POST | `/api/jobs` | Create a job | `{company, title, ...}` | `{job}` |
| GET | `/api/jobs/:id` | Get single job | — | `{job}` |
| PATCH | `/api/jobs/:id` | Update job (partial) | `{field: value, ...}` | `{job}` |
| DELETE | `/api/jobs/:id` | Delete job | — | `204 No Content` |

### Application Todos API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/jobs/:id/todos` | List todos for a job | — | `[{todo}, ...]` |
| POST | `/api/jobs/:id/todos` | Create a todo | `{title, category?, description?}` | `{todo}` |
| PATCH | `/api/jobs/:id/todos/:todoId` | Update a todo | `{title?, completed?, ...}` | `{todo}` |
| DELETE | `/api/jobs/:id/todos/:todoId` | Delete a todo | — | `204 No Content` |

### Job Documents API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/jobs/:id/documents?type=` | Get latest document version | — | `{document}` |
| GET | `/api/jobs/:id/documents/history?type=` | Get all document versions | — | `[{document}, ...]` |
| POST | `/api/jobs/:id/documents` | Save new document version | `{doc_type, content, edit_summary?}` | `{document}` |
| DELETE | `/api/jobs/:id/documents/:docId` | Delete a document version | — | `204 No Content` |

**Job Object Fields:**

Required:
- `company` (string): Company name
- `title` (string): Job title

Optional:
- `url` (string): Job posting URL
- `status` (string): One of `saved`, `applied`, `interviewing`, `offer`, `rejected` (default: `saved`)
- `notes` (text): Free-form notes
- `salary_min` (int): Minimum salary
- `salary_max` (int): Maximum salary
- `location` (string): Job location
- `remote_type` (string): One of `onsite`, `hybrid`, `remote`
- `tags` (string): Comma-separated tags
- `contact_name` (string): Hiring manager or recruiter name
- `contact_email` (string): Contact email
- `applied_date` (string): ISO date when application was submitted
- `source` (string): Where you found the job (e.g., "LinkedIn", "Company Website")
- `job_fit` (int): 0-5 star rating of how well the job matches your profile
- `requirements` (text): Newline-separated list of job requirements
- `nice_to_haves` (text): Newline-separated list of nice-to-have qualifications

Auto-generated:
- `id` (int): Primary key
- `created_at` (datetime): Timestamp when record was created
- `updated_at` (datetime): Timestamp when record was last updated

### Chat API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/chat/conversations` | List conversations (newest first) | — | `[{conversation}, ...]` |
| POST | `/api/chat/conversations` | Create conversation | `{title?}` | `{conversation}` |
| GET | `/api/chat/conversations/:id` | Get conversation with messages | — | `{conversation with messages}` |
| DELETE | `/api/chat/conversations/:id` | Delete conversation | — | `204 No Content` |
| POST | `/api/chat/conversations/:id/messages` | Send message | `{content}` | SSE stream |
| GET | `/api/chat/conversations/:id/search-results` | Get search results for conversation | — | `[{searchResult}, ...]` |
| POST | `/api/chat/conversations/:id/search-results/:resultId/add-to-tracker` | Promote search result to job tracker | — | `{job}` |

**SSE Event Types** (chat streaming):

- `text_delta`: `{"content": "..."}` — Incremental text from the LLM
- `tool_start`: `{"id": "...", "name": "...", "arguments": {...}}` — Tool execution starting
- `tool_result`: `{"id": "...", "name": "...", "result": {...}}` — Tool completed successfully
- `tool_error`: `{"id": "...", "name": "...", "error": "..."}` — Tool execution failed
- `search_result_added`: `{...SearchResult}` — Job added to search results panel (emitted by `add_search_result` tool)
- `document_saved`: `{"document": {...}, "job_id": int, "doc_type": "..."}` — Document saved (emitted by `save_job_document` tool)
- `done`: `{"content": "full text"}` — Agent finished
- `error`: `{"message": "..."}` — Fatal error

### Onboarding API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| POST | `/api/chat/onboarding/conversations` | Create onboarding conversation | — | `{conversation}` |
| POST | `/api/chat/onboarding/conversations/:id/messages` | Send onboarding message | `{content}` | SSE stream |
| POST | `/api/chat/onboarding/kick` | Start onboarding (agent greeting) | — | SSE stream |

**Additional SSE Event** (onboarding only):
- `onboarding_complete`: `{}` — Onboarding interview finished

### Profile API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/profile` | Get user profile markdown | — | `{content: "..."}` |
| PUT | `/api/profile` | Update user profile markdown | `{content: "..."}` | `{content: "..."}` |
| GET | `/api/profile/onboarding-status` | Check if onboarded | — | `{onboarded: true/false}` |
| POST | `/api/profile/onboarding-status` | Set onboarding status | `{onboarded: true/false}` | `{onboarded: true/false}` |

### Config API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/config` | Get configuration (masked) | — | `{llm: {...}, integrations: {...}}` |
| POST | `/api/config` | Update configuration | `{llm: {...}, integrations: {...}}` | `{success: true}` |
| POST | `/api/config/models` | List available models for a provider | `{provider, api_key?}` | `{models: [...]}` |
| POST | `/api/config/test` | Test LLM connection | `{provider, api_key, model?}` | `{success: true/false, message}` |
| GET | `/api/config/providers` | List available LLM providers | — | `[{id, name, default_model, requires_api_key}, ...]` |
| GET | `/api/health` | Health check endpoint | — | `{status, llm: {...}, integrations: {...}}` |

### Telemetry API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| GET | `/api/telemetry/stats` | Get telemetry DB metrics | — | `{runs, records, size}` |
| GET | `/api/telemetry/export?mode=` | Export telemetry data (`full` or `anonymized`) | — | JSON file download |
| POST | `/api/chat/conversations/:id/messages/:msgId/feedback` | Record thumbs up/down feedback | `{signal, comment?}` | `{status: "recorded"}` |

### Resume API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| POST | `/api/resume` | Upload resume (PDF/DOCX) | multipart/form-data with `file` field | `{filename, size, text, text_length}` |
| GET | `/api/resume` | Get saved resume info + text + structured data | — | `{resume: {filename, size, text, text_length, parsed} \| null}` |
| DELETE | `/api/resume` | Delete saved resume | — | `{status: "deleted" \| "no_resume"}` |
| POST | `/api/resume/parse` | Parse resume with LLM | — | `{parsed: {...}}` |

**Supported formats:** PDF (`.pdf`) and Microsoft Word (`.docx`). Maximum file size: 10 MB.

The raw text is extracted using PyMuPDF (PDF) or python-docx (DOCX, including table content). Resume files are stored in a `resumes/` subdirectory under the data directory.

The `POST /api/resume/parse` endpoint uses `ResumeParser` to send the raw extracted text to the configured LLM, which cleans up PDF/DOCX extraction artifacts (broken formatting, garbled characters, merged words) and returns structured JSON with fields like `contact_info`, `work_experience`, `education`, `skills`, `certifications`, `projects`, and more. The structured data is persisted as `resume_parsed.json` and returned by subsequent `GET /api/resume` calls.

**Configuration Object Format:**
```json
{
  "llm": {
    "provider": "anthropic",
    "api_key": "sk-ant-****",
    "model": ""
  },
  "onboarding_llm": {
    "provider": "",
    "api_key": "",
    "model": ""
  },
  "search_llm": {
    "provider": "",
    "api_key": "",
    "model": ""
  },
  "agent": {
    "design": "default"
  },
  "integrations": {
    "search_api_key": "",
    "rapidapi_key": ""
  },
  "logging": {
    "level": "INFO"
  },
  "telemetry": {
    "enabled": true,
    "retention_days": 90
  }
}
```

**Note**: API keys are masked with asterisks when returned via GET `/api/config`.

## Database Models

### Job Model

Located in `backend/models/job.py`.

**Schema:**

```python
class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.Text)
    status = db.Column(db.String(50), default='saved')
    notes = db.Column(db.Text)
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    location = db.Column(db.String(200))
    remote_type = db.Column(db.String(50))
    tags = db.Column(db.Text)
    contact_name = db.Column(db.String(200))
    contact_email = db.Column(db.String(200))
    applied_date = db.Column(db.String(50))
    source = db.Column(db.String(200))
    job_fit = db.Column(db.Integer)
    requirements = db.Column(db.Text)
    nice_to_haves = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Key Methods:**
- `to_dict()`: Serializes model to dictionary for JSON responses

### Chat Models

Located in `backend/models/chat.py`.

**Conversation Schema:**

```python
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')
```

**Message Schema:**

```python
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### SearchResult Model

Located in `backend/models/search_result.py`.

**Schema:**

```python
class SearchResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.Text)
    salary = db.Column(db.String(100))
    location = db.Column(db.String(200))
    remote_type = db.Column(db.String(50))
    source = db.Column(db.String(200))
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    nice_to_haves = db.Column(db.Text)
    job_fit = db.Column(db.Integer)           # 0-5 star rating
    fit_reason = db.Column(db.Text)
    added_to_tracker = db.Column(db.Boolean, default=False)
    tracker_job_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### ApplicationTodo Model

Located in `backend/models/application_todo.py`.

**Schema:**

```python
class ApplicationTodo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    category = db.Column(db.String(50))       # document, question, assessment, reference, other
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### JobDocument Model

Located in `backend/models/job_document.py`.

**Schema:**

```python
class JobDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    doc_type = db.Column(db.String(50), nullable=False)  # 'cover_letter' or 'resume'
    content = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, nullable=False)
    edit_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Key Methods:**
- `get_latest(job_id, doc_type)`: Get the latest version of a document
- `get_history(job_id, doc_type)`: Get all versions of a document
- `next_version(job_id, doc_type)`: Get the next version number

## LLM Provider System

The LLM system uses LiteLLM to provide a unified interface across multiple AI providers. All providers are accessed through `litellm.completion()` using a provider-prefixed model string and an `LLMConfig` dataclass created by a single factory function.

### Architecture

1. **Factory** (`backend/llm/llm_factory.py`): `create_llm_config(provider_name, api_key, model)` returns an `LLMConfig` dataclass with the LiteLLM model string (e.g., `anthropic/claude-sonnet-4-5-20250929`) and credentials
2. **Model Listing** (`backend/llm/model_listing.py`): `list_models(provider_name, api_key)` queries available models via each provider's raw SDK; `MODEL_LISTERS` maps provider names to listing functions
3. **LiteLLM**: Single package that translates `litellm.completion()` calls to provider-specific APIs with consistent OpenAI-format input/output

### Supported Providers

| Provider | Default Model | Notes |
|----------|---------------|-------|
| `anthropic` | `claude-sonnet-4-5-20250929` | Best quality, tool calling |
| `openai` | `gpt-4o` | Good quality, tool calling |
| `gemini` | `gemini-2.0-flash` | Fast, tool calling |
| `ollama` | `llama3.1` | Local, free, requires Ollama server |

### Configuration

Providers are configured through `config.json` (with optional environment variable override):

**config.json format:**
```json
{
  "llm": {
    "provider": "anthropic",
    "api_key": "your-api-key-here",
    "model": ""
  },
  "onboarding_llm": {
    "provider": "",
    "api_key": "",
    "model": "claude-haiku-4-5-20251001"
  },
  "search_llm": {
    "provider": "",
    "api_key": "",
    "model": ""
  },
  "agent": {
    "design": "default"
  },
  "telemetry": {
    "enabled": true,
    "retention_days": 90
  }
}
```

**Environment variable override (optional):**
```bash
# Main chat configuration
export LLM_PROVIDER=anthropic
export LLM_API_KEY=your-api-key
export LLM_MODEL=custom-model-name

# Onboarding configuration (optional, defaults to main config)
export ONBOARDING_LLM_PROVIDER=anthropic
export ONBOARDING_LLM_API_KEY=your-api-key
export ONBOARDING_LLM_MODEL=claude-haiku-4-5-20251001

# Search configuration (optional, defaults to main config)
export SEARCH_LLM_PROVIDER=anthropic
export SEARCH_LLM_MODEL=claude-haiku-4-5-20251001

# Agent design
export AGENT_DESIGN=default
```

Configuration is managed by `backend/config_manager.py` which reads from `config.json` and falls back to environment variables. The Settings UI provides a user-friendly interface for configuration.

### Adding a New Provider

1. Add a new case in `create_llm_config()` in `backend/llm/llm_factory.py` with the LiteLLM model prefix
2. Add a default model in the `DEFAULT_MODELS` dict
3. Add a model listing function in `backend/llm/model_listing.py` and register it in `MODEL_LISTERS`

Example (adding to `llm_factory.py`):

```python
# In create_llm_config():
elif provider_name == "yourprovider":
    litellm_model = f"yourprovider/{resolved_model}"
```

LiteLLM supports 100+ providers out of the box — often no code changes are needed beyond adding the model prefix mapping. See [LiteLLM providers](https://docs.litellm.ai/docs/providers) for the full list.

## Agent System

The agent system uses abstract base classes (ABCs) to define the interface between the application routes and agent implementations. This allows agent implementations to be swapped without modifying the rest of the application.

### Architecture

**Agent ABCs** (`backend/agent/base.py`):
- `Agent` — main chat agent with `run(messages)` generator method
- `OnboardingAgent` — profile interview agent with `run(messages)` generator method
- `ResumeParser` — resume parsing with `parse(raw_text)` method

**Agent Design Selector** (`backend/agent/__init__.py`):
- `get_agent_classes(design_name)` — resolves active design at call time (hot-swappable)
- Supports raw names (`default`, `micro_agents_v1`) and mode aliases (`freeform`, `orchestrated`)

**Agent Tools** (`backend/agent/tools/`):
- `@agent_tool`-decorated functions across multiple modules
- `execute(tool_name, arguments)` — dispatch tool calls by name
- `get_tool_definitions()` — return tool metadata for LLM framework adaptation

**Event Bus** (`backend/agent/event_bus.py`):
- Thread-safe event queue for streaming SSE events from agent worker threads

**Agent Loop** (implemented by concrete agent classes):
1. User sends message
2. Agent calls LLM with system prompt + conversation history + tools
3. LLM responds with text and/or tool calls
4. Agent executes tool calls via `AgentTools.execute()`
5. Tool results are added to conversation history
6. If LLM made tool calls, return to step 2
7. Stream final response to user via SSE events

### Available Tools

Defined in `backend/agent/tools/`:

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `web_search` | Search the web via Tavily API | `query`, `num_results` (opt) |
| `web_research` | Multi-step web research with synthesis and citations | `query` |
| `job_search` | Search job boards via RapidAPI (JSearch, Active Jobs DB, LinkedIn) | `query`, `location` (opt), `remote_only` (opt), `salary_min`/`salary_max` (opt), `provider` (opt), `num_results` (opt) |
| `scrape_url` | Fetch and parse a web page | `url`, `query` (opt) |
| `create_job` | Add a job to the database | `company`, `title` (required); plus all optional job fields |
| `list_jobs` | List and filter tracked jobs | `status` (opt), `company` (opt), `title` (opt), `url` (opt), `limit` (opt) |
| `edit_job` | Update an existing job | `job_id` (required); plus optional fields to update |
| `remove_job` | Delete a job and associated todos/documents | `job_id` |
| `list_job_todos` | List application todos for a job | `job_id` |
| `add_job_todo` | Add an application todo item | `job_id`, `title` (required); `category` (opt), `description` (opt) |
| `edit_job_todo` | Update an existing todo | `job_id`, `todo_id` (required); plus optional fields |
| `remove_job_todo` | Delete a todo | `job_id`, `todo_id` |
| `read_user_profile` | Read the user's profile markdown | — |
| `update_user_profile` | Update the user's profile | `content`; `section` (opt) |
| `read_resume` | Read the user's uploaded resume | — |
| `add_search_result` | Add a qualifying job to search results panel | `company`, `title`, `job_fit` (required); plus optional fields |
| `list_search_results` | List search results from current conversation | `min_fit` (opt) |
| `save_job_document` | Save a cover letter or tailored resume for a job | `job_id`, `doc_type`, `content`; `edit_summary` (opt) |
| `get_job_document` | Retrieve latest document for a job | `job_id`; `doc_type` (opt) |

### Tool Definitions

Tools are defined as `@agent_tool`-decorated functions in `backend/agent/tools/` with colocated Pydantic input schemas. The `get_tool_definitions()` function returns metadata that agent implementations use to adapt tools to their specific LLM framework:

```python
class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    num_results: int = Field(default=5, description="Number of results to return (max 10)")

@agent_tool(
    description="Search the web using Tavily.",
    args_schema=WebSearchInput,
)
def web_search(self, query, num_results=5):
    # tool implementation
    ...
```

### User Profile Integration

The agent automatically reads the user profile at the start of each conversation and injects it into the system prompt. This allows the agent to personalize responses and provide better job recommendations.

The agent also proactively extracts job-search-relevant information from user messages and updates the profile via the `update_user_profile` tool (e.g., preferred job titles, locations, salary expectations).

### Onboarding Agent

`OnboardingAgent` is a specialized agent ABC. Implementations use a dedicated system prompt that conducts an interview to build the user's profile. It asks about:
- Job search status and goals
- Preferred job titles and roles
- Skills and experience
- Location preferences and remote work preferences
- Salary expectations

Once complete, it sets the `onboarded: true` flag in the user profile frontmatter and yields an `onboarding_complete` SSE event.

### Adding a New Tool

1. Create a new module in `backend/agent/tools/` (or add to an existing one) with a Pydantic input model and an `@agent_tool`-decorated function
2. Import the module in `backend/agent/tools/__init__.py` to register it
3. If the tool mutates jobs, add its name to `JOB_MUTATING_TOOLS` in `frontend/src/components/ChatPanel.jsx` to trigger live list refresh

Example:

```python
# In backend/agent/tools/my_tool.py

from pydantic import BaseModel, Field
from backend.agent.tools._registry import agent_tool

class UpdateJobInput(BaseModel):
    job_id: int = Field(description="ID of the job to update")
    field: str = Field(description="Field name to update")
    value: str = Field(description="New value for the field")

@agent_tool(
    description="Update an existing job in the tracker",
    args_schema=UpdateJobInput,
)
def update_job(job_id, field, value):
    job = Job.query.get_or_404(job_id)
    setattr(job, field, value)
    db.session.commit()
    return job.to_dict()
```

Then in `frontend/src/components/ChatPanel.jsx`:

```javascript
const JOB_MUTATING_TOOLS = new Set(['create_job', 'edit_job', 'remove_job', 'add_job_todo', 'edit_job_todo', 'remove_job_todo', 'save_job_document', 'update_job']);
```

## Development Conventions

### General

- **One feature per commit**: Keep changes focused and atomic
- **Verify builds**: Run `cd frontend && npm run build` before committing frontend changes
- **Prefer editing over creating**: Avoid file bloat by editing existing files when possible

### Backend (Python)

- **Follow PEP 8**: Use standard Python style conventions
- **Use blueprints**: Organize routes into blueprints and register in `backend/app.py`
- **Thin controllers**: Keep route handlers thin; business logic goes in models or services
- **Model serialization**: Use `to_dict()` methods for JSON serialization
- **Validate inputs**: Check required fields before creating/updating records
- **Type hints**: Use type hints for function parameters and return values
- **Logging**: Use the configured logger (`import logging; logger = logging.getLogger(__name__)`)

### Frontend (React/JS)

- **Functional components**: Use functional components with hooks (no class components)
- **File organization**: Pages in `pages/`, reusable components in `components/`
- **Centralized API calls**: All backend calls go through `frontend/src/api.js`
- **Tailwind CSS only**: Use Tailwind utility classes, no separate CSS files
- **Component size**: Keep components under ~150 lines; extract subcomponents if larger
- **PropTypes or TypeScript**: Document component props (future improvement)

### Logging

- **Logger names**: Use `__name__` for module-specific loggers
- **Log levels**:
  - `DEBUG`: Full tool results, detailed execution flow
  - `INFO`: High-level events (agent iterations, tool calls, API requests)
  - `WARNING`: Unexpected but handled situations
  - `ERROR`: Errors that need attention
- **Key loggers**:
  - `backend.agent.tools`: Tool execution details
  - `backend.llm.*`: Provider requests/responses
  - `backend.routes.chat`: Incoming messages, response completion

### Configuration Management

- **Primary method**: `config.json` managed via the Settings UI (never hardcode secrets)
- **Environment variable override**: Env vars take precedence over `config.json` for deployment flexibility
- **Defaults**: Provide sensible defaults in `backend/config_manager.py`
- **Validation**: Validate required config on app startup

## Telemetry System

The telemetry system passively captures agent execution data during normal app usage to enable future [DSPy optimization](TELEMETRY_DESIGN.md). Data is stored in a separate `telemetry.db` SQLite file (in the data directory), isolated from `app.db`.

### What's Captured

| Data Type | Source | Details |
|-----------|--------|---------|
| **Agent runs** | `telemetry_run()` context manager | Run lifecycle (start, end, success/error, duration) |
| **DSPy module traces** | `TracedModule` mixin | Inputs, outputs, CoT reasoning, timing, nested parent-child relationships |
| **Tool calls** | `AgentTools.execute()` hook | Tool name, arguments, result, success/error, timing |
| **Workflow traces** | `@traced_workflow` decorator (auto-applied) | Workflow name, outcome, params, result, timing |
| **LLM call metrics** | LiteLLM callback | Model, tokens in/out, latency, cost |
| **User feedback** | Feedback API endpoint | Thumbs up/down, optional comment |

### Configuration

In `config.json`:
```json
{
  "telemetry": {
    "enabled": true,
    "retention_days": 90
  }
}
```

- **`enabled`**: Set to `false` to disable all telemetry collection. When disabled, all recording calls are no-ops with zero overhead.
- **`retention_days`**: Records older than this are automatically pruned on startup.

### Key Integration Points

- **`backend/app.py`**: `_init_telemetry()` initializes the collector at startup, registers the LiteLLM callback, and runs compaction
- **Agent `run()` methods**: Wrapped in `with telemetry_run(conversation_id, user_message, design_name)`
- **DSPy modules**: Inherit from `TracedModule` mixin (e.g., `class OutcomePlanner(TracedModule, dspy.Module)`)
- **Workflows**: Auto-traced via `BaseWorkflow.__init_subclass__` — no per-workflow changes needed
- **Tool calls**: Recorded automatically in `AgentTools.execute()`
- **LLM calls**: Captured by `TelemetryLiteLLMCallback` registered at startup

### For Developers

**Adding a new DSPy module:** Add `TracedModule` to the class hierarchy:
```python
from backend.telemetry.traced_module import TracedModule
class MyModule(TracedModule, dspy.Module):
    ...
```

**Adding a new workflow:** Inherit from `BaseWorkflow` — tracing is auto-applied via `__init_subclass__`.

**Adding a new agent design:** Wrap the agent's run method with `telemetry_run()`:
```python
from backend.telemetry.context import telemetry_run
def run(self, messages):
    with telemetry_run(self.conversation_id, messages[-1], "my_design"):
        # ... agent logic ...
```

**Error isolation:** All telemetry calls are wrapped in try/except. Telemetry failures are logged at DEBUG level and never propagate to affect user experience.

**Inspecting telemetry data:**
- `GET /api/telemetry/stats` — record counts and DB size
- `GET /api/telemetry/export?mode=full` — full database export
- `GET /api/telemetry/export?mode=anonymized` — export with user content stripped
- Delete `telemetry.db` to reset all telemetry data

For the full architecture and DSPy optimization roadmap, see [TELEMETRY_DESIGN.md](TELEMETRY_DESIGN.md).

## Testing

> **Note**: Testing infrastructure is currently minimal. This section outlines the planned approach.

### Backend Testing

Use `pytest` for backend tests:

```bash
uv run pytest
```

**Test structure:**
- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`
- Fixtures in `tests/conftest.py`

**Key test areas:**
- Model CRUD operations
- API endpoint behavior
- Agent tool execution
- LLM provider mocking

### Frontend Testing

Use Vitest for frontend tests:

```bash
cd frontend
npm run test
```

**Test structure:**
- Component tests using React Testing Library
- API client mocking
- SSE stream handling

## Deployment

### Desktop Distribution (Tauri)

For distributing the app as a standalone desktop application:

1. Build the Flask sidecar binary:
   ```bash
   ./build_sidecar.sh
   ```
2. Build the Tauri desktop app:
   ```bash
   npm run tauri:build
   ```
3. The built application will be in `src-tauri/target/release/bundle/`

In the desktop build, data files are stored in platform-standard directories:
- **Linux**: `~/.local/share/com.shortlist.app/`
- **macOS**: `~/Library/Application Support/com.shortlist.app/`
- **Windows**: `C:\Users\<user>\AppData\Roaming\com.shortlist.app\`

### Server Deployment (Web)

1. **Database**: Replace SQLite with PostgreSQL or MySQL for production
2. **Configuration**: Use environment variables (not `config.json`) with a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
3. **WSGI server**: Run Flask with Gunicorn or uWSGI (not the dev server)
4. **Static files**: Serve frontend build with nginx or CDN
5. **HTTPS**: Use TLS certificates (Let's Encrypt)
6. **Logging**: Send logs to a centralized logging service
7. **Monitoring**: Add application performance monitoring (APM)

**Note**: While `config.json` is convenient for local development, environment variables are recommended for production deployments as they integrate better with container orchestration, CI/CD pipelines, and secrets management systems.

### Build Process

1. Build frontend:

```bash
cd frontend
npm run build
```

2. Serve frontend static files from Flask:

```python
# In backend/app.py
from flask import send_from_directory

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join('frontend/dist', path)):
        return send_from_directory('frontend/dist', path)
    return send_from_directory('frontend/dist', 'index.html')
```

3. Run with Gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "backend.app:create_app()"
```

### Configuration for Production

**Recommended**: Use environment variables for production deployments (they override `config.json`):

```bash
# Flask
FLASK_ENV=production
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# LLM Configuration
LLM_PROVIDER=anthropic
LLM_API_KEY=your-api-key
LLM_MODEL=claude-sonnet-4-5-20250929

# Onboarding LLM (optional, uses cheaper model)
ONBOARDING_LLM_PROVIDER=anthropic
ONBOARDING_LLM_MODEL=claude-haiku-4-5-20251001

# Optional Integrations
INTEGRATIONS_SEARCH_API_KEY=your-tavily-key
INTEGRATIONS_RAPIDAPI_KEY=your-rapidapi-key

# Agent Design (optional)
AGENT_DESIGN=default

# Logging
LOG_LEVEL=INFO
```

Environment variables take precedence over `config.json`, making them ideal for containerized deployments and CI/CD pipelines.

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and automated releases.

### CI Workflow (`.github/workflows/ci.yml`)

- **Triggers:** Pull requests to `main`
- **Matrix:** Linux (ubuntu-latest) + Windows (windows-latest)
- **What it does:** Checks out code, installs dependencies (Rust, Node.js, Python/uv), builds the Flask sidecar binary, and runs `tauri build` to verify the app compiles
- **Purpose:** Catch build failures before merging PRs

### Release Workflow (`.github/workflows/release.yml`)

- **Triggers:** Push of `v*` tags (e.g., `v0.6.0`) or manual `workflow_dispatch`
- **Matrix:** Linux x86_64, macOS ARM64, Windows x86_64
- **Artifacts produced:**
  - **Linux:** `.deb`, `.rpm`, `.AppImage`
  - **macOS:** `.dmg`
  - **Windows:** `.exe` (NSIS installer), `.msi`
- **What it does:**
  1. Checks out code and installs all dependencies
  2. Restores cached sidecar binary (keyed on Python source hash + `uv.lock`); skips steps 3–4 on cache hit
  3. Installs Python dependencies via `uv sync --dev` (skipped on sidecar cache hit)
  4. Builds the Flask sidecar binary via PyInstaller (`build_sidecar.sh` or `build_sidecar.ps1`) (skipped on sidecar cache hit)
  5. Runs `tauri build` to produce platform-specific installers
  6. Creates a **draft** GitHub Release and uploads all artifacts

### Build Caching

Both workflows cache two things to speed up builds:

- **uv package cache** (`enable-cache: true` on `astral-sh/setup-uv`): Persists downloaded Python packages between runs so `uv sync` only fetches what changed.
- **Sidecar binary cache** (keyed on `sidecar-<target>-<hash of all .py files + uv.lock>`): If no Python source or dependency files have changed since the last build, the entire Python install + PyInstaller step is skipped. This is the biggest win for frontend-only releases, saving 5–10+ minutes per platform.

### Creating a Release

1. Update version in all five files: `package.json`, `frontend/package.json`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, and `pyproject.toml`
2. Commit and tag:
   ```bash
   git tag v0.4.2
   git push origin v0.4.2
   ```
3. Wait for the release workflow to complete (check the Actions tab)
4. Go to GitHub Releases, review the draft, and click **Publish**

### Build Scripts

| Script | Platform | Description |
|--------|----------|-------------|
| `build_sidecar.sh` | Mac/Linux | Detects architecture, runs PyInstaller, places binary in `src-tauri/binaries/` with Tauri target-triple naming |
| `build_sidecar.ps1` | Windows | PowerShell equivalent — builds Flask as standalone `.exe` for Tauri sidecar |

### Code Signing Status

Code signing is **not yet configured**. This means:
- **Windows:** Users will see a SmartScreen warning on first install ("More info" → "Run anyway")
- **macOS:** Users need to approve the app in System Settings → Privacy & Security

To enable code signing in the future:
- **macOS:** Add Apple Developer secrets (`APPLE_CERTIFICATE`, `APPLE_SIGNING_IDENTITY`, etc.) to the GitHub repo settings and uncomment the relevant env vars in `release.yml`
- **Windows:** Obtain an EV code signing certificate and configure it in the release workflow

> **Note:** Tauri update signing (via `TAURI_SIGNING_PRIVATE_KEY`) is separate from OS code signing. Update signing is already configured and is used to verify auto-update integrity. OS code signing is what eliminates the SmartScreen/Gatekeeper warnings.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting bugs, requesting features, and submitting pull requests.
