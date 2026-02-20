# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shortlist — a desktop application and web app to track and manage job applications. Users can add, edit, and delete job applications and track their status through the hiring pipeline. Includes an LLM-powered AI assistant that can research job postings, scrape URLs, search the web, and automatically add jobs to the database via a chat interface.

Available as a downloadable desktop app (via Tauri — the primary distribution method for regular users) or as a web app run from source (for developers). User-facing documentation (README, INSTALLATION.md) prioritizes the desktop download path, with "run from source" as an advanced alternative.

## Tech Stack

- **Backend:** Python 3.12+, Flask, Flask-SQLAlchemy, SQLite
- **LLM providers:** Anthropic, OpenAI, Google Gemini, Ollama (configurable via Settings UI or env vars)
- **Agent tools:** Tavily search API, BeautifulSoup web scraping, JSearch/Adzuna job search
- **Frontend:** React 19, Vite, Tailwind CSS 4
- **Desktop wrapper:** Tauri v2 (sidecar approach — Flask as child process, React in native webview)
- **Package management:** uv (Python), npm (JS)

## Key Commands

### Quick Start (Recommended)
- **Mac/Linux:** `./start.sh` — auto-checks dependencies, installs packages if needed, starts both servers, opens browser
- **Windows:** `start.bat` — auto-checks dependencies, installs packages if needed, starts both servers, opens browser

The start scripts handle everything automatically. Use the manual commands below only if you need fine-grained control.

### Backend (Manual)
- `uv sync` — install Python dependencies
- `uv run python main.py` — start Flask dev server (port 5000)
- `uv run python main.py --data-dir /path/to/dir` — start with custom data directory
- `uv run python main.py --port 8080` — start on a custom port

### Frontend (Manual)
- `cd frontend && npm install` — install JS dependencies
- `cd frontend && npm run dev` — start Vite dev server (port 3000)
- `cd frontend && npm run build` — production build (use to verify changes compile)

### Desktop Mode (Tauri)
- `npm run tauri:dev` — launch Tauri dev window (start Flask manually in a separate terminal first)
- `npm run tauri:build` — build production desktop app (run `./build_sidecar.sh` first to bundle Flask)
- `./build_sidecar.sh` — build Flask backend as a standalone binary for Tauri sidecar

## Project Structure

### Root
- `start.sh` — unified startup script for Mac/Linux (checks deps, installs packages, starts servers, opens browser)
- `start.bat` — unified startup script for Windows (checks deps, installs packages, starts servers, opens browser)
- `build_sidecar.sh` — builds Flask backend as a PyInstaller binary for Tauri sidecar (Mac/Linux)
- `build_sidecar.ps1` — builds Flask backend as a PyInstaller binary for Tauri sidecar (Windows)
- `config.json` — application configuration file (auto-created, gitignored)
- `app.db` — SQLite database (auto-created, gitignored)
- `user_profile.md` — user job search profile with YAML frontmatter (auto-created, gitignored)

### Backend
- `main.py` — entry point, runs Flask server (supports `--data-dir` and `--port` CLI args)
- `backend/data_dir.py` — centralized data directory resolver (`get_data_dir()`); uses `DATA_DIR` env var or defaults to project root
- `backend/app.py` — Flask app factory (`create_app`)
- `backend/config.py` — app configuration (Flask-specific settings)
- `backend/config_manager.py` — configuration file management (read/write `config.json`, env var fallback)
- `backend/database.py` — SQLAlchemy `db` instance
- `backend/models/job.py` — `Job` model (fields: `id`, `company`, `title`, `url`, `status`, `notes`, `salary_min`, `salary_max`, `location`, `remote_type`, `tags`, `contact_name`, `contact_email`, `applied_date`, `source`, `job_fit`, `created_at`, `updated_at`)
- `backend/routes/jobs.py` — CRUD blueprint (`jobs_bp` at `/api/jobs`)
- `backend/routes/chat.py` — Chat blueprint (`chat_bp` at `/api/chat`) with SSE streaming
- `backend/routes/config.py` — Configuration blueprint (`config_bp` at `/api/config`, `/api/health`)
- `backend/routes/profile.py` — Profile blueprint (`profile_bp` at `/api/profile`)
- `backend/routes/resume.py` — Resume upload blueprint (`resume_bp` at `/api/resume`) — upload, fetch, delete resume files; LLM-powered resume parsing endpoint
- `backend/resume_parser.py` — Resume parsing utilities (PDF via PyMuPDF, DOCX via python-docx); file save/load/delete helpers; parsed resume JSON storage (`save_parsed_resume`, `get_parsed_resume`, `delete_parsed_resume`)
- `backend/models/chat.py` — `Conversation` and `Message` models for chat persistence
- `backend/llm/base.py` — `LLMProvider` ABC, `StreamChunk`, `ToolCall` dataclasses
- `backend/llm/anthropic_provider.py` — Anthropic Claude provider
- `backend/llm/openai_provider.py` — OpenAI GPT provider
- `backend/llm/gemini_provider.py` — Google Gemini provider
- `backend/llm/ollama_provider.py` — Ollama local model provider
- `backend/llm/factory.py` — `create_provider()` factory function
- `backend/agent/tools.py` — `AgentTools` class + `TOOL_DEFINITIONS` (web_search, job_search, scrape_url, create_job, list_jobs, read_user_profile, update_user_profile, read_resume)
- `backend/agent/agent.py` — `Agent` class with iterative tool-calling loop; `OnboardingAgent` for user profile interview; `ResumeParsingAgent` for LLM-powered resume cleanup and JSON structuring; injects user profile and resume status into system prompt
- `backend/agent/user_profile.py` — User profile markdown file management with YAML frontmatter (onboarded flag with tri-state: `false`/`in_progress`/`true`), read/write/onboarding helpers

### Frontend
- `frontend/vite.config.js` — Vite config (React plugin, Tailwind CSS plugin, API proxy, Tauri-compatible settings)
- `frontend/src/main.jsx` — React entry point
- `frontend/src/index.css` — Tailwind CSS base import
- `frontend/src/App.jsx` — App shell with header, layout, settings auto-open, onboarding auto-start, and Tauri external link interceptor (opens http/https/mailto links in system browser)
- `frontend/src/api.js` — API helper with `getApiBase()` for Tauri URL resolution (`fetchJobs`, `createJob`, `updateJob`, `deleteJob`, chat functions, `streamMessage`, `fetchProfile`, `updateProfile`, config functions, onboarding functions, resume functions)
- `frontend/src/pages/JobList.jsx` — Main dashboard: job table with status badges, add/edit/delete
- `frontend/src/components/JobForm.jsx` — Reusable form for creating and editing jobs
- `frontend/src/components/ChatPanel.jsx` — Slide-out AI assistant chat panel with SSE streaming
- `frontend/src/components/ProfilePanel.jsx` — Slide-out user profile viewer/editor panel with resume upload section (PDF/DOCX)
- `frontend/src/components/SettingsPanel.jsx` — Slide-out settings panel for configuring LLM provider, API keys, and onboarding agent; includes `ApiKeyGuide` sub-component that renders expandable step-by-step instructions + direct links for each key field (Anthropic, OpenAI, Gemini, Tavily, JSearch, Adzuna); Ollama renders nothing (no key needed)
- `frontend/src/components/SetupWizard.jsx` — First-time setup wizard (centered modal, 4 steps: welcome → provider selection → API key entry with inline how-to guide + test connection → done); auto-opens for new users instead of Settings panel; calls `onComplete()` to launch onboarding chat or `onClose()` to dismiss; `pendingOnboarding` stays true on dismiss so the Settings manual-save path still triggers onboarding
- `frontend/src/components/ModelCombobox.jsx` — Searchable combobox for model selection; fetches available models from provider API, with client-side cache (5-min TTL) and graceful fallback to free-text input on error
- `frontend/src/components/HelpPanel.jsx` — Slide-out help panel with Getting Started, Job Tracking, AI Chat, API Key Guides, and Troubleshooting sections
- `frontend/src/components/UpdateBanner.jsx` — Auto-update notification banner (Tauri desktop only); shows version info, download progress, and restart button
- `frontend/src/components/Toast.jsx` — Toast notification system (`useToast` hook, `ToastContainer` component); used for error notifications with collapsible technical details
- `frontend/src/utils/errorClassifier.js` — Maps raw LLM/network error strings to user-friendly toast messages with actionable guidance (`classifyError`, `classifyNetworkError`)

### Tauri (Desktop Wrapper)
- `src-tauri/tauri.conf.json` — Tauri configuration (build commands, window settings, sidecar config)
- `src-tauri/Cargo.toml` — Rust dependencies (tauri 2, tauri-plugin-shell 2)
- `src-tauri/build.rs` — Tauri build script
- `src-tauri/src/main.rs` — Rust entry point
- `src-tauri/src/lib.rs` — Sidecar launch logic (spawns Flask backend with `--data-dir` pointing to appDataDir)
- `src-tauri/capabilities/default.json` — Shell permissions for sidecar spawning and opening external URLs

### CI/CD
- `.github/workflows/release.yml` — builds Tauri app for all platforms on `v*` tag push, creates draft GitHub Release
- `.github/workflows/ci.yml` — builds Tauri app on PRs to `main` (Linux + Windows only, no release upload)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/jobs` | List all jobs (newest first) |
| POST | `/api/jobs` | Create job (`company`, `title` required) |
| GET | `/api/jobs/:id` | Get single job |
| PATCH | `/api/jobs/:id` | Update job (partial) |
| DELETE | `/api/jobs/:id` | Delete job |
| GET | `/api/chat/conversations` | List conversations (newest first) |
| POST | `/api/chat/conversations` | Create conversation |
| GET | `/api/chat/conversations/:id` | Get conversation with messages |
| DELETE | `/api/chat/conversations/:id` | Delete conversation |
| POST | `/api/chat/conversations/:id/messages` | Send message, returns SSE stream |
| GET | `/api/profile` | Get user profile markdown content |
| PUT | `/api/profile` | Update user profile markdown content |
| GET | `/api/profile/onboarding-status` | Check if user has been onboarded |
| POST | `/api/profile/onboarding-status` | Set onboarding status |
| POST | `/api/chat/onboarding/conversations` | Create onboarding conversation |
| POST | `/api/chat/onboarding/conversations/:id/messages` | Send onboarding message, returns SSE stream |
| POST | `/api/chat/onboarding/kick` | Start onboarding (agent greeting), returns SSE stream |
| GET | `/api/config` | Get current configuration (with masked API keys) |
| POST | `/api/config` | Update configuration |
| POST | `/api/config/models` | List available models for a provider |
| POST | `/api/config/test` | Test LLM provider connection |
| GET | `/api/config/providers` | Get list of available LLM providers |
| POST | `/api/resume` | Upload resume (multipart/form-data, PDF/DOCX) |
| GET | `/api/resume` | Get saved resume info, parsed text, and structured data |
| DELETE | `/api/resume` | Delete saved resume |
| POST | `/api/resume/parse` | Parse resume with LLM (cleans up text, returns structured JSON) |
| GET | `/api/health` | Health check (returns 503 if LLM not configured) |

Job statuses: `saved`, `applied`, `interviewing`, `offer`, `rejected`
Remote types: `onsite`, `hybrid`, `remote` (or `null`)

Optional job fields: `salary_min` (int), `salary_max` (int), `location` (string), `remote_type` (string), `tags` (comma-separated string), `contact_name` (string), `contact_email` (string), `applied_date` (ISO date string), `source` (string), `job_fit` (int, 0-5 star rating), `requirements` (text, newline-separated), `nice_to_haves` (text, newline-separated)

### Configuration

**Primary method:** `config.json` file (auto-created in project root)

Users configure the app through the **Settings UI** (accessed via the gear icon in the top navigation). The Settings panel allows users to:
- Select LLM provider (Anthropic, OpenAI, Gemini, Ollama)
- Enter API keys
- Override default models
- Configure optional integrations (Tavily search, JSearch/Adzuna job search)
- Test their connection before saving

Configuration structure in `config.json`:
```json
{
  "llm": {
    "provider": "anthropic",
    "api_key": "sk-ant-...",
    "model": ""
  },
  "onboarding_llm": {
    "provider": "",
    "api_key": "",
    "model": ""
  },
  "integrations": {
    "search_api_key": "tvly-...",
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

**Fallback method:** Environment variables

Environment variables are checked first, then `config.json`. Useful for development or server deployments:
- `LLM_PROVIDER` — provider name: `anthropic` (default), `openai`, `gemini`, `ollama`
- `LLM_API_KEY` — API key for the chosen provider
- `LLM_MODEL` — optional model override (each provider has a sensible default)
- `ONBOARDING_LLM_PROVIDER` — optional, defaults to `LLM_PROVIDER`
- `ONBOARDING_LLM_API_KEY` — optional, defaults to `LLM_API_KEY`
- `ONBOARDING_LLM_MODEL` — optional, defaults to `LLM_MODEL` (use a cheaper model to save costs)
- `SEARCH_API_KEY` — Tavily API key for web search tool
- `ADZUNA_APP_ID` — Adzuna API application ID (for job search)
- `ADZUNA_APP_KEY` — Adzuna API application key (for job search)
- `ADZUNA_COUNTRY` — Adzuna country code (default: `us`)
- `JSEARCH_API_KEY` — RapidAPI key for JSearch API (for job search); preferred over Adzuna when both are configured
- `DATA_DIR` — directory for all data files (db, config, logs, profile); defaults to project root if unset

### Logging
- `LOG_LEVEL` — `DEBUG`, `INFO` (default), `WARNING`, `ERROR`
- Logs go to both the console and `logs/app.log` (file auto-rotated by the OS; directory auto-created)
- Set `LOG_LEVEL=DEBUG` to see full tool result payloads in the log
- Key loggers: `backend.agent.agent` (agent loop, iterations, tool calls), `backend.agent.tools` (tool execution details), `backend.llm.*` (provider requests/responses), `backend.routes.chat` (incoming messages, response completion)

### SSE Event Types (chat streaming)
- `text_delta` — `{"content": "..."}` — incremental text from the LLM
- `tool_start` — `{"id": "...", "name": "...", "arguments": {...}}` — tool execution starting
- `tool_result` — `{"id": "...", "name": "...", "result": {...}}` — tool completed successfully
- `tool_error` — `{"id": "...", "name": "...", "error": "..."}` — tool execution failed
- `done` — `{"content": "full text"}` — agent finished
- `onboarding_complete` — `{}` — onboarding interview finished (only in onboarding flow)
- `error` — `{"message": "..."}` — fatal error

## Conventions

### Configuration & Startup
- Use `./start.sh` (Mac/Linux) or `start.bat` (Windows) to start the app — these scripts handle everything automatically
- Configuration is stored in `config.json` in the project root (auto-created, gitignored)
- Users configure LLM and integrations through the **Settings UI** (gear icon in nav bar)
- Settings panel auto-opens on first launch if LLM is not configured
- Environment variables can override `config.json` values (useful for development/deployment)
- The `/api/health` endpoint returns 503 if LLM is not configured (used by frontend to trigger settings panel)

### Data Files & Storage
- All data files are resolved via `backend/data_dir.get_data_dir()` — defaults to project root, overridden by `DATA_DIR` env var
- `main.py --data-dir /path` sets `DATA_DIR` before app import; Tauri passes its `appDataDir` this way
- SQLite database file is `app.db` in the data directory (gitignored, auto-created)
- User profile file is `user_profile.md` in the data directory (gitignored, auto-created with default template)
- User profile uses YAML frontmatter for metadata (`onboarded: false/in_progress/true`); body is markdown

### User Onboarding Flow
- On first visit, if LLM is not configured, Settings panel auto-opens
- After saving settings, if user hasn't been onboarded, the onboarding interview auto-starts
- Onboarding uses a separate LLM config (`onboarding_llm.*` in `config.json`) so a cheaper model can be used
- The AI agent interviews the user and fills their profile via the `update_user_profile` tool
- Onboarding state is tracked in the profile frontmatter as a tri-state: `false` → `in_progress` → `true`
- If the user closes the app mid-onboarding (`in_progress`), reopening detects this and resumes onboarding with a contextual kick message so the agent continues from where it left off instead of restarting
- Users can view and manually edit their profile anytime via the Profile panel in the UI
- The AI agent reads the user profile on every turn and injects it into the system prompt
- The agent proactively extracts job-search-relevant info from user messages and updates the profile

### API & Architecture
- Backend API routes are prefixed with `/api/`
- Frontend Vite dev server proxies `/api` to Flask at `localhost:5000`
- Frontend pages live in `frontend/src/pages/`, reusable components in `frontend/src/components/`
- API helper functions in `frontend/src/api.js` — all backend calls go through this module
- **Live job list refresh:** `ChatPanel` has a `JOB_MUTATING_TOOLS` set that tracks which agent tools modify job data (currently `create_job`). When a `tool_result` SSE event fires for one of these tools, the panel calls `onJobsChanged()` which bumps a `jobsVersion` counter in `App`, causing `JobList` to re-fetch. **When adding a new agent tool that creates, updates, or deletes jobs, add its name to `JOB_MUTATING_TOOLS` in `frontend/src/components/ChatPanel.jsx`.**

## Best Practices

### General
- Keep changes focused — one feature or fix per commit
- Run `cd frontend && npm run build` to verify frontend changes compile before committing
- Prefer editing existing files over creating new ones to avoid file bloat
- After implementing a feature or fix, update `docs/TODO.md` to mark completed items as done (`[x]`) and **condense the item to a single line** — remove sub-bullets and detailed descriptions, keeping only the essential summary of what was done
- After implementing a feature or fix, update `docs/CHANGELOG.md` under `[Unreleased]` with a concise entry describing the change
- After making changes, update any relevant documentation (CLAUDE.md, README.md, INSTALLATION.md, etc.) to reflect the current state of the codebase

### Git Commits
- Use **conventional commit** format: `type: description`
- Common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `style`
- Examples: `feat: add job search filtering`, `fix: resolve onboarding deadlock`, `docs: update installation guide`
- Use lowercase after the type prefix: `docs: add feature` not `docs: Add feature`
- Keep subject line concise (under 72 characters), use body for detailed explanations if needed

### Backend (Python)
- Follow PEP 8 style conventions
- Use Flask blueprints for new route groups; register them in `backend/app.py`
- Add new models in `backend/models/` and import them in `backend/models/__init__.py`
- Use SQLAlchemy model methods (e.g., `to_dict()`) to serialize responses — keep route handlers thin
- Validate required fields in route handlers before creating/updating records

### Frontend (React/JS)
- Use functional components with hooks (`useState`, `useEffect`)
- Place page-level components in `frontend/src/pages/`, shared UI in `frontend/src/components/`
- All API calls go through `frontend/src/api.js` — never call `fetch` directly in components
- Use Tailwind CSS utility classes for styling — no separate CSS files per component
- Keep components focused: if a component grows beyond ~150 lines, consider extracting subcomponents

## CI/CD & Releases

### Creating a Release
1. Ensure version is updated in `package.json`, `frontend/package.json`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, and `pyproject.toml`
2. Tag and push:
   ```bash
   git tag v0.4.0
   git push origin v0.4.0
   ```
3. The `release.yml` workflow builds for all 3 platforms (Linux x86_64, macOS ARM64, Windows x86_64)
4. A **draft** GitHub Release is created with installer artifacts
5. Go to GitHub Releases, review the draft, and click **Publish**

### Workflows
- **`.github/workflows/release.yml`** — triggered by `v*` tags or manual `workflow_dispatch`; builds all platforms and uploads artifacts to a draft release
- **`.github/workflows/ci.yml`** — triggered on PRs to `main`; builds Linux + Windows only (no release upload) to verify the app compiles

### Sidecar Build Scripts
- `build_sidecar.sh` — Mac/Linux: detects arch, runs PyInstaller, places binary in `src-tauri/binaries/`
- `build_sidecar.ps1` — Windows PowerShell equivalent of the above

### Auto-Update System
The desktop app uses `tauri-plugin-updater` to check for updates on startup. When a new version is published on GitHub Releases, users see a banner with the new version number, a download progress bar, and a restart button.

**How it works:**
1. On startup, the app fetches `latest.json` from the latest GitHub Release
2. If a newer version exists, an `UpdateBanner` component appears at the top of the page
3. User clicks "Update Now" to download and install, or "Later" to dismiss
4. After download completes, user clicks "Restart Now" to apply the update

**Signing key setup (required for auto-updates to work):**
```bash
npx @tauri-apps/cli signer generate -w ~/.tauri/shortlist.key
```
This generates a keypair. Then:
1. Copy the **public key** (printed to stdout) into `src-tauri/tauri.conf.json` → `plugins.updater.pubkey` (replacing `PLACEHOLDER_PUBLIC_KEY`)
2. Add the **private key file contents** as GitHub secret `TAURI_SIGNING_PRIVATE_KEY`
3. Add the **password** (if set) as GitHub secret `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`

**Important:** The `latest.json` endpoint (`/releases/latest/download/latest.json`) only works with **published** releases, not drafts. After the CI creates a draft release, you must publish it on GitHub for auto-updates to detect it.

### Code Signing (Future)
- macOS: add Apple Developer secrets (`APPLE_CERTIFICATE`, `APPLE_SIGNING_IDENTITY`, etc.) to repo settings; uncomment env vars in `release.yml`

## Documentation

After making changes, update this file (`CLAUDE.md`) to reflect:
- New or modified files in the project structure section
- New API endpoints or changes to existing ones
- New commands, dependencies, or conventions
- Any architectural decisions that future contributors should know about

Keeping this file accurate ensures Claude Code (and human developers) can work with the codebase effectively.
