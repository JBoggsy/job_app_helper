# TODO

## UX Improvements

- [x] **Make tool use errors less scary** — amber warning icon with collapsible details instead of red error blocks
- [x] **Improve onboarding intro message** — agent coaches users to give detailed, full-sentence answers
- [x] **Clarify API key requirements** — Tavily marked as recommended, help text updated across Settings/Help/Installation
- [x] **Simplify API key acquisition** — Added first-time setup wizard with inline how-to guides
  (step-by-step instructions + direct links) for all API key fields in both the wizard and Settings
  panel
- [x] **Onboarding resumption checks profile** — Tri-state onboarding status (`not_started`/`in_progress`/`completed`) in profile frontmatter; agent reads existing profile and continues from where it left off when user reopens mid-onboarding


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
