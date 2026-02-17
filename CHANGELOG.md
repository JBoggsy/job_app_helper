# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- User profile system with YAML frontmatter for metadata
- Onboarding interview flow with dedicated OnboardingAgent
- Automatic profile reading on each agent turn for personalized responses
- Proactive profile updates via `update_user_profile` tool
- Profile panel in UI for viewing and manually editing user profile
- Job search API integrations (Adzuna and JSearch via RapidAPI)
- `job_search` agent tool for searching job boards
- AI-powered job fit rating field (0-5 stars)
- Job requirements and nice-to-haves fields (newline-separated)
- Job detail panel with markdown rendering
- Comprehensive logging system with file and console output
- Structured logging infrastructure with configurable log levels
- Sortable columns in job list table
- Stream cancellation with stop button
- Live job list refresh after AI creates jobs (via `JOB_MUTATING_TOOLS`)
- Enhanced `list_jobs` tool with filtering capabilities (status, limit)
- Message separation and markdown rendering in chat panel
- Dotenv support for environment variable configuration
- Separate LLM configuration for onboarding (`ONBOARDING_LLM_*` env vars)
- Multi-LLM provider support: Anthropic Claude, OpenAI GPT, Google Gemini, Ollama
- LLM provider abstraction layer with factory pattern
- Slide-out chat panel with Server-Sent Events (SSE) streaming
- Agent system with tool-calling loop
- Agent tools: `web_search`, `scrape_url`, `create_job`, `list_jobs`, `read_user_profile`, `update_user_profile`
- Extended job fields: salary range, location, remote type, tags, contact info, applied date, source
- Frontend job dashboard with React and Tailwind CSS
- Flask backend with SQLAlchemy and SQLite database
- Job CRUD API endpoints

### Changed
- Migrated Gemini provider from legacy SDK to `google-genai` package
- Improved chat tool ordering for better user experience
- Enhanced chat panel with better message formatting

### Fixed
- Tool ordering issues in chat interface

## [0.1.0] - 2026-01-15

### Added
- Initial project skeleton with Flask backend and React frontend
- Basic job tracking functionality
- Job model with company, title, URL, status, and notes fields
- REST API for job CRUD operations
- React frontend with Vite build tool
