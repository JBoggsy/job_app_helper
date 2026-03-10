# UI Redesign Report — Page-Based Architecture with Document Editor

## Executive Summary

The current Shortlist UI is a single-page application with one visible page (the job list) and five slide-out panels (Chat, Profile, Settings, Help, SearchResults). All state is managed in `App.jsx` via boolean flags (`chatOpen`, `profileOpen`, `settingsOpen`, `helpOpen`). There is no client-side router — no `react-router-dom` dependency exists.

This report proposes migrating to a **page-based architecture** with client-side routing, where the AI chat panel is the only persistent overlay. The document editor (Option C from the Resume & Cover Letter report) becomes a dedicated page with a side-by-side editor + chat layout.

---

## 1. Current UI Architecture

### 1.1 Layout Structure

```
┌──────────────────────────────────────────────┐
│ Header (sticky)                              │
│ [Add Job] [Help] [Settings] [Profile] [Chat] │
├──────────────────────────────────────────────┤
│                                              │
│   JobList (max-w-5xl, centered)              │
│   ├── Sort/filter controls                   │
│   ├── Job table rows                         │
│   └── JobDetailPanel (inline overlay)        │
│                                              │
└──────────────────────────────────────────────┘

        Slide-out panels (right-anchored, z-50):
        ┌─────────────┐
        │ ChatPanel    │ ← resizable, has SearchResultsPanel companion
        │ ProfilePanel │ ← resizable
        │ SettingsPanel│ ← resizable
        │ HelpPanel    │ ← resizable
        └─────────────┘
```

### 1.2 Key Characteristics

- **No router**: App.jsx renders everything; panels toggle via boolean state
- **Panel-per-feature**: Each feature area (chat, profile, settings, help) is a slide-out panel with backdrop overlay, resize handle, close button
- **State explosion in App.jsx**: 11 `useState` calls just for panel/modal visibility and flow control (`chatOpen`, `profileOpen`, `settingsOpen`, `helpOpen`, `onboarding`, `onboardingChecked`, `pendingOnboarding`, `wizardOpen`, `jobsVersion`, `showAddForm`, `updateInfo`)
- **Shared pattern**: Every panel uses `useResizablePanel` hook, has a backdrop div, identical header/close layout
- **Panel conflicts**: Multiple panels can open simultaneously but compete for screen space; no coordination between them
- **Single content area**: The only "page" is the job list. Everything else is an overlay.
- **JobDetailPanel** is rendered inline within JobList (not a slide-out), appearing as an overlay within the main content area

### 1.3 Problems with Current Design

1. **Cluttered header**: 5 buttons in the nav bar, each opening a different panel
2. **Panel stacking**: Opening Chat + SearchResults + clicking a job detail = overlapping panels with no clear hierarchy
3. **No deep linking**: Can't link to a specific settings section, help topic, or job detail
4. **Poor extensibility**: Every new feature = new boolean in App.jsx + new panel component + new header button
5. **App.jsx is a god component**: Orchestrates all panels, onboarding flow, health checks, update banner, error handling, and job state
6. **Mobile unfriendly**: Slide-out panels don't work well on narrow screens; multiple panels are unusable

---

## 2. Proposed Architecture

### 2.1 Page Structure

```
/                       → Home (dashboard)
/jobs                   → Job Tracker (current JobList, full-featured)
/jobs/:id               → Job Detail (expanded view, replaces JobDetailPanel overlay)
/jobs/:id/documents/:type → Document Editor (side-by-side editor + chat)
/settings               → Settings (full page, replaces SettingsPanel)
/profile                → Profile (full page, replaces ProfilePanel)
/help                   → Help (full page, replaces HelpPanel)
```

### 2.2 Layout Diagram

```
┌──────────────────────────────────────────────────────────┐
│ Navigation Bar (sticky)                                  │
│ [Logo/Home] [Jobs] [Profile] [Settings] [Help] [Chat●]  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│   <Outlet />  ← React Router renders current page here   │
│                                                          │
│   (Home | JobTracker | JobDetail | DocumentEditor |      │
│    Settings | Profile | Help)                            │
│                                                          │
└──────────────────────────────────────────────────────────┘

        Chat Panel (persistent overlay, right-anchored):
        ┌──────────────┐
        │ ChatPanel     │  ← only slide-out panel remaining
        │ (resizable)   │  ← persists across page navigation
        │               │  ← includes SearchResultsPanel companion
        └──────────────┘
```

### 2.3 Component Hierarchy

```
App.jsx
├── NavigationBar          (sticky top bar with route links + chat toggle)
├── UpdateBanner           (Tauri only, conditional)
├── ToastContainer         (global notifications)
├── SetupWizard            (first-run modal, conditional)
├── <Routes>
│   ├── / → HomePage
│   │   ├── QuickSettings  (LLM status card, key config shortcuts)
│   │   ├── RecentJobs     (5 most recently modified jobs)
│   │   └── RecentDocuments(recently edited cover letters/resumes)
│   │
│   ├── /jobs → JobTrackerPage
│   │   ├── JobFilters     (search, status filter, sort)
│   │   └── JobTable       (sortable table with document indicators)
│   │
│   ├── /jobs/:id → JobDetailPage
│   │   ├── JobHeader      (company, title, status, actions)
│   │   ├── JobMetadata    (salary, location, remote, tags, contacts)
│   │   ├── JobNotes       (editable notes section)
│   │   ├── ApplicationTodos (todo list with categories)
│   │   └── JobDocuments   (cover letter/resume cards → link to editor)
│   │
│   ├── /jobs/:id/documents/:type → DocumentEditorPage
│   │   ├── EditorToolbar  (save, undo, redo, version history, export)
│   │   ├── TextEditor     (main editing area — rich text)
│   │   └── VersionHistory (sidebar or dropdown)
│   │
│   ├── /settings → SettingsPage
│   │   ├── LLMSettings    (provider, API key, model)
│   │   ├── AgentSettings  (design mode, per-mode LLM config)
│   │   ├── IntegrationSettings (Tavily, RapidAPI)
│   │   └── LoggingSettings
│   │
│   ├── /profile → ProfilePage
│   │   ├── ProfileEditor  (markdown editor for user profile)
│   │   └── ResumeSection  (upload, view, parse)
│   │
│   └── /help → HelpPage
│       ├── GettingStarted
│       ├── JobTracking
│       ├── AIChat
│       └── Troubleshooting
│
└── ChatPanel              (persistent overlay, outside <Routes>)
    └── SearchResultsPanel (companion panel, conditional)
```

### 2.4 Navigation Bar

The header transitions from action buttons to a proper navigation bar:

```
┌─────────────────────────────────────────────────────────────┐
│ 📋 Shortlist    Jobs   Profile   Settings   Help    [💬 AI] │
│                  ▔▔▔▔                                       │
│             (active indicator under current page)           │
└─────────────────────────────────────────────────────────────┘
```

- **Left**: App logo/name (links to home)
- **Center**: Page links with active state indicator (underline or highlight)
- **Right**: Chat toggle button (the only button that opens a panel overlay)
- The "Add Job" button moves into the JobTrackerPage itself (contextual action, not global)
- On narrow screens, the nav collapses to a hamburger menu

---

## 3. Document Editor Page (Option C)

### 3.1 Layout

The document editor page is the centerpiece of this redesign. It implements the "real-time side-by-side editing" from Option C of the Resume & Cover Letter report.

```
┌──────────────────────────────────────────────────────────┐
│ Nav Bar                                              [💬] │
├──────────────────────────────────────────────────────────┤
│ Editor Toolbar                                           │
│ [← Back to Job] [Save ✓] [Undo] [Redo] [v3 ▼] [Export] │
├────────────────────────────┬─────────────────────────────┤
│                            │                             │
│   Text Editor              │   Chat Panel                │
│   (rich text editing)      │   (contextual to document)  │
│                            │                             │
│   Dear Hiring Manager,     │   User: Make the opening    │
│                            │   paragraph more impactful   │
│   I am writing to express  │                             │
│   my interest in the       │   Agent: I've updated the   │
│   Software Engineer role   │   opening. Here's what I    │
│   at Acme Corp...          │   changed: [diff preview]   │
│                            │                             │
│                            │   [View Changes] [Accept]   │
│                            │                             │
├────────────────────────────┴─────────────────────────────┤
│ Status: Cover Letter for Acme Corp – SWE │ v3 │ Saved    │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Key Features

**Text Editor (left pane)**
- Rich text editing powered by a library like **Tiptap** (ProseMirror-based, React-native, extensible, MIT licensed) or **Plate** (also ProseMirror, more opinionated toward Tailwind)
- Standard editing features: bold, italic, bullet lists, headings, undo/redo
- Auto-save with debounce (creates new version after idle period + manual save button)
- Clean document-like appearance (generous margins, readable font, proper heading hierarchy)
- Keyboard shortcuts: Ctrl+S save, Ctrl+Z undo, Ctrl+Shift+Z redo

**Chat Panel (right pane)**
- The global ChatPanel is reused but scoped to the current document context
- When on the document editor page, the chat panel docks into the right pane instead of floating as a slide-out overlay
- The agent is automatically aware of the document being edited (the document content is included in context via `get_job_document`)
- Agent edits to the document automatically refresh the editor (via `document_saved` SSE event)
- Agent can highlight the specific section it changed (stretch goal)

**Version History**
- Dropdown in the toolbar showing all versions with timestamps and edit summaries
- Click a version to view it (read-only)
- "Restore" button to promote an old version as the new latest
- Diff view between any two versions (using a lightweight diff library)

**Export**
- Copy to clipboard (plain text)
- Download as `.txt` or `.md`
- Future: PDF/DOCX export via backend endpoint

### 3.3 Editor ↔ Agent Interaction Flow

```
User opens /jobs/42/documents/cover_letter
  │
  ├─ Editor loads latest version from GET /api/jobs/42/documents?type=cover_letter
  ├─ Chat panel opens in document-aware mode
  │
  ├─ User edits directly in the editor
  │   └─ On save: POST /api/jobs/42/documents (content, editSummary="Manual edit")
  │       └─ New version created, toolbar version indicator updates
  │
  ├─ User types in chat: "Make the tone more confident"
  │   └─ Agent calls get_job_document → reads latest version
  │   └─ Agent produces new content
  │   └─ Agent calls save_job_document → new version saved
  │   └─ Backend emits document_saved SSE event
  │   └─ Editor receives event → reloads content → user sees changes
  │   └─ Chat shows summary: "Updated cover letter (v4). Made tone more assertive."
  │
  └─ User can undo agent changes by restoring previous version
```

### 3.4 Rich Text Editor Evaluation

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| **Tiptap** (v2) | ProseMirror-based, excellent React support, highly extensible, great docs, MIT core | Pro extensions paid (but not needed for our use case) | **Recommended** |
| **Plate** | ProseMirror-based, Tailwind-first, headless UI components | Newer, smaller community | Good alternative |
| **Lexical** (Meta) | Fast, accessible, React-native | Steeper learning curve, less mature ecosystem | Overengineered for this use case |
| **Milkdown** | Markdown-first, plugin system | Smaller community, fewer resources | Decent if markdown-only is acceptable |
| Plain `<textarea>` | Zero dependencies, simple | No formatting, poor UX for documents | Only for v0/prototype |

**Recommendation: Tiptap v2.** It's the most mature ProseMirror wrapper for React, has excellent Tailwind integration, and the free tier includes everything we need (bold, italic, lists, headings, undo/redo, placeholder text). The `@tiptap/starter-kit` package covers all standard formatting. It also supports collaborative editing extensions if we ever want real-time co-editing.

---

## 4. Migration Strategy

### 4.1 New Dependencies

```
npm install react-router-dom @tiptap/react @tiptap/starter-kit @tiptap/extension-placeholder
```

### 4.2 Phased Implementation

#### Phase 1: Router Foundation & Page Shells

**Goal:** Introduce React Router, create page shell components, move existing panel content into pages. Chat remains the only panel.

**Changes:**

| File | Change |
|------|--------|
| `package.json` | Add `react-router-dom` |
| `main.jsx` | Wrap `<App>` in `<BrowserRouter>` |
| `App.jsx` | Replace panel state management with `<Routes>` + `<Outlet>`. Keep ChatPanel as overlay. Remove `settingsOpen`, `profileOpen`, `helpOpen` state. |
| `NavigationBar.jsx` | **New.** `<NavLink>` components for each route, chat toggle button |
| `pages/HomePage.jsx` | **New.** Dashboard with quick stats, recent jobs, recent documents |
| `pages/JobTrackerPage.jsx` | **New.** Wraps existing `JobList` content. "Add Job" button moves here. |
| `pages/JobDetailPage.jsx` | **New.** Wraps existing `JobDetailPanel` content as a full page. Uses `useParams()` for job ID. |
| `pages/SettingsPage.jsx` | **New.** Moves `SettingsPanel` content into a full page layout (no slide-out wrapper, no backdrop, no resize handle). |
| `pages/ProfilePage.jsx` | **New.** Moves `ProfilePanel` content into a full page layout. |
| `pages/HelpPage.jsx` | **New.** Moves `HelpPanel` content into a full page layout. |

**App.jsx after Phase 1 (simplified):**
```jsx
function App() {
  const [chatOpen, setChatOpen] = useState(false);
  const [onboarding, setOnboarding] = useState(false);
  // ... onboarding/wizard state (minimal)

  return (
    <div className="min-h-screen bg-gray-100">
      <NavigationBar onChatToggle={() => setChatOpen(!chatOpen)} chatOpen={chatOpen} />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Outlet />
      </main>
      <ChatPanel isOpen={chatOpen} onClose={() => setChatOpen(false)} ... />
      <SetupWizard ... />
      <ToastContainer ... />
    </div>
  );
}
```

**Migration approach for panels → pages:** Extract the inner content of each panel (everything inside the slide-out wrapper) into a standalone component. The page component just renders this content in a normal page layout. The old panel component can be deleted. This is mostly a cut-and-paste with removal of the panel chrome (backdrop, resize handle, close button, fixed positioning).

#### Phase 2: Document Editor Page

**Goal:** Build the document editor with side-by-side chat. Wire up the backend SSE events.

**Changes:**

| File | Change |
|------|--------|
| `package.json` | Add `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-placeholder` |
| `pages/DocumentEditorPage.jsx` | **New.** Main editor page with toolbar, Tiptap editor, docked chat. Uses `useParams()` for job ID and doc type. |
| `components/DocumentEditor.jsx` | **New.** Tiptap editor wrapper component with formatting toolbar. |
| `components/EditorToolbar.jsx` | **New.** Save, undo, redo, version selector, export buttons. |
| `components/VersionHistory.jsx` | **New.** Dropdown/sidebar showing document versions. |
| `api.js` | Add `fetchJobDocument`, `fetchDocumentHistory`, `saveJobDocument`, `deleteJobDocument` |
| `backend/models/job.py` | Add `has_cover_letter`/`has_resume` to `to_dict()` |
| `backend/routes/jobs.py` | Query document presence for job list |
| `backend/agent/tools/job_documents.py` | Add `document_saved` SSE event emission |
| `ChatPanel.jsx` | Handle `document_saved` SSE event; support "docked mode" for document editor page |
| `pages/JobDetailPage.jsx` | Add documents section with links to `/jobs/:id/documents/:type` |
| `pages/JobTrackerPage.jsx` | Add document indicator icons to job rows |

#### Phase 3: Polish & Enhanced Features

**Goal:** Diff view, export, version restore, improved document formatting, responsive design.

**Changes:**

| Feature | Implementation |
|---------|---------------|
| Diff view | Add a lightweight diff library (e.g., `diff` npm package). Compare any two versions in a split view. |
| Export | Backend endpoint using `python-docx` or `weasyprint` for PDF/DOCX generation. Frontend download button. |
| Version restore | "Restore this version" button that creates a new version with the old content. |
| Responsive design | Stacked layout on narrow screens (editor above, chat below). Collapsible nav. |
| Document templates | Pre-loaded cover letter/resume templates selectable when creating a new document. |

### 4.3 Tauri Compatibility

React Router uses client-side routing with the History API. Tauri's webview supports this natively — no special configuration needed. However, the Vite config needs a `historyApiFallback` equivalent:

```js
// vite.config.js — add to dev server config
server: {
  historyApiFallback: true // Vite calls this via the default SPA behavior
}
```

For production builds, Tauri loads `index.html` locally, which already works with client-side routing since all routes are handled by React Router (no server-side routing needed).

---

## 5. State Management Considerations

### 5.1 Current State (All in App.jsx)

The current App.jsx manages 11+ state variables. With routing, most panel visibility state disappears entirely — the URL becomes the source of truth for which "page" is shown.

### 5.2 Proposed State Distribution

| State | Location | Rationale |
|-------|----------|-----------|
| Chat open/closed | App.jsx (persists across pages) | Chat is the only global overlay |
| Onboarding flow | App.jsx (persists across pages) | Global flow, not page-specific |
| Jobs data | JobTrackerPage (local) | Only needed on that page; `jobsVersion` counter for refresh |
| Job detail | JobDetailPage (local, from `useParams`) | Route param drives data fetch |
| Document content | DocumentEditorPage (local) | Editor state is page-scoped |
| Settings config | SettingsPage (local) | Fetch on mount, save on submit |
| Profile content | ProfilePage (local) | Fetch on mount, save on submit |
| Toast notifications | App.jsx (global) | Cross-page notifications |

### 5.3 Cross-Page Communication

Two features require cross-page communication:

1. **Agent creates/edits a job → job list should refresh when user navigates back.** Solution: The ChatPanel (global) can maintain a `dirtyJobs` flag. When the user navigates to the job tracker, it checks this flag and refreshes if needed. Alternatively, always re-fetch on mount (simplest).

2. **Agent saves a document → document editor should refresh.** Solution: The ChatPanel processes `document_saved` SSE events. When on the document editor page, the ChatPanel calls a callback (provided via React context or prop) to notify the editor. When not on the editor page, the event is noted but no action is needed.

**Recommended approach:** Use a lightweight **React Context** (`AppContext`) to hold a small set of cross-cutting state:
```jsx
const AppContext = createContext();

// Provides:
// - chatOpen / setChatOpen
// - onboarding state
// - addToast
// - jobsVersion / bumpJobsVersion (for cross-page refresh)
// - documentRefreshSignal (for agent → editor communication)
```

This replaces the prop-drilling currently done through App.jsx and keeps the context lean (no full state management library needed).

---

## 6. Extensibility

The page-based architecture makes the app trivially extensible:

### Adding a New Feature/Page

1. Create `pages/NewFeaturePage.jsx`
2. Add a route in `App.jsx`: `<Route path="/new-feature" element={<NewFeaturePage />} />`
3. Add a nav link in `NavigationBar.jsx`
4. Done. No new state in App.jsx. No new panel component. No new boolean flag.

### Adding a New Sub-Page

1. Create `pages/SubPage.jsx`
2. Add a nested route under the parent
3. The parent page renders `<Outlet />` for child routes

### Examples of Future Features That Fit Naturally

| Feature | Route | Notes |
|---------|-------|-------|
| Interview Prep | `/jobs/:id/interview-prep` | Sub-page of job detail |
| Analytics/Dashboard | `/analytics` | New top-level page |
| Templates Library | `/templates` | New top-level page |
| Networking/Contacts | `/contacts` | New top-level page |
| Calendar/Timeline | `/calendar` | New top-level page |

Each is just a new page component + route + nav link. The chat panel works with all of them automatically since it's a global overlay.

---

## 7. File Change Summary

### New Dependencies
| Package | Purpose |
|---------|---------|
| `react-router-dom` | Client-side routing |
| `@tiptap/react` | Rich text editor React bindings |
| `@tiptap/starter-kit` | Standard editor extensions (bold, italic, lists, headings, etc.) |
| `@tiptap/extension-placeholder` | Placeholder text in empty editor |

### New Files (Phase 1 + 2)

| File | Purpose |
|------|---------|
| `frontend/src/components/NavigationBar.jsx` | App navigation with route links and chat toggle |
| `frontend/src/contexts/AppContext.jsx` | Shared state context (chat, toasts, refresh signals) |
| `frontend/src/pages/HomePage.jsx` | Dashboard with recent jobs, documents, quick settings |
| `frontend/src/pages/JobTrackerPage.jsx` | Full job list with filters, sort, add button |
| `frontend/src/pages/JobDetailPage.jsx` | Full job detail with todos, documents section |
| `frontend/src/pages/DocumentEditorPage.jsx` | Side-by-side editor + chat |
| `frontend/src/pages/SettingsPage.jsx` | Full-page settings |
| `frontend/src/pages/ProfilePage.jsx` | Full-page profile + resume |
| `frontend/src/pages/HelpPage.jsx` | Full-page help |
| `frontend/src/components/DocumentEditor.jsx` | Tiptap editor wrapper |
| `frontend/src/components/EditorToolbar.jsx` | Editor toolbar controls |
| `frontend/src/components/VersionHistory.jsx` | Document version history |

### Modified Files

| File | Change |
|------|--------|
| `frontend/package.json` | Add dependencies |
| `frontend/src/main.jsx` | Wrap in `<BrowserRouter>` |
| `frontend/src/App.jsx` | Major rewrite: remove panel state, add `<Routes>`, keep ChatPanel as only overlay |
| `frontend/src/components/ChatPanel.jsx` | Add "docked mode" for document editor, handle `document_saved` events, add `save_job_document` to `JOB_MUTATING_TOOLS` |
| `frontend/src/api.js` | Add 4 document API functions |
| `frontend/vite.config.js` | Ensure SPA fallback for dev and build |
| `backend/models/job.py` | Add `has_cover_letter`/`has_resume` to `to_dict()` |
| `backend/routes/jobs.py` | Query document presence for job list |
| `backend/agent/tools/job_documents.py` | Emit `document_saved` SSE event |

### Deleted Files (after migration complete)

| File | Reason |
|------|--------|
| `frontend/src/components/SettingsPanel.jsx` | Content moved to `SettingsPage.jsx` |
| `frontend/src/components/ProfilePanel.jsx` | Content moved to `ProfilePage.jsx` |
| `frontend/src/components/HelpPanel.jsx` | Content moved to `HelpPage.jsx` |
| `frontend/src/components/JobDetailPanel.jsx` | Content moved to `JobDetailPage.jsx` |

Note: These can be deleted once the pages are fully functional and tested. The inner content is reused — only the slide-out panel wrapper (backdrop, resize handle, fixed positioning) is removed.

---

## 8. Risks & Mitigations

### 8.1 Large Migration Surface

**Risk:** Touching App.jsx, all panels, and adding routing affects every part of the frontend.

**Mitigation:** Phase 1 can be done incrementally. Start by adding the router and creating page shells that literally just render the existing panel content (minus the slide-out wrapper). Each panel → page migration can be its own commit. The old panels can coexist with the new pages during transition.

### 8.2 Chat Panel Complexity

**Risk:** ChatPanel is the most complex component (~500+ lines). Making it work in both "overlay mode" (normal pages) and "docked mode" (document editor) adds complexity.

**Mitigation:** Extract the chat core (conversation list, message rendering, input, SSE handling) into a `ChatCore` component. Then `ChatPanel` (overlay) and the document editor page each render `ChatCore` with different layout wrappers. This also makes ChatPanel more maintainable independently.

### 8.3 Onboarding Flow

**Risk:** The onboarding flow (health check → wizard → onboarding chat) currently relies heavily on App.jsx state coordination. Routing could break this.

**Mitigation:** Keep onboarding logic in App.jsx / AppContext. The onboarding flow happens early (before the user navigates anywhere) and only involves the wizard modal + chat panel — neither of which are page-routed. No change needed to the onboarding flow itself.

### 8.4 Tauri Deep Linking

**Risk:** Tauri loads from a local file, not a web server. Deep links (e.g., refreshing on `/jobs/42`) need to resolve correctly.

**Mitigation:** Tauri serves the built `index.html` for all paths by default (single-page app behavior). Use `HashRouter` instead of `BrowserRouter` if issues arise — hash routing (`/#/jobs/42`) works universally without server configuration. However, `BrowserRouter` should work fine with Tauri's default setup since there's no server-side routing involved.

### 8.5 Editor Library Bundle Size

**Risk:** Tiptap adds to the frontend bundle.

**Mitigation:** Tiptap core + starter-kit is ~150KB gzipped. This is reasonable for a desktop app. The document editor page can also be lazy-loaded (`React.lazy()`) so the editor code is only fetched when the user navigates to it.

---

## 9. Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| Navigation | Header buttons → slide-out panels | Nav bar with route links → full pages |
| Routing | None (single page + overlays) | React Router with 7+ routes |
| App.jsx state | 11+ useState for panels/flow | ~4 useState (chat, onboarding, toasts, wizard) |
| Adding a new feature | New boolean + panel + button | New page file + route + nav link |
| Document editing | Doesn't exist | Dedicated page with Tiptap + docked chat |
| Chat panel | Slide-out overlay | Slide-out overlay (unchanged) OR docked in editor |
| Panel count | 5 slide-out panels | 1 slide-out panel (chat only) |
| Deep linking | Not possible | Full URL-based navigation |
