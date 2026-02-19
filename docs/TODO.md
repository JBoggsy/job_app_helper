# TODO

## UX Improvements

- [ ] **Make tool use errors less scary**
  - Currently displayed as red blocks of text that alarm non-technical users
  - Tool errors are often non-critical (e.g., a scrape fails but the agent retries or works around it)
  - Redesign to use a subtle warning style instead of alarming error blocks
  - Consider collapsing error details behind an expandable "Details" toggle

- [ ] **Improve onboarding intro message**
  - Have the agent tell the user at the outset that the onboarding process works better if they:
    - Write full sentences with lots of detail
    - Treat it like they're really working with a job consultant
  - Non-technical users tend to give terse answers; coaching them upfront improves profile quality

- [ ] **Clarify API key requirements in installation guide**
  - Make it clear that Tavily is required for the AI assistant's web search to work
  - JSearch and/or Adzuna are optional but recommended for job searching
  - Update INSTALLATION.md and the Settings panel help text accordingly

- [ ] **Explore ways to simplify API key acquisition**
  - Current flow requires users to visit multiple external sites and copy-paste keys
  - Ideas: direct links to signup pages, embedded iframes, OAuth flows, or bundled free-tier keys
  - Research what's feasible given provider TOS constraints

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

- [ ] **Auto-Update System**
  - Integrate Tauri's built-in updater
  - Check for updates on startup (optional/configurable)
  - Download and apply updates in background
  - Changelog display in update prompt

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
