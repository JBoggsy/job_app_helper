# Design: Job Search Results Panel & Sub-Agent

## Overview

Combine the "dedicated job search results interface" and "job search sub-agent" TODO items into a single feature. When the user asks the agent to search for jobs, the main agent delegates to a job search sub-agent. The sub-agent searches, evaluates, and populates a persistent results panel that slides out next to the chat. The main agent then highlights the best finds.

---

## User Experience Flow

1. User asks the agent something like "Find me React developer jobs in Austin"
2. Main agent recognizes this as a job search task and invokes the job search sub-agent via a `run_job_search` tool
3. Sub-agent makes multiple `job_search` and `web_search` calls, scrapes promising listings, and evaluates each against the user's profile
4. For every job rated ≥3 stars, the sub-agent calls an `add_search_result` tool — this is an internal tool (not available to the main agent) that appends to a per-conversation results list
5. When the first result is added, a **Job Search Results panel** slides out to the right of the chat panel, showing results in real-time as they arrive
6. Sub-agent runs until satisfied it's exhausted available results, then returns a summary to the main agent
7. Main agent reviews the full results list, picks up to 5 highlights, and presents them in chat with brief commentary on why each is a good fit
8. User can expand any result in the panel to see details and click **"Add to Tracker"** to save it as a tracked job

### Panel Behavior
- The panel is **per-conversation** — each conversation has its own results list
- Opening a historical conversation with results shows the panel with those results
- Starting a new conversation starts with an empty/hidden panel
- The panel can be manually closed/reopened via a toggle button in the chat header
- Results persist in the database, tied to the conversation

---

## Architecture

### Backend

#### New Model: `SearchResult`

```python
# backend/models/search_result.py
class SearchResult(db.Model):
    __tablename__ = "search_results"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)

    # Job data (mirrors Job model fields for easy promotion to tracker)
    company = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500))
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    location = db.Column(db.String(200))
    remote_type = db.Column(db.String(50))       # onsite, hybrid, remote
    source = db.Column(db.String(200))            # jsearch, adzuna, web
    description = db.Column(db.Text)              # job description summary
    requirements = db.Column(db.Text)             # newline-separated
    nice_to_haves = db.Column(db.Text)            # newline-separated

    # AI evaluation
    job_fit = db.Column(db.Integer)               # 0-5 star rating
    fit_reason = db.Column(db.Text)               # brief explanation of rating

    # State
    added_to_tracker = db.Column(db.Boolean, default=False)
    tracker_job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
```

#### New API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/chat/conversations/:id/search-results` | Get all search results for a conversation |
| POST | `/api/chat/conversations/:id/search-results/:resultId/add-to-tracker` | Promote a search result to the job tracker |

The GET endpoint is used by the frontend to load results when opening a conversation. The POST endpoint copies fields from the `SearchResult` to a new `Job` record and marks `added_to_tracker = True`.

#### Job Search Sub-Agent: `LangChainJobSearchAgent`

A new agent class in `backend/agent/langchain_agent.py` (or a new file `backend/agent/job_search_agent.py` if cleaner).

**Characteristics:**
- Receives: the user's search request (as interpreted by the main agent), the user profile, and resume data
- Has access to tools: `job_search`, `web_search`, `scrape_url`, `add_search_result` (new), `read_user_profile`, `read_resume`
- Does NOT have: `create_job`, `update_user_profile`, `list_jobs` (these stay with the main agent)
- Has its own system prompt focused on thorough job searching and evaluation
- Uses the same LLM as the main agent (inherits from agent config)
- Has a higher iteration limit (e.g., `MAX_ITERATIONS = 40`) since it may need many search/scrape cycles

**Sub-agent system prompt key instructions:**
- Make multiple searches with varied queries (title variations, synonyms, related roles)
- For each job found, evaluate fit against user profile on a 0-5 scale
- Only add jobs rated ≥3 stars to the results list
- Include a brief `fit_reason` explaining the rating
- Extract structured data (salary, location, remote type, requirements) when available
- Continue searching until confident you've covered the major job boards and search variations
- Return a summary to the main agent: total jobs found, rating distribution, notable patterns

**`add_search_result` tool schema:**
```python
class AddSearchResultInput(BaseModel):
    company: str           # required
    title: str             # required
    url: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    location: Optional[str]
    remote_type: Optional[str]
    source: Optional[str]
    description: Optional[str]
    requirements: Optional[str]
    nice_to_haves: Optional[str]
    job_fit: int           # 0-5, required
    fit_reason: Optional[str]
```

#### Main Agent Integration: `run_job_search` Tool

A new tool available to the main agent:

```python
class RunJobSearchInput(BaseModel):
    query: str              # natural language search description
    location: Optional[str] # target location
    remote_only: Optional[bool]
    salary_min: Optional[int]
    salary_max: Optional[int]
```

When invoked:
1. Main agent's tool execution instantiates `LangChainJobSearchAgent`
2. Sub-agent runs its full loop, yielding SSE events that get forwarded to the client
3. Sub-agent returns a summary dict: `{ "total_found": N, "results_added": M, "rating_distribution": {...}, "summary": "..." }`
4. Main agent receives this summary and uses it (along with access to the full results list via a `list_search_results` tool) to write its highlight commentary

#### SSE Event Extensions

New events for the sub-agent flow:

| Event | Data | Description |
|-------|------|-------------|
| `search_started` | `{ "query": "..." }` | Sub-agent search has begun |
| `search_result_added` | Full `SearchResult` dict | A new result was added (frontend appends to panel) |
| `search_completed` | `{ "total_found": N, "results_added": M }` | Sub-agent finished |

These events flow through the existing SSE stream. The `search_result_added` event is what triggers real-time panel updates — the frontend doesn't need to poll.

#### Sub-Agent Execution Model

The sub-agent runs **within** the main agent's tool execution. When the main agent calls `run_job_search`:

```
Main agent loop iteration N:
  → Main agent emits: tool_start { name: "run_job_search", ... }
  → Tool execution starts sub-agent
  → Sub-agent emits: search_started { query: "..." }
  → Sub-agent iteration 1:
      → Sub-agent calls job_search tool internally (no SSE for sub-agent tool calls)
      → Sub-agent evaluates results
      → Sub-agent calls add_search_result → emits: search_result_added { ... }
      → Sub-agent calls add_search_result → emits: search_result_added { ... }
  → Sub-agent iteration 2:
      → Sub-agent calls web_search internally
      → Sub-agent calls scrape_url internally
      → Sub-agent calls add_search_result → emits: search_result_added { ... }
  → ...
  → Sub-agent finishes → emits: search_completed { total_found: 15, results_added: 8 }
  → Main agent emits: tool_result { name: "run_job_search", result: { summary } }
Main agent loop iteration N+1:
  → Main agent reviews results, writes highlights
  → Emits text_delta events with commentary
```

**Key design decision:** The sub-agent's internal tool calls (job_search, web_search, scrape_url) do NOT emit individual `tool_start`/`tool_result` SSE events. Only the `search_result_added` events flow to the client. This keeps the chat UI clean — the user sees "Searching for jobs..." status rather than a flood of individual tool call indicators.

However, the sub-agent should emit `text_delta`-like events for its progress updates (e.g., "Searching JSearch for React jobs in Austin...", "Found 12 results, evaluating fit...", "Trying broader search with 'frontend developer'..."). These could use a new `search_progress` event type displayed in the chat as a subtle status line.

### Frontend

#### `SearchResultsPanel` Component

A new slide-out panel that appears **to the right of the ChatPanel**. Unlike other panels, this one is contextually tied to the chat — it opens automatically when results arrive and coexists with the chat panel.

**Layout:**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Header                                                             │
├───────────────────────────────────┬─────────────────────────────────┤
│                                   │  Chat Panel    │  Results Panel │
│                                   │  (existing)    │  (new)         │
│         Job Tracker Table         │                │                │
│         (main content)            │  [messages]    │  [results]     │
│                                   │                │                │
│                                   │  [input]       │                │
├───────────────────────────────────┴─────────────────────────────────┤
```

**Props:**
```jsx
SearchResultsPanel({
  isOpen,                    // boolean
  results,                   // SearchResult[]
  onClose,                   // callback
  onAddToTracker,            // (resultId) => Promise
  conversationId,            // current conversation ID
})
```

**Result Card (collapsed):**
```
┌──────────────────────────────────────────┐
│  ★★★★☆  Senior React Dev — Acme Corp    │
│         Austin, TX · Remote · $120-150k  │
└──────────────────────────────────────────┘
```

**Result Card (expanded):**
```
┌──────────────────────────────────────────┐
│  ★★★★☆  Senior React Dev — Acme Corp    │
│         Austin, TX · Remote · $120-150k  │
│                                          │
│  Why it's a fit: Strong match for your   │
│  React expertise and remote preference.  │
│  Salary aligns with target range.        │
│                                          │
│  Requirements:                           │
│  • 5+ years React experience             │
│  • TypeScript proficiency                │
│  • ...                                   │
│                                          │
│  [View Posting]    [Add to Tracker ✓]    │
└──────────────────────────────────────────┘
```

**Sorting:** Results are displayed sorted by job_fit (highest first), then by creation time.

**Real-time updates:** When `search_result_added` SSE events arrive, the new result is appended to the list with a brief highlight animation (e.g., a subtle slide-in or glow).

**"Add to Tracker" flow:**
1. User clicks button
2. Frontend calls `POST /api/chat/conversations/:id/search-results/:resultId/add-to-tracker`
3. Backend creates a `Job` from the `SearchResult` fields, marks `added_to_tracker = True`
4. Button changes to a disabled "Added ✓" state
5. `onAddToTracker` callback fires → parent bumps `jobsVersion` to refresh the tracker table

#### ChatPanel Changes

- Add a toggle button in the chat header area (e.g., a list/results icon) that shows/hides the results panel. Badge with result count when panel is closed.
- Track `searchResults` state, populated from SSE events during streaming and from API on conversation load
- When loading a conversation, fetch its search results and display the panel if any exist
- During streaming: listen for `search_result_added` events and append to state
- Show a status indicator in chat during sub-agent execution (e.g., "🔍 Searching for jobs..." with a progress counter: "Found 3 results so far...")

#### App.jsx Changes

- The `SearchResultsPanel` can either be managed by `ChatPanel` directly (since it's contextually coupled) or lifted to `App.jsx` — recommend keeping it as a child/sibling of `ChatPanel` for simpler state management
- Add `onAddToTracker` callback that bumps `jobsVersion` (reuse existing pattern from `onJobsChanged`)

---

## Data Flow Summary

```
User message: "Find me React jobs in Austin"
        │
        ▼
   Main Agent (LangChainAgent)
        │
        │ calls run_job_search tool
        ▼
   Job Search Sub-Agent (LangChainJobSearchAgent)
        │
        ├── calls job_search("react developer", location="Austin")
        │   └── gets 10 raw results from JSearch
        ├── calls job_search("frontend engineer react", location="Austin, TX")
        │   └── gets 10 more results
        ├── calls web_search("react developer jobs Austin TX hiring")
        │   └── gets 5 web results
        ├── calls scrape_url(promising_listing_1)
        ├── calls scrape_url(promising_listing_2)
        │
        │ Evaluates each job against user profile:
        │   - Senior React Dev at Acme → ★★★★☆ (4/5) → add_search_result ──→ SSE: search_result_added
        │   - Junior JS Dev at Foo    → ★★☆☆☆ (2/5) → skip (below threshold)
        │   - React Lead at Bar       → ★★★★★ (5/5) → add_search_result ──→ SSE: search_result_added
        │   - ...
        │
        │ Returns summary to main agent
        ▼
   Main Agent continues
        │
        │ calls list_search_results to see all found jobs
        │ Picks top 5 to highlight
        ▼
   Chat response: "I found 8 jobs that match your profile! Here are the top picks:
   1. ★★★★★ React Lead at Bar — perfect match for your 7 years of experience...
   2. ★★★★☆ Senior React Dev at Acme — strong fit, good salary range...
   ..."
```

---

## Implementation Plan

### Phase 1: Backend Foundation
1. Create `SearchResult` model and migration
2. Add `GET /api/chat/conversations/:id/search-results` endpoint
3. Add `POST /api/chat/conversations/:id/search-results/:resultId/add-to-tracker` endpoint
4. Add search results to conversation `to_dict()` (or as a separate fetch)

### Phase 2: Sub-Agent
5. Create `LangChainJobSearchAgent` class with its own system prompt
6. Create `add_search_result` tool (writes to DB, yields SSE event)
7. Create `run_job_search` tool for the main agent (instantiates and runs sub-agent)
8. Create `list_search_results` tool for the main agent (reads results from DB)
9. Wire up SSE event forwarding from sub-agent through main agent's stream
10. Update main agent system prompt to describe when/how to use `run_job_search`

### Phase 3: Frontend — Results Panel
11. Create `SearchResultsPanel` component with collapsed/expanded result cards
12. Add star rating display component
13. Implement "Add to Tracker" flow with API call and state update
14. Add panel open/close toggle to ChatPanel header

### Phase 4: Frontend — Integration
15. Handle `search_result_added` SSE events in ChatPanel streaming handler
16. Load search results when opening a historical conversation
17. Show search progress status in chat during sub-agent execution
18. Wire up `onAddToTracker` → `jobsVersion` refresh
19. Handle `search_started` / `search_completed` events for status display

### Phase 5: Polish
20. Result card highlight animation on arrival
21. Sort results by rating
22. Handle edge cases: no results found, search errors, conversation deletion cleanup
23. Update main agent system prompt with highlight instructions (pick top 5, explain why)
24. Test with multiple providers (Anthropic, OpenAI, Gemini)

---

## Open Questions

1. **Sub-agent LLM cost:** The sub-agent will make many LLM calls (evaluating each job
   individually). Should we offer a config option to use a cheaper model for the sub-agent (like the
   onboarding agent pattern)?
   **Answer:** Yes, and it should default to a cheap option. Also, 

2. **Deduplication:** If the user asks to search again in the same conversation, should results
   append to the existing list or replace it?
   **Answer:** Append but deduplicate by URL.

3. **Result limit:** Should there be a max number of results per search?
   **Answer:** Yes, it should be user-configurable with default 25 to keep the panel manageable and control API costs.

4. **Rating threshold:** Hardcode ≥3 stars or make configurable?
   **Answer:** Hardcode at 3 for now, make configurable later if users request it.

5. **Sub-agent visibility:** How much of the sub-agent's internal reasoning should be visible? Options:
   **Answer:** Show brief progress lines like "Searching JSearch... Found 12 results... Evaluating fit..." (recommended — gives user confidence something is happening)

6. **Panel positioning:** Should the results panel push the chat panel narrower, or overlay/float
   independently?
   **Answer:** The chat panel and results panel share the right side, with the chat panel narrowing
   when results are shown. On small screens, the results panel could be a tab within the chat panel
   instead.
