# TODO

## 🚨 Urgent Bugfixes

## Features

- [ ] **Improve agent orchestration**
  - Provide more guidance to the agent using an architected workflow rather than relying on the
    agent to just work
  - Create sub-agents for particular common tasks such as job searching, job evaluation, and job
    adding

- [ ] **Job application preparation**
  - Add per-job preparation components (interview prep, resume tailoring, cover letter drafts)
  - Store preparation notes/materials linked to each job
  - Agent tools to generate and manage prep content

- [ ] **Resume uploading and parsing**
  - Add ability for user to upload resume, which will be parsed and used to inform job search

## Polish & Publication

### Phase 1: Quick Wins

- [x] **Polish repository for GitHub publication** (v0.1.0)
  - Expand README to better explain project to potential users (what it does, why use it, quick demo/screenshots)
  - Move technical components (project structure, tech stack, API endpoints, conventions) to new DEVELOPMENT.md
  - Fill in DEVELOPMENT.md as comprehensive onboarding guide for project developers
  - Add LICENSE file (MIT)
  - Add CHANGELOG.md to track version history and notable changes
  - Add CONTRIBUTING.md with guidelines for contributors
  - Add .github/ISSUE_TEMPLATE and PULL_REQUEST_TEMPLATE
  - Add application screenshots to docs/screenshots/

- [x] **Simplify installation and startup** (v0.2.0-v0.2.2)
  - Create single startup script/command that runs both backend and frontend (`start.sh`, `start.bat`)
  - Automatic dependency checking with friendly error messages
  - Auto-install missing dependencies where possible
  - Document installation process clearly in README
  - Add troubleshooting section for common issues
  - Handle Windows-specific issues (Python Store aliases, uv PATH)

- [x] **In-app configuration** (v0.2.0)
  - Add Settings panel in UI for LLM provider and API key configuration
  - Store LLM configuration in config.json file (not just env vars)
  - Show available LLM providers with their default models
  - Validate API keys with "Test Connection" button
  - Support for optional integrations (Tavily, JSearch, Adzuna)
  - Environment variables override config file for production deployments

- [x] **In-app help and documentation**
  - Add Help section in app UI (help icon/button in header) ✓
  - Build feature wiki or help docs within app (how to use chat, job tracking, etc.) ✓
  - In-app guides for getting API keys (Anthropic, OpenAI, Gemini, Ollama, Tavily, JSearch, Adzuna) ✓
  - Troubleshooting section in Help panel ✓
  - Interactive tutorial/walkthrough: skipped (static help panel covers first-time user needs)
  - Inline error message links: skipped (help panel accessible from header at all times)

- [x] **Configuration improvements**
  - Allow changing LLM provider/model without restarting app (hot reload) ✓ (LLM provider created fresh per-request; already worked)
  - Separate configuration UI for onboarding agent vs chat agent ✓ (added collapsible Onboarding Agent section in Settings)
  - Show current API usage/costs: skipped (complex per-provider, out of scope for Phase 1)
  - Support for multiple API keys: skipped (out of scope for Phase 1)

### Phase 2: Standalone Desktop Application

**Goal**: Package as a true desktop app - no Python/Node.js installation required

- [ ] **Tauri Migration**
  - Migrate from Flask dev server to Tauri desktop app framework
  - Embed Python backend using PyInstaller or similar
  - Use existing React frontend with Tauri webview
  - Replace HTTP/SSE with Tauri IPC (inter-process communication)
  - Maintain feature parity with web version

- [ ] **Platform-Specific Installers**
  - Windows: `.exe` installer with MSI option
  - macOS: `.dmg` installer with code signing
  - Linux: `.AppImage`, `.deb`, and `.rpm` packages
  - Include all dependencies (Python runtime, SQLite, etc.)
  - No separate backend/frontend setup required

- [ ] **Auto-Update System**
  - Integrate Tauri's built-in updater
  - Check for updates on startup (optional/configurable)
  - Download and apply updates in background
  - Changelog display in update prompt
  - Rollback capability for failed updates

- [ ] **Native OS Integration**
  - System tray icon with quick actions
  - Native notifications for job status changes
  - Native file picker for resume upload
  - OS-specific menu bar integration
  - Platform-native dialogs and UI elements

- [ ] **Desktop-Specific Features**
  - Local SQLite database (no external database needed)
  - Offline mode (work without internet, sync later)
  - Multiple workspace/profile support
  - Data import/export (JSON, CSV)
  - Backup and restore functionality

- [ ] **Developer Experience**
  - Hot reload for development
  - Build scripts for all platforms
  - CI/CD pipeline for automated releases
  - Code signing certificates setup
  - Release artifact publishing to GitHub Releases

- [ ] **Documentation Updates**
  - Installation guide for standalone app
  - Building from source instructions
  - Troubleshooting for desktop app issues
  - Migration guide from web version

### Phase 3: Enhanced Features (Future)

- [ ] **Multi-user support**
  - User accounts and authentication
  - Cloud sync across devices
  - Shared job boards for teams
  - Collaboration features

- [ ] **Advanced analytics**
  - Application success rate tracking
  - Time-to-hire metrics
  - Salary range analysis
  - Job market insights

- [ ] **Browser extension**
  - One-click job saving from LinkedIn, Indeed, etc.
  - Auto-fill application forms
  - Quick notes on job postings

- [ ] **Mobile app**
  - React Native or Flutter mobile app
  - Job tracking on the go
  - Push notifications for deadlines