# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.0] - 2026-02-26

### Added
- **Application todo extraction** — Extract application steps (documents, questions, assessments) from job postings via LLM. Todos are tracked per-job with checkboxes in the Job Detail Panel. Auto-extracted during job enrichment, on-demand via "Extract from posting" button, or via AI agent `extract_application_todos` tool. Manual todo creation also supported.
- **ApplicationTodo model** — New `backend/models/application_todo.py` with category, title, description, completed, sort_order fields
- **Todo extractor module** — New `backend/todo_extractor.py` with LLM prompt for extracting application steps from scraped job text
- **Todo API endpoints** — CRUD routes at `/api/jobs/:id/todos` plus `/api/jobs/:id/todos/extract` for LLM extraction
- **Agent tool** — `extract_application_todos` tool lets the AI extract and save application steps for any tracked job
- **Application Steps UI** — Interactive checklist in Job Detail Panel grouped by category with progress bar, expand/collapse descriptions, and inline add/delete

## [0.9.1] - 2026-02-26

### Added
- **Automatic job enrichment** — When adding a job to the tracker (via search results panel or agent `create_job` tool), the system automatically scrapes the job posting URL and uses an LLM to extract missing fields (salary, location, remote type, requirements, nice-to-haves, tags). Uses the cheaper search LLM config. Gracefully falls back to original data if scraping or LLM fails.
- **Job enrichment module** — New `backend/job_enrichment.py` with `enrich_job_data()` function for URL scraping + LLM-based field extraction
- **Enrichment loading state** — "Add to Tracker" button now shows spinner and "Enriching & Adding..." text during the enrichment process

## [0.9.0] - 2026-02-26

### Added
- **Job search sub-agent with results panel** — When the user asks the AI to search for jobs, a specialized sub-agent runs multiple searches, evaluates each job against the user profile (0-5 star rating), and populates a slide-out results panel next to the chat. Results are persistent per-conversation and each can be added to the job tracker with one click.
- **SearchResult model** — New `backend/models/search_result.py` for per-conversation job search results with fit rating, description, and tracker promotion state
- **Job search sub-agent** — New `backend/agent/job_search_agent.py` with `LangChainJobSearchAgent` that searches, scrapes, evaluates, and collects qualifying jobs (>=3 stars) via `add_search_result` tool
- **Main agent search tools** — `run_job_search` tool delegates to sub-agent; `list_search_results` tool reads results for highlight commentary
- **Search results API** — `GET /api/chat/conversations/:id/search-results` and `POST .../add-to-tracker` endpoints
- **SearchResultsPanel component** — Slide-out panel with collapsible result cards, star ratings, fit reasons, and "Add to Tracker" buttons
- **Search SSE events** — `search_started`, `search_result_added`, `search_progress`, `search_completed` events for real-time panel updates
- **Search LLM config** — Separate `search_llm` configuration for the job search sub-agent (defaults to main LLM, recommended to use a cheaper model)
- **Real-time search progress in chat** — Sub-agent search progress events streamed to the chat interface for visibility
- **Direct download links in releases** — Release workflow now generates clickable download links for each platform's installer in the GitHub Release description
- **Direct download links in README** — Download table now links directly to the latest release artifacts instead of just linking to the Releases page
- **Integration keys in setup wizard** — First-time setup wizard now includes a step for Tavily search and JSearch API keys with inline how-to guides and direct sign-up links

## [0.8.0] - 2026-02-21

Complete migration from custom LLM provider layer to LangChain — all 4 providers (Anthropic, OpenAI, Gemini, Ollama) now use a unified `BaseChatModel` interface. No user-facing API or frontend changes; SSE events, tool behavior, and all endpoints remain identical.

### Added
- **LangChain integration** — Added `langchain-core`, `langchain`, `langchain-anthropic`, `langchain-openai`, `langchain-google-genai`, `langchain-ollama` dependencies
- **LangChain model factory** — New `backend/llm/langchain_factory.py` with `create_langchain_model()` that returns a `BaseChatModel` instance for any supported provider
- **`@agent_tool` decorator** — New decorator for tool methods in `backend/agent/tools.py` with Pydantic input schemas colocated alongside business logic; `to_langchain_tools()` auto-generates LangChain `StructuredTool` instances — adding a new tool now requires a single decorated method instead of edits across 3 files
- **LangChain agent classes** — New `backend/agent/langchain_agent.py` with `LangChainAgent`, `LangChainOnboardingAgent`, and `LangChainResumeParser` using `BaseChatModel.stream()` / `.invoke()` with streaming tool-call chunk accumulation
- **Model listing module** — New `backend/llm/model_listing.py` with standalone `list_models()` functions for each provider using raw SDKs
- **Migration guide** — New `docs/LANGCHAIN_MIGRATION.md` documenting the full 6-phase migration plan and architecture decisions

### Changed
- **Routes wired to LangChain** — `backend/routes/chat.py`, `backend/routes/config.py`, and `backend/routes/resume.py` now use LangChain models and agents instead of the old custom provider/agent code; SSE events and API contracts unchanged
- **Config class slimmed** — `backend/config.py` now only includes Flask-consumed settings (`SQLALCHEMY_*`, `SECRET_KEY`, `LOG_LEVEL`); dead LLM/integration attributes removed
- **Tool definitions consolidated** — Tool methods in `AgentTools` are now public (no underscore prefix); `execute()` auto-dispatches via `getattr()` and decorator detection
- **Developer docs updated** — `docs/DEVELOPMENT.md` rewritten with LangChain architecture: project structure, LLM provider system, agent system, and "Adding a New Provider/Tool" guides

### Removed
- **Old custom LLM providers** — Deleted `backend/llm/base.py` (`LLMProvider` ABC, `StreamChunk`, `ToolCall`), `anthropic_provider.py`, `openai_provider.py`, `gemini_provider.py`, `ollama_provider.py`
- **Old agent classes** — Deleted `backend/agent/agent.py` (`Agent`, `OnboardingAgent`, `ResumeParsingAgent`) — replaced by LangChain equivalents
- **Dead modules** — Deleted `backend/llm/factory.py` (dead re-export layer) and `backend/agent/langchain_tools.py` (intermediate wrapper consolidated into `@agent_tool`)
- **`TOOL_DEFINITIONS` dict** — Removed ~170-line manual tool definition dictionary, replaced by `@agent_tool` decorator metadata
- **Unused imports** — Cleaned up stale imports across `langchain_agent.py`, `routes/config.py`, `tools.py`, `resume_parser.py`

## [0.7.3] - 2026-02-21

### Added
- **Resizable panels** — All slide-out panels (AI Assistant, Profile, Settings, Help) can now be resized by dragging their left edge; widths persist across sessions via localStorage

### Improved
- **Sticky header with Add Job button** — Header bar now stays fixed at the top when scrolling; "+Add Job" button moved from the job list into the header for easy access at all times
- **Resilient web scraping** — Scrape tool now uses cloudscraper (handles Cloudflare anti-bot challenges), realistic Sec-* browser headers, updated User-Agents, random retry delays, and falls back to Tavily Extract API when direct scraping fails — significantly reducing 403 errors on job posting sites

## [0.7.1] - 2026-02-19

### Added
- **AI resume parsing agent** — After uploading a resume, an LLM-powered agent automatically cleans up the raw extracted text (fixing PDF artifacts, broken formatting, garbled characters) and structures it into JSON with contact info, work experience, education, skills, certifications, projects, and more. Structured data displayed in a rich preview in the Profile panel with Structured/Raw toggle and Re-parse button. New `POST /api/resume/parse` endpoint and `ResumeParsingAgent` class.

### Improved
- **User-friendly error notifications** — LLM errors (quota exhaustion, invalid API key, rate limiting, timeouts, etc.) now appear as toast notifications instead of inline chat messages, with actionable guidance on how to fix each issue; raw technical details available behind a collapsible toggle

## [0.7.0] - 2026-02-19

### Added
- **Resume uploading and parsing** — Users can upload a resume (PDF or DOCX) via the Profile panel. The file is parsed and stored so the AI agent can reference it when evaluating job fit and searching for jobs. New `read_resume` agent tool, `/api/resume` endpoints, and resume section in ProfilePanel.

### Fixed
- **Onboarding resumption checks profile** — When the user closes and re-opens the app mid-onboarding, the agent now reads the existing profile and continues from where it left off instead of starting over. Uses a tri-state onboarding status (`not_started` / `in_progress` / `completed`) in the profile frontmatter.

## [0.6.3] - 2026-02-19

### Fixed
- **Flask sidecar not terminating on desktop app close** — PyInstaller `--onefile` binaries fork on Linux: the bootloader is the PID Tauri tracks, but the actual Flask process runs as a child. `CommandChild::kill()` only killed the bootloader, orphaning the Flask child. Now kills the full process tree via `pkill -KILL -P <pid>` (Unix) / `taskkill /T` (Windows) before killing the bootloader. Also cleans up stale sidecar processes on startup and handles both `WindowEvent::Destroyed` and `RunEvent::Exit` for belt-and-suspenders reliability.
- **CI uv cache causing false build failures** — Disabled uv cache in CI workflows to prevent stale cache entries from breaking builds

## [0.6.2] - 2026-02-19

### Added
- **Model name discovery** — Model override fields in Settings and Setup Wizard now show a searchable dropdown populated from each provider's API; gracefully falls back to free-text input when the API call fails or no key is entered yet

### Improved
- **Onboarding chat panel can now be closed** — Users can dismiss the chat panel during onboarding to explore the app or change settings; reopening resumes the conversation where it left off; AI Assistant button pulses to indicate an active onboarding session

### Fixed
- **Masked API keys sent to model discovery endpoint** — The model dropdown was failing with 401 errors because the Settings panel was sending masked API keys (e.g. `sk-a****xyz`) to the models endpoint; the backend now resolves the real key from config when it detects a masked value

## [0.6.1] - 2026-02-18

### Fixed
- Flask sidecar process now terminates when the desktop window closes (previously persisted as an orphan process after the app exited)

## [0.6.0] - 2026-02-18

### Added
- **First-time setup wizard** — New centered modal wizard (4 steps: welcome → provider selection → API key entry with inline how-to guide + test connection → done) replaces the auto-open Settings panel for new users; closes itself and launches onboarding chat on completion
- **Inline API key guides in Settings** — "How do I get this key?" expandable guides with step-by-step instructions and direct links added below each API key input (LLM provider, Tavily, JSearch, Adzuna)

## [0.5.0] - 2026-02-18

### Added
- **Auto-update system** — Desktop app checks for updates on startup using `tauri-plugin-updater`; shows a banner with version info, download progress, and restart button; requires signing key setup (see CLAUDE.md) for production releases; `latest.json` manifest auto-generated by CI release workflow

### Improved
- **Tool error display** — Tool errors in chat now show as an amber warning icon instead of a red X, with error details hidden behind a collapsible "Details" toggle; less alarming for non-technical users when errors are non-critical
- **Onboarding interview quality** — The onboarding agent now coaches users upfront to give detailed, full-sentence answers (e.g., "Think of this like talking to a career consultant"), leading to richer user profiles
- **API key guidance** — Tavily is now marked as "Recommended" in the Settings panel with an amber badge, and help text across Settings, Help, and Installation docs clarifies that it's required for web search; JSearch/Adzuna descriptions also improved

### Fixed
- **Timezone display bug** — Job timestamps now include explicit UTC offset (`+00:00`) so browsers parse them correctly instead of treating bare ISO strings as local time
- **External links in Tauri desktop app** — Added `@tauri-apps/plugin-shell` and a global click interceptor in `App.jsx` that opens http/https/mailto links in the system browser; added `shell:allow-open` permission to Tauri capabilities
- **scrape_url 403 errors** — Replaced bare User-Agent with a pool of realistic browser User-Agent strings, added browser-like headers, and retry logic (up to 3 attempts with UA rotation) to reduce blocks from job posting sites

## [0.4.2] - 2026-02-18

### Fixed
- **CI/CD workflow build failures** — Resolved issues in the release and CI workflows that caused builds to fail

## [0.4.1] - 2026-02-18

### Added

**CI/CD Pipeline**
- GitHub Actions release workflow (`.github/workflows/release.yml`) — builds Tauri desktop app for Linux x86_64, macOS ARM64, and Windows x86_64 on `v*` tag push; creates draft GitHub Release with installer artifacts
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) — builds Linux + Windows on PRs to `main` to verify the app compiles
- Windows sidecar build script (`build_sidecar.ps1`) — PowerShell equivalent of `build_sidecar.sh` for building Flask backend as standalone binary on Windows

### Changed

**Documentation Restructure for Desktop Distribution**
- `docs/INSTALLATION.md` restructured into two-track layout: "Desktop App (Recommended)" for regular users and "Running from Source (Advanced)" for developers
- `README.md` hero section restructured with prominent Download section and platform table; "Run from Source" demoted to brief subsection
- `docs/DEVELOPMENT.md` updated with CI/CD Pipeline section covering workflows, build scripts, and release process
- `docs/CONTRIBUTING.md` updated with desktop app notes in bug reports and PR checklist
- `.github/ISSUE_TEMPLATE/bug_report.md` updated with installation method and app version fields
- `CLAUDE.md` updated to reflect desktop app as primary distribution method
- `docs/TODO.md` updated with completed Phase 2 items and version annotations

## [0.4.0] - 2026-02-18

### Added

**Tauri v2 Desktop App (Optional)**
- Added Tauri v2 as an optional native desktop wrapper using the sidecar approach
- Tauri renders the React frontend in a native webview and launches Flask as a child process
- Data files (app.db, config.json, logs/, user_profile.md) are stored in platform-standard directories when running under Tauri
- Existing browser-based workflow (`start.sh` / `start.bat`) preserved as fallback

**Data Directory Abstraction**
- New `backend/data_dir.py` module with `get_data_dir()` for centralized data directory resolution
- `DATA_DIR` environment variable support to override data file location
- `main.py` now accepts `--data-dir` and `--port` CLI arguments
- All data file paths (database, config, logs, user profile) now resolve through `get_data_dir()`

**Frontend Tauri Compatibility**
- Added `getApiBase()` in `frontend/src/api.js` for absolute URL resolution in Tauri webview (detects Tauri via `window.__TAURI_INTERNALS__`)
- Tauri-compatible Vite config settings (`clearScreen`, `envPrefix`, `strictPort`)

**Build & Tooling**
- `build_sidecar.sh` script for bundling Flask backend as a standalone binary via PyInstaller with Tauri target-triple naming
- Tauri project scaffolding (`src-tauri/`) with Rust sidecar launch logic, capabilities, and configuration
- `npm run tauri:dev` and `npm run tauri:build` scripts in `frontend/package.json`
- PyInstaller added as a dev dependency

**Agent Improvements**
- Increased agent `MAX_ITERATIONS` from 10 to 25 for handling complex multi-step tasks

### Changed

**Project Cleanup**
- Moved developer/contributor documentation into `docs/` directory (CHANGELOG, CONTRIBUTING, DEVELOPMENT, INSTALLATION, TODO, config.example.json)
- Updated all cross-references in README.md and other docs to reflect new locations
- README.md and CLAUDE.md remain at project root per GitHub/Claude Code conventions

## [0.3.0] - 2026-02-18

### Added

**In-App Help Panel**
- New Help panel accessible via the `?` button in the header
- Getting Started section with a 3-step guide (configure LLM → onboarding → add jobs)
- Job Tracking section covering statuses, fields, and how to add/edit/delete jobs
- AI Chat Assistant section with example prompts and tool descriptions
- Getting API Keys section with direct links for all supported providers and integrations (Anthropic, OpenAI, Gemini, Ollama, Tavily, JSearch, Adzuna)
- Troubleshooting section with solutions for the most common issues

**Onboarding Agent Configuration UI**
- New collapsible "Onboarding Agent" section in the Settings panel
- Allows configuring a separate (cheaper) LLM provider, API key, and model for the one-time onboarding interview
- Defaults to the main AI Assistant configuration when left blank
- Backend support for `onboarding_llm.*` configuration was already present; this adds the missing UI

## [0.2.2] - 2026-02-17

### Fixed

**Windows Compatibility - uv PATH Issue**
- Fixed `uv` command not being recognized after installation on Windows
- `start.bat` now automatically uses `python -m uv` as fallback when `uv` command is not in PATH
- Added `UV_CMD` variable used consistently throughout the script
- Script notifies users they can use `uv` directly after restarting terminal
- Added troubleshooting section to README for uv PATH issues

This fix resolves the issue where `uv` installs successfully via `pip install uv` but the command is not recognized until the terminal is restarted, due to Windows PATH caching.

## [0.2.1] - 2026-02-17

### Fixed

**Windows Compatibility**
- Fixed Python detection on Windows when Microsoft Store app execution aliases are enabled
- `start.bat` now automatically tries `python3` command as fallback when `python` is intercepted by Windows Store
- Added clear error messages guiding Windows users to disable app execution aliases
- Added troubleshooting section to README specifically for Windows Python detection issues

This fix resolves the common issue where `python --version` fails on Windows even when Python is installed, due to Windows Store aliases intercepting the command.

## [0.2.0] - 2026-02-17

### Added

**Simplified Installation & Startup**
- Unified startup scripts for one-command setup (`start.sh` for Mac/Linux, `start.bat` for Windows)
- Automatic dependency checking with friendly installation guidance
- Auto-install of missing dependencies where possible
- Concurrent backend and frontend server startup
- Automatic browser opening to application URL
- Graceful shutdown handling with Ctrl+C

**Configuration System**
- File-based configuration system using `config.json`
- Configuration management API (`backend/config_manager.py`)
- REST API endpoints for reading and updating configuration (`/api/config`)
- LLM connection testing endpoint (`/api/config/test`)
- Health check endpoint (`/api/health`)
- Configuration template file (`config.example.json`)
- Environment variables now override file-based config (backwards compatible)

**Settings UI**
- New Settings panel in the application UI (gear icon in header)
- Visual LLM provider selection (Anthropic, OpenAI, Gemini, Ollama)
- API key management with masked input fields
- Real-time connection testing with "Test Connection" button
- Integration settings (Tavily Search, JSearch, Adzuna)
- In-app configuration with persistent storage
- Clear success/error messages for user actions

**Error Handling & UX**
- Graceful error messages when LLM is not configured
- User-friendly guidance to open Settings when configuration is missing
- Better error messages for LLM provider initialization failures
- Health check endpoint showing configuration status
- Improved dependency version checking in startup scripts

**Documentation**
- Completely restructured README.md with "Easy Setup" section
- Settings UI documented as primary configuration method
- New Troubleshooting section with common issues and solutions
- Updated DEVELOPMENT.md with config.json system details
- Removed deprecated `.env` file references
- Added configuration priority documentation (defaults → config.json → env vars)
- Updated API reference with Config API endpoints

### Changed
- Configuration system now uses `config.json` as primary method (environment variables still supported)
- Removed `example.env` in favor of `config.example.json`
- README.md restructured to prioritize user experience over technical details
- DEVELOPMENT.md updated with Quick Start section for new contributors
- Startup workflow simplified from multi-terminal process to single command

### Deprecated
- Direct `.env` file usage (environment variables still work but config.json is recommended for local development)

## [0.1.0] - 2026-02-17

Initial release of Shortlist - a full-stack web application for tracking job applications with an AI-powered assistant.

### Added

**Core Features**
- Flask backend with SQLAlchemy and SQLite database
- React frontend with Vite and Tailwind CSS
- Job CRUD API endpoints with comprehensive job tracking
- Extended job fields: salary range, location, remote type, tags, contact info, applied date, source
- Job requirements and nice-to-haves fields (newline-separated)
- AI-powered job fit rating field (0-5 stars)
- Sortable columns in job list table
- Job detail panel with markdown rendering

**AI Assistant**
- Multi-LLM provider support: Anthropic Claude, OpenAI GPT, Google Gemini, Ollama
- LLM provider abstraction layer with factory pattern
- Agent system with iterative tool-calling loop
- Slide-out chat panel with Server-Sent Events (SSE) streaming
- Stream cancellation with stop button
- Message separation and markdown rendering in chat panel
- Live job list refresh after AI creates jobs

**Agent Tools**
- `web_search` - Search the web via Tavily API
- `job_search` - Search job boards (Adzuna and JSearch via RapidAPI)
- `scrape_url` - Fetch and parse web pages
- `create_job` - Add jobs to the database
- `list_jobs` - List and filter jobs with enhanced capabilities
- `read_user_profile` - Read user profile
- `update_user_profile` - Update user profile with extracted information

**User Profile System**
- User profile with YAML frontmatter for metadata
- Onboarding interview flow with dedicated OnboardingAgent
- Automatic profile reading on each agent turn for personalized responses
- Proactive profile updates via agent tools
- Profile panel in UI for viewing and manually editing user profile
- Separate LLM configuration for onboarding (`ONBOARDING_LLM_*` env vars)

**Infrastructure**
- Comprehensive logging system with file and console output
- Structured logging infrastructure with configurable log levels
- Dotenv support for environment variable configuration

**Documentation**
- User-focused README with screenshots and quick start guide
- Comprehensive DEVELOPMENT.md for contributors
- MIT License
- Contributing guidelines and code of conduct
- GitHub issue templates (bug report, feature request)
- GitHub pull request template
- Complete API reference and architecture documentation

### Changed
- Migrated Gemini provider from legacy SDK to `google-genai` package
- Improved chat tool ordering for better user experience
- Enhanced chat panel with better message formatting

### Fixed
- Tool ordering issues in chat interface
