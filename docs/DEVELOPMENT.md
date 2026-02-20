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
- [Testing](#testing)
- [Deployment](#deployment)

## Architecture Overview

The Shortlist is built as a full-stack web application with a clear separation between frontend and backend:

- **Backend (Flask)**: Provides REST API and Server-Sent Events (SSE) streaming for real-time AI responses. Handles data persistence via SQLAlchemy/SQLite and orchestrates the AI agent system.
- **Frontend (React + Vite)**: Single-page application that consumes the backend API. Uses Tailwind CSS for styling and includes real-time chat with SSE streaming.
- **Desktop (Tauri v2, Optional)**: Native desktop wrapper using the sidecar approach — Tauri renders the React frontend in a native webview and launches Flask as a child process. The existing browser-based workflow is preserved as a fallback.
- **AI Agent**: Tool-calling agent that can search the web, scrape URLs, search job boards, and manage job records. Supports multiple LLM providers (Anthropic, OpenAI, Gemini, Ollama).
- **User Profile System**: Markdown-based user profile with YAML frontmatter. Includes onboarding flow with a dedicated agent that interviews users to build their profile.
- **Data Directory Abstraction**: All data files (app.db, config.json, logs/, user_profile.md) are resolved via `backend/data_dir.get_data_dir()`. Defaults to the project root; overridden by the `DATA_DIR` environment variable (set automatically by Tauri to its appDataDir).

## Tech Stack

### Backend
- **Python 3.12+**: Core language
- **Flask**: Web framework with blueprints for route organization
- **Flask-SQLAlchemy**: ORM for database interactions
- **SQLite**: Development database (easily swappable for PostgreSQL/MySQL in production)
- **uv**: Fast Python package manager

### LLM Providers
- **Anthropic Claude**: Default provider (`claude-sonnet-4-5-20250929`)
- **OpenAI GPT**: Alternative provider (`gpt-4o`)
- **Google Gemini**: Alternative provider (`gemini-2.0-flash`)
- **Ollama**: Local model provider (default: `llama3.1`)

### Agent Tools
- **Tavily API**: Web search integration
- **Adzuna API**: Job board search (optional)
- **JSearch API**: Job board search via RapidAPI (optional, preferred over Adzuna)
- **BeautifulSoup**: HTML parsing for web scraping

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
│   │   └── chat.py                # Conversation and Message models
│   ├── resume_parser.py               # Resume parsing (PDF via PyMuPDF, DOCX via python-docx), parsed JSON storage
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── jobs.py                # CRUD endpoints for jobs
│   │   ├── chat.py                # Chat endpoints with SSE streaming
│   │   ├── profile.py             # User profile endpoints
│   │   ├── resume.py              # Resume upload, fetch, delete, LLM parse endpoints
│   │   └── config.py              # Config and health check endpoints
│   ├── llm/
│   │   ├── base.py                # LLMProvider ABC, StreamChunk, ToolCall dataclasses
│   │   ├── factory.py             # create_provider() factory function
│   │   ├── anthropic_provider.py  # Anthropic Claude implementation
│   │   ├── openai_provider.py     # OpenAI GPT implementation
│   │   ├── gemini_provider.py     # Google Gemini implementation
│   │   └── ollama_provider.py     # Ollama local model implementation
│   └── agent/
│       ├── tools.py               # AgentTools class + TOOL_DEFINITIONS
│       ├── agent.py               # Agent and OnboardingAgent classes
│       └── user_profile.py        # User profile file management
├── frontend/
│   ├── vite.config.js             # Vite config (React, Tailwind CSS plugin, proxy)
│   ├── package.json
│   └── src/
│       ├── main.jsx               # React entry point
│       ├── index.css              # Tailwind imports
│       ├── App.jsx                # App shell with routing and layout
│       ├── api.js                 # Centralized API client
│       ├── pages/
│       │   └── JobList.jsx        # Main dashboard
│       ├── components/
│       │   ├── JobForm.jsx        # Create/edit job form
│       │   ├── JobDetailPanel.jsx # Slide-out job detail viewer
│       │   ├── ChatPanel.jsx      # AI assistant slide-out panel
│       │   ├── ProfilePanel.jsx   # User profile slide-out panel
│       │   ├── SettingsPanel.jsx  # Settings configuration panel (includes ApiKeyGuide sub-component)
│       │   ├── SetupWizard.jsx    # First-time setup wizard (4-step modal)
│       │   ├── ModelCombobox.jsx  # Searchable model selection combobox
│       │   ├── HelpPanel.jsx      # Help panel with guides and tips
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
├── user_profile.md                # User profile file (gitignored)
└── CLAUDE.md                      # Claude Code instructions
```

### Key Files and Their Responsibilities

#### Backend

**`main.py`**: Entry point that calls `create_app()` and runs the Flask development server. Accepts `--data-dir` (sets `DATA_DIR` env var for custom data file location) and `--port` (default 5000) CLI arguments.

**`backend/data_dir.py`**: Centralized data directory resolver. `get_data_dir()` returns the directory where all runtime data files (app.db, config.json, logs/, user_profile.md) are stored. Uses `DATA_DIR` env var if set, otherwise defaults to the project root.

**`backend/app.py`**: App factory that creates and configures the Flask app, registers blueprints, and initializes the database.

**`backend/config.py`**: Centralized configuration loading from config.json file with environment variable fallback. Includes LLM provider settings, API keys, and logging configuration. Uses `get_data_dir()` for the database path.

**`backend/config_manager.py`**: Configuration file management utilities. Provides functions to read/write config.json, get/set individual config values, and mask sensitive data. Environment variables override file-based config. Config file path is resolved lazily via `get_data_dir()` to respect `DATA_DIR` set after import.

**`backend/database.py`**: SQLAlchemy instance shared across the app.

**`backend/models/job.py`**: Job model with fields for company, title, URL, status, salary range, location, remote type, tags, contact info, applied date, source, job fit rating, requirements, and nice-to-haves. Includes `to_dict()` for JSON serialization.

**`backend/models/chat.py`**: Conversation and Message models for chat persistence. Messages store role (user/assistant) and content.

**`backend/routes/jobs.py`**: CRUD blueprint for job management. Mounted at `/api/jobs`.

**`backend/routes/chat.py`**: Chat blueprint with SSE streaming. Mounted at `/api/chat`. Handles conversation creation, message sending, and agent response streaming.

**`backend/routes/profile.py`**: Profile blueprint for user profile CRUD and onboarding status. Mounted at `/api/profile`.

**`backend/routes/config.py`**: Configuration blueprint for settings management. Provides endpoints for getting/updating config, testing LLM connections, listing providers, and health checks. Mounted at `/api/config`.

**`backend/routes/resume.py`**: Resume upload blueprint. Handles file upload (multipart/form-data), parsing, storage, retrieval, and deletion. Supports PDF and DOCX files up to 10 MB. Also provides an LLM-powered parsing endpoint (`POST /api/resume/parse`) that uses `ResumeParsingAgent` to clean up raw extracted text and structure it into JSON. Mounted at `/api/resume`.

**`backend/resume_parser.py`**: Resume parsing utilities. Extracts plain text from PDF files (via PyMuPDF) and DOCX files (via python-docx, including table content). Provides file save/load/delete helpers with resume files stored in a `resumes/` subdirectory under the data dir. Also stores LLM-parsed structured JSON (`save_parsed_resume`, `get_parsed_resume`, `delete_parsed_resume`).

**`backend/llm/base.py`**: Abstract base class defining the interface all LLM providers must implement (`stream_with_tools`). Also defines `StreamChunk` and `ToolCall` dataclasses.

**`backend/llm/factory.py`**: `create_provider(provider_name, api_key, model)` factory function that instantiates the appropriate provider.

**`backend/llm/*_provider.py`**: Provider implementations. Each translates the generic tool format to the provider's native format and handles streaming responses.

**`backend/agent/tools.py`**: Defines all available tools (`web_search`, `job_search`, `scrape_url`, `create_job`, `list_jobs`, `read_user_profile`, `update_user_profile`, `read_resume`) with their schemas and execution logic. Tools are exposed via the `AgentTools` class.

**`backend/agent/agent.py`**: Main `Agent` class that runs the tool-calling loop. Takes a user message, calls the LLM, executes tools, and iterates until completion. Also includes `OnboardingAgent` subclass for the onboarding interview flow and `ResumeParsingAgent` for LLM-powered resume cleanup and JSON structuring. Injects resume availability status into the system prompt.

**`backend/agent/user_profile.py`**: User profile file management with YAML frontmatter parsing. Handles reading, writing, and onboarding status checking.

#### Frontend

**`frontend/src/main.jsx`**: React entry point that mounts `App`.

**`frontend/src/App.jsx`**: App shell with header navigation, layout, onboarding auto-start logic, and setup wizard management. Manages global state like `jobsVersion` for triggering list refreshes. On first launch, opens `SetupWizard` instead of Settings if the LLM is unconfigured and the user hasn't been onboarded.

**`frontend/src/api.js`**: Centralized API client with helper functions for all backend endpoints. All fetch calls go through this module. Includes `getApiBase()` which detects Tauri (via `window.__TAURI_INTERNALS__`) and returns absolute URLs to reach Flask directly, bypassing the Vite proxy.

**`frontend/src/pages/JobList.jsx`**: Main dashboard displaying job table with sortable columns, status badges, and inline add/edit/delete.

**`frontend/src/components/JobForm.jsx`**: Reusable form component for creating and editing jobs. Handles all job fields including requirements and nice-to-haves.

**`frontend/src/components/JobDetailPanel.jsx`**: Slide-out panel that displays comprehensive job details including requirements, nice-to-haves, salary range, location, and job fit rating. Shows all fields in a read-only format with markdown rendering.

**`frontend/src/components/ChatPanel.jsx`**: Slide-out AI assistant panel with SSE streaming, markdown rendering, and tool execution visibility. Includes `JOB_MUTATING_TOOLS` set for live job list refresh.

**`frontend/src/components/ProfilePanel.jsx`**: Slide-out user profile viewer/editor panel with resume upload section (PDF/DOCX). Users can upload, preview (Structured/Raw toggle), replace, or remove their resume. Auto-triggers LLM parsing on upload; includes a Re-parse button. `StructuredResumeView` sub-component renders parsed JSON as a rich formatted view. Also supports manual profile markdown editing.

**`frontend/src/components/SettingsPanel.jsx`**: Slide-out settings panel for configuring LLM provider, API keys, and integrations. Includes "Test Connection" functionality and saves to config.json. Contains `ApiKeyGuide` sub-component that renders expandable step-by-step instructions and a direct link for each key field (Anthropic, OpenAI, Gemini, Tavily, JSearch, Adzuna); renders nothing for Ollama (no key required).

**`frontend/src/components/ModelCombobox.jsx`**: Searchable combobox for selecting an LLM model. Fetches available models from the provider's API with a client-side cache (5-minute TTL). Falls back to free-text input if the API call fails or no API key is entered yet.

**`frontend/src/components/SetupWizard.jsx`**: Centered modal wizard for first-time setup. Four steps: welcome, provider selection (2×2 card grid), API key entry with always-visible inline how-to guide and test connection, and a done screen that launches onboarding. Requires a successful connection test before allowing the user to continue (Ollama skips the key requirement). Calls `onComplete()` to open onboarding chat or `onClose()` to dismiss.

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

Once the app is running, configure your LLM API key through the Settings panel (gear icon in the header).

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
  "integrations": {
    "search_api_key": "",
    "jsearch_api_key": "",
    "adzuna_app_id": "",
    "adzuna_app_key": "",
    "adzuna_country": "us"
  },
  "logging": {
    "level": "INFO"
  }
}
```

**Environment variable override (optional):**
```bash
export LLM_PROVIDER=anthropic
export LLM_API_KEY=your-api-key-here
export SEARCH_API_KEY=your-tavily-key
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

This stores all data files (app.db, config.json, logs/, user_profile.md) in the specified directory instead of the project root.

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

**SSE Event Types** (chat streaming):

- `text_delta`: `{"content": "..."}` — Incremental text from the LLM
- `tool_start`: `{"id": "...", "name": "...", "arguments": {...}}` — Tool execution starting
- `tool_result`: `{"id": "...", "name": "...", "result": {...}}` — Tool completed successfully
- `tool_error`: `{"id": "...", "name": "...", "error": "..."}` — Tool execution failed
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

### Resume API

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| POST | `/api/resume` | Upload resume (PDF/DOCX) | multipart/form-data with `file` field | `{filename, size, text, text_length}` |
| GET | `/api/resume` | Get saved resume info + text + structured data | — | `{resume: {filename, size, text, text_length, parsed} \| null}` |
| DELETE | `/api/resume` | Delete saved resume | — | `{status: "deleted" \| "no_resume"}` |
| POST | `/api/resume/parse` | Parse resume with LLM | — | `{parsed: {...}}` |

**Supported formats:** PDF (`.pdf`) and Microsoft Word (`.docx`). Maximum file size: 10 MB.

The raw text is extracted using PyMuPDF (PDF) or python-docx (DOCX, including table content). Resume files are stored in a `resumes/` subdirectory under the data directory.

The `POST /api/resume/parse` endpoint uses `ResumeParsingAgent` to send the raw extracted text to the configured LLM, which cleans up PDF/DOCX extraction artifacts (broken formatting, garbled characters, merged words) and returns structured JSON with fields like `contact_info`, `work_experience`, `education`, `skills`, `certifications`, `projects`, and more. The structured data is persisted as `resume_parsed.json` and returned by subsequent `GET /api/resume` calls.

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
  "integrations": {
    "search_api_key": "",
    "adzuna_app_id": "",
    "adzuna_app_key": "",
    "adzuna_country": "us",
    "jsearch_api_key": ""
  },
  "logging": {
    "level": "INFO"
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

## LLM Provider System

The LLM provider system uses an abstract factory pattern to support multiple AI providers with a unified interface.

### Architecture

1. **Abstract Base Class** (`backend/llm/base.py`): Defines `LLMProvider` ABC with `stream_with_tools()` method and optional `list_models()` static method
2. **Factory** (`backend/llm/factory.py`): `create_provider(provider, api_key, model)` instantiates the correct provider
3. **Provider Implementations**: Each provider translates generic tool schemas to its native format and handles streaming

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
```

Configuration is managed by `backend/config_manager.py` which reads from `config.json` and falls back to environment variables. The Settings UI provides a user-friendly interface for configuration.

### Adding a New Provider

1. Create `backend/llm/your_provider.py` extending `LLMProvider`
2. Implement `stream_with_tools(messages, tools, system_prompt="")`
3. Handle tool calling in the provider's native format
4. Yield `StreamChunk` objects with `delta` and/or `tool_calls`
5. Register in `factory.py`'s `create_provider()`

Example skeleton:

```python
from backend.llm.base import LLMProvider, StreamChunk, ToolCall

class YourProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = 'default-model'):
        self.api_key = api_key
        self.model = model

    def stream_with_tools(self, messages: list, tools: list, system_prompt: str = ""):
        # Convert tools to provider's format
        native_tools = self._convert_tools(tools)

        # Make streaming API call
        for chunk in self._stream_api_call(messages, native_tools, system_prompt):
            # Parse chunk and yield StreamChunk
            if chunk.has_text:
                yield StreamChunk(type="text", content=chunk.text)
            if chunk.has_tool_calls:
                yield StreamChunk(type="tool_calls", tool_calls=[
                    ToolCall(id=tc.id, name=tc.name, arguments=tc.arguments)
                    for tc in chunk.tool_calls
                ])
```

## Agent System

The agent system provides an iterative tool-calling loop that enables the AI to interact with external APIs and the database.

### Architecture

**Agent Loop** (`backend/agent/agent.py`):
1. User sends message
2. Agent calls LLM with system prompt + conversation history + tool definitions
3. LLM responds with text and/or tool calls
4. Agent executes tool calls via `AgentTools`
5. Tool results are added to conversation history
6. If LLM made tool calls, return to step 2
7. Stream final response to user

### Available Tools

Defined in `backend/agent/tools.py`:

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `web_search` | Search the web via Tavily API | `query`, `num_results` (opt) |
| `job_search` | Search job boards via JSearch/Adzuna | `query`, `location` (opt), `remote_only` (opt), `salary_min`/`salary_max` (opt), `provider` (opt) |
| `scrape_url` | Fetch and parse a web page | `url` |
| `create_job` | Add a job to the database | `company`, `title` (required); plus all optional job fields |
| `list_jobs` | List and filter tracked jobs | `status` (opt), `company` (opt), `title` (opt), `url` (opt), `limit` (opt) |
| `read_user_profile` | Read the user's profile markdown | — |
| `update_user_profile` | Update the user's profile | `content` |
| `read_resume` | Read the user's uploaded resume text | — |

### Tool Definitions

Tools are defined in `TOOL_DEFINITIONS` list with JSON Schema:

```python
TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the web for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    # ...
]
```

### User Profile Integration

The agent automatically reads the user profile at the start of each conversation and injects it into the system prompt. This allows the agent to personalize responses and provide better job recommendations.

The agent also proactively extracts job-search-relevant information from user messages and updates the profile via the `update_user_profile` tool (e.g., preferred job titles, locations, salary expectations).

### Onboarding Agent

`OnboardingAgent` is a subclass of `Agent` with a specialized system prompt that conducts an interview to build the user's profile. It asks about:
- Job search status and goals
- Preferred job titles and roles
- Skills and experience
- Location preferences and remote work preferences
- Salary expectations

Once complete, it sets the `onboarded: true` flag in the user profile frontmatter.

### Adding a New Tool

1. Define the tool in `TOOL_DEFINITIONS` with name, description, and JSON schema
2. Implement the tool method in `AgentTools` class
3. If the tool mutates jobs, add its name to `JOB_MUTATING_TOOLS` in `frontend/src/components/ChatPanel.jsx` to trigger live list refresh

Example:

```python
# In TOOL_DEFINITIONS
{
    "name": "update_job",
    "description": "Update an existing job",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "integer"},
            "field": {"type": "string"},
            "value": {"type": "string"}
        },
        "required": ["job_id", "field", "value"]
    }
}

# In AgentTools class
def update_job(self, job_id: int, field: str, value: str) -> dict:
    job = Job.query.get_or_404(job_id)
    setattr(job, field, value)
    db.session.commit()
    return job.to_dict()
```

Then in `frontend/src/components/ChatPanel.jsx`:

```javascript
const JOB_MUTATING_TOOLS = new Set(['create_job', 'update_job']);
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
  - `backend.agent.agent`: Agent loop, iterations, tool calls
  - `backend.agent.tools`: Tool execution details
  - `backend.llm.*`: Provider requests/responses
  - `backend.routes.chat`: Incoming messages, response completion

### Configuration Management

- **Primary method**: `config.json` managed via the Settings UI (never hardcode secrets)
- **Environment variable override**: Env vars take precedence over `config.json` for deployment flexibility
- **Defaults**: Provide sensible defaults in `backend/config_manager.py`
- **Validation**: Validate required config on app startup

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
SEARCH_API_KEY=your-tavily-key
JSEARCH_API_KEY=your-rapidapi-key
ADZUNA_APP_ID=your-app-id
ADZUNA_APP_KEY=your-app-key

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
