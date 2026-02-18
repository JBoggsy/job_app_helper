# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

Initial release of Job Application Helper - a full-stack web application for tracking job applications with an AI-powered assistant.

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
