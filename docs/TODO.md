# TODO

## Completed

- [x] Make tool use errors less scary (v0.5.0)
- [x] Improve onboarding intro message (v0.5.0)
- [x] Clarify API key requirements (v0.5.0)
- [x] Simplify API key acquisition — first-time setup wizard with inline how-to guides (v0.6.0)
- [x] Onboarding resumption checks profile — tri-state status in profile frontmatter (v0.7.0)
- [x] User-friendly error notifications — toast system with error classification (v0.7.1)
- [x] Resizable panels — drag-to-resize with localStorage persistence (v0.7.3)
- [x] Direct download links in README and releases
- [x] Integration keys step in setup wizard (Tavily, JSearch)
- [x] Resume uploading and parsing — PDF/DOCX upload with AI agent access (v0.7.0)
- [x] AI resume parsing agent — structured JSON extraction from resumes (v0.7.1)
- [x] Auto-update system — Tauri updater with download progress banner (v0.5.0)
- [x] Dedicated visual interface for job search results (v0.9.0)
- [x] Job search sub-agent for better result coverage (v0.9.0)
- [x] Main agent delegates job searches to specialized sub-agent via `run_job_search` tool (v0.9.0)

## Features

- [x] **Better job adding** — Jobs added to tracker are auto-enriched by scraping the posting URL and extracting missing fields via LLM

- [ ] **Job application preparation**
  - Add per-job preparation components (interview prep, resume tailoring, cover letter drafts)
  - Store preparation notes/materials linked to each job
  - Agent tools to generate and manage prep content

## Desktop App

- [ ] **Native OS Integration**
  - System tray icon with quick actions
  - Native notifications for job status changes
  - Native file picker for resume upload
  - OS-specific menu bar integration

- [ ] **Desktop-Specific Features**
  - Offline mode (work without internet, sync later)
  - Multiple workspace/profile support
  - Data import/export (JSON, CSV)
  - Backup and restore functionality
