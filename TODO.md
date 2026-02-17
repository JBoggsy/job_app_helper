# TODO

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

- [ ] **Polish repository for GitHub publication**
  - Expand README to better explain project to potential users (what it does, why use it, quick demo/screenshots)
  - Move technical components (project structure, tech stack, API endpoints, conventions) to new DEVELOPMENT.md
  - Fill in DEVELOPMENT.md as comprehensive onboarding guide for project developers
  - Add LICENSE file (choose appropriate open source license)
  - Add CHANGELOG.md to track version history and notable changes
  - Add CONTRIBUTING.md with guidelines for contributors
  - Consider adding .github/ISSUE_TEMPLATE and PULL_REQUEST_TEMPLATE

- [ ] **Simplify installation and startup**
  - Create single startup script/command that runs both backend and frontend
  - One-line installation command (e.g., install script that runs `uv sync` and `cd frontend && npm install`)
  - Build infrastructure for Windows/Mac standalone builds (consider PyInstaller/Electron or Tauri)
  - Create release workflow for downloadable executables
  - Document installation process clearly in README

- [ ] **In-app help and documentation**
  - Add Help section in app UI (help icon/button in header)
  - Create interactive tutorial/walkthrough for first-time users
  - Build feature wiki or help docs within app (how to use chat, job tracking, etc.)
  - Add setup and configuration guides, especially for LLM providers:
    - How to get API keys (Anthropic, OpenAI, Gemini, Ollama)
    - How to set environment variables or configure API keys
    - How to select and configure different models
    - Troubleshooting common setup issues

- [ ] **In-app LLM provider and model selection**
  - Add settings panel in UI for selecting LLM provider and model
  - Store LLM configuration in database or user config file (not just env vars)
  - Allow changing provider/model without restarting app
  - Show available models for each provider
  - Validate API keys and show connection status
  - Separate configuration for chat agent vs onboarding agent