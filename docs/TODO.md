# TODO

## UX Improvements

- [x] **Make tool use errors less scary** — amber warning icon with collapsible details instead of red error blocks
- [x] **Improve onboarding intro message** — agent coaches users to give detailed, full-sentence answers
- [x] **Clarify API key requirements** — Tavily marked as recommended, help text updated across Settings/Help/Installation
- [x] **Simplify API key acquisition** — Added first-time setup wizard with inline how-to guides
  (step-by-step instructions + direct links) for all API key fields in both the wizard and Settings
  panel
- [x] **Onboarding resumption checks profile** — Tri-state onboarding status (`not_started`/`in_progress`/`completed`) in profile frontmatter; agent reads existing profile and continues from where it left off when user reopens mid-onboarding
- [x] **User-friendly error notifications** — Toast notification system with error classification; LLM errors shown as actionable toasts instead of chat messages
- [x] **Resizable panels** — All slide-out panels can be dragged wider/thinner via left-edge handle; widths persist in localStorage


## Features

- [x] **Direct download links in README and releases** — README download table links directly to latest installers; release workflow auto-generates clickable download links per platform
- [x] **Improve initial setup wizard with all API keys** — Setup wizard now includes a dedicated step for Tavily and JSearch API keys with inline how-to guides and direct sign-up links

- [ ] **Dedicated visual interface for job search results**
  - When the agent finds jobs, they should be presented in a standardized, visually distinct format — not just a text chat bubble
  - Currently different models format found jobs differently; results should have a consistent, appealing layout
  - Design a dedicated job results component separate from the agent's speech bubble (design TBD)

- [ ] **Job search sub-agent for better result coverage**
  - Currently web/job search results go directly into the agent's context during its ReAct loop, limiting output to ~4-7 suggestions regardless of market size
  - Create a sub-agent that receives all raw search results and evaluates each individually (or in small batches)
  - Sub-agent builds a comprehensive results list that is handed back to the main agent
  - Goal: "find AI jobs in SF" should return significantly more results than "find AI jobs in Charlotte, NC"
  - Exact sub-agent process TBD

- [ ] **Improve agent orchestration**
  - Provide more guidance to the agent using an architected workflow rather than relying on the
    agent to just work
  - Create sub-agents for particular common tasks such as job searching, job evaluation, and job
    adding

- [ ] **Job application preparation**
  - Add per-job preparation components (interview prep, resume tailoring, cover letter drafts)
  - Store preparation notes/materials linked to each job
  - Agent tools to generate and manage prep content

- [x] **Resume uploading and parsing** — PDF/DOCX upload via Profile panel, parsed text available to AI agent via `read_resume` tool
- [x] **AI resume parsing agent** — LLM cleans up raw PDF/DOCX text artifacts and structures into JSON; auto-triggers on upload with structured preview in Profile panel

## Desktop App (Phase 2 Remaining)

- [x] **Auto-Update System** — Integrated `tauri-plugin-updater` with update check on startup, download progress banner, and restart prompt; requires signing key setup for production releases

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

- [ ] **Code signing certificates setup**
  - macOS and Windows code signing not yet configured

## Future (Phase 3)

- [ ] **Multi-user support** — accounts, cloud sync, shared job boards, collaboration
- [ ] **Advanced analytics** — success rates, time-to-hire, salary analysis, market insights
- [ ] **Browser extension** — one-click save from LinkedIn/Indeed, auto-fill, quick notes
- [ ] **Mobile app** — React Native or Flutter, job tracking on the go, push notifications
