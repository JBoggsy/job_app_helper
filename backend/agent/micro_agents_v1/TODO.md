# micro_agents_v1 — TODO

Items are grouped by priority.  "Needs implementing" items are blockers
for correctness; "improvements" items are quality-of-life or
architectural refinements.

---

## Needs Implementing (blockers)

### Stub workflows — `raise NotImplementedError`

These are registered in the workflow registry and will be selected by
the mapper, but immediately crash the pipeline when dispatched.  Until
they exist the executor's top-level `try/except` swallows the error and
returns a generic `error` SSE event, which is confusing for users.

- [ ] **`WriteCoverLetterWorkflow`** (`workflows/write_cover_letter.py`)
  - Resolve target job via `JobResolver`
  - Load user profile + resume
  - DSPy-orchestrated interactive writing session (section by section)
  - Save final letter via `save_job_document`

- [ ] **`SpecializeResumeWorkflow`** (`workflows/specialize_resume.py`)
  - Resolve target job via `JobResolver`
  - Load resume + profile
  - DSPy chain-of-thought suggests targeted edits (reorder experience,
    emphasise skills, adjust summary)
  - Interactive loop until user is satisfied

- [ ] **`PrepInterviewWorkflow`** (`workflows/prep_interview.py`)
  - Resolve target job via `JobResolver`
  - Load resume + profile + job details
  - DSPy module generates: likely questions (behavioural/technical),
    STAR-format answer suggestions, research topics, questions for the
    interviewer
  - Stream results as formatted markdown

### Stub agents — `raise NotImplementedError`

- [ ] **`MicroAgentsV1OnboardingAgent`** (`onboarding_agent.py`)
  - Port the default design's onboarding interview into this pipeline
  - Uses a dedicated `OnboardingWorkflow` or the `update_profile`
    workflow in a guided loop
  - Must emit `onboarding_complete` SSE event when done

- [ ] **`MicroAgentsV1ResumeParser`** (`resume_parser.py`)
  - Single-shot DSPy module: raw resume text → structured JSON
  - Can reuse the same signature as the default design's parser

---

## Improvements / Refinements

### Critical

- [ ] **Flush `_pending_events` during streaming** (`agent.py:59`)
  `MicroAgentsV1Agent._pending_events` collects SSE events from tool
  callbacks (e.g. `search_result_added`) via `_on_tool_event()`, but
  `run()` never yields them.  `search_result_added` events are silently
  dropped, breaking the real-time search results panel in the UI.
  Fix: yield queued events after each workflow completes (or after the
  executor returns).

- [ ] **Graceful fallback for `NotImplementedError` in workflows**
  When the executor dispatches a stub workflow, the `NotImplementedError`
  propagates all the way to `agent.py`'s top-level handler.  Add a
  `try/except NotImplementedError` inside the executor's per-workflow
  loop to produce a clean `WorkflowResult(success=False, summary="…not
  yet implemented")` instead.

### Architecture

- [ ] **`MicroAgentsV1Agent` is not a `dspy.Module`**
  The README states the top-level agent is a DSPy module enabling
  end-to-end optimization.  Currently it inherits from the `Agent` ABC
  and composes stages imperatively.  Making it a `dspy.Module` that
  exposes sub-modules would unlock DSPy optimizer support (e.g.
  `BootstrapFewShot`, `MIPROv2`) across the whole pipeline.

- [ ] **Pass workflow descriptions to `WorkflowMapper`**
  The mapper only receives workflow names as a comma-separated string
  (`"general, job_search, add_to_tracker, ..."`).  The LLM must infer
  each workflow's purpose from its name alone.  Pass a richer format
  (e.g. JSON with `name` + short `description`) so routing decisions
  are more reliable.

- [ ] **Pass conversation context to workflows**
  `agent.py` never includes recent conversation history in workflow
  `params`.  As a result `conversation_context` is always an empty
  string in `JobResolver` and `SearchResultResolver`, limiting their
  ability to resolve relative references ("the first one", "the job we
  were just discussing").  Extract the last N messages and include them
  in the params dict before dispatching.

### User experience

- [ ] **Suppress verbose pipeline internals from chat output**
  `agent.py` streams "Planning approach…", the raw outcome list with
  IDs and `depends_on`, "Mapping to workflows…", and full
  `WorkflowAssignment` details (including `deferred_params`, workflow
  name codes, etc.) directly into the chat.  This is noisy and confusing
  for users.  Options:
  - Log these at DEBUG and show only a minimal "Thinking…" indicator
  - Show a clean collapsible "plan" block rather than raw data

- [ ] **`GeneralWorkflow` is a black box** (`workflows/general.py`)
  The DSPy `ReAct` loop runs fully synchronously with no
  `tool_start`/`tool_result` SSE events emitted during execution.
  Users see no activity while it works.  Consider wrapping tool
  functions in a shim that emits progress events, or adding a
  DSPy callback hook.

- [ ] **Result collation doesn't stream token-by-token**
  `ResultCollator.collate()` emits one large `text_delta` event with the
  full response (DSPy produces complete outputs).  Users see a blank
  "Summarising results…" pause before the final answer appears.
  Workaround: use the LiteLLM `completion()` API with streaming for the
  collation step instead of DSPy.

### Performance / correctness

- [ ] **Cache `list_jobs` within a pipeline run**
  Multi-outcome pipelines (e.g. "edit this job and compare it to the
  others") trigger multiple identical `list_jobs` DB queries.  A simple
  request-scoped dict passed through workflow params would eliminate the
  redundancy.

- [ ] **Verify thread safety of `dspy.context` in parallel analysis**
  `EditCoverLetterWorkflow` runs three analysis passes in a
  `ThreadPoolExecutor`, each calling `dspy.context(lm=lm)`.  DSPy's
  context manager is thread-local (safe in theory), but this has not
  been tested under load.  Add a test or a comment confirming safety.
