# Fixed Pipeline Agent Design

A programmatic pipeline architecture that replaces the monolithic ReAct loop
with **structured routing + micro-agents**. Instead of giving a single LLM
free-form access to all tools and hoping it reasons its way to the right
sequence of actions, the agent classifies user intent, extracts structured
parameters, and then executes a **deterministic pipeline** for each request
type — invoking small, focused LLM calls ("micro-agents") only at the
specific steps that genuinely require natural-language reasoning.

---

## Why This Design?

The `default` monolithic ReAct agent works but has structural weaknesses:

| Problem | Root Cause | Fixed Pipeline Fix |
|---|---|---|
| Slow multi-step tasks | LLM reasons about what to do next on every iteration | Programmatic pipeline knows the plan; LLM only runs where needed |
| Unpredictable tool sequences | LLM may call tools in a suboptimal order or skip steps | Pipeline enforces correct ordering |
| Expensive | Every reasoning step is a full LLM call with all tools bound | Micro-agents are scoped calls with minimal context |
| Hard to debug | One opaque loop does everything | Each pipeline step has clear inputs/outputs |
| Inconsistent quality | LLM may forget to evaluate fit, resolve URLs, etc. | Pipeline guarantees each step runs |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Message                                │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │    Routing Agent (DSPy)   │
                    │    (single LLM call)      │
                    │                           │
                    │  Extracts:                │
                    │   • request_type (enum)   │
                    │   • params (structured)   │
                    │   • entity_refs (IDs,     │
                    │     names, URLs)          │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Pipeline Dispatcher     │
                    │   (pure Python switch)    │
                    └──┬────┬────┬────┬────┬───┘
                       │    │    │    │    │
              ┌────────┘    │    │    │    └────────┐
              ▼             ▼    ▼    ▼             ▼
         FIND_JOBS    RESEARCH  CRUD  PREPARE   GENERAL
         pipeline     pipeline  exec  pipeline  pipeline
              │             │    │    │             │
              ▼             ▼    ▼    ▼             ▼
         (steps with     (steps)  (DB  (steps)  (single
          micro-agents)          ops)            micro-agent)
```

### Core Principles

1. **Classify once, execute deterministically.** The Routing Agent (a DSPy
   `ChainOfThought` module) is the only "creative" LLM call at the top
   level. After that, the pipeline for each request type is a fixed
   sequence of steps.

2. **Micro-agents are scoped.** Each micro-agent gets only the context it
   needs (not the entire tool set) and produces structured output validated
   by a Pydantic schema, or streams free-form text. This makes them
   cheaper, faster, and more reliable.

3. **Programmatic steps don't need LLMs.** Database queries, API calls, data
   filtering, and response formatting are pure Python. The LLM is only
   invoked for tasks that require natural-language understanding or generation.

4. **SSE streaming is preserved.** The pipeline yields the same SSE event
   dicts as the default design (`text_delta`, `tool_start`, `tool_result`,
   `done`, etc.) so the frontend works without changes.

5. **Tools are reused.** The existing `AgentTools` class from
   `backend/agent/tools/` is used for all DB and API operations. Micro-agents
   do NOT get direct tool access — the pipeline calls tools programmatically
   and passes results to micro-agents as context.

6. **DSPy integration enables optimization.** Structured-output micro-agents
   are implemented as DSPy modules with `ChainOfThought` signatures. Training
   examples are collected passively from pipeline runs and scored based on
   user actions (tracker adds, fit edits). BootstrapFewShot optimization
   compiles few-shot examples into modules, improving quality over time.

---

## Request Types

The Routing Agent classifies every user message into one of these types:

| Type | Description | Example |
|---|---|---|
| `find_jobs` | Search for jobs matching criteria | "Find remote React jobs paying $150k+" |
| `research_url` | Analyze a specific URL (job posting, company page) | "Tell me about this job: https://..." |
| `track_crud` | Create, edit, or delete a job in the tracker | "Add the Stripe job" / "Update Google to interviewing" |
| `query_jobs` | Read/filter/summarize tracked jobs | "What jobs am I interviewing for?" |
| `todo_mgmt` | Create, toggle, or list application todos | "Create a checklist for the Stripe app" |
| `profile_mgmt` | Read or update the user profile | "Add React to my skills" |
| `prepare` | Interview prep, cover letters, resume tailoring | "Help me prepare for the Google interview" |
| `compare` | Compare or rank multiple jobs | "Compare the Google and Meta offers" |
| `research` | General research (company, salary, industry) | "Research Stripe's engineering culture" |
| `general` | Career advice, app help, open-ended questions | "How should I negotiate this offer?" |
| `multi_step` | User request that chains 2+ of the above | "Find jobs, add the top 3, and create todos" |

---

## Routing Agent

A DSPy `ChainOfThought` module (`RoutingModule`) that classifies user intent
in a single LLM call. No tools bound.

### Input
- System prompt: routing instructions + brief summary of each request type
  (defined in `ROUTING_SYSTEM_PROMPT` in `prompts.py`)
- Conversation context: the last 6 messages of history (`HISTORY_WINDOW = 6`)

### Output

The `RoutingModule` (via the `RouteRequest` DSPy signature) produces a
`RoutingResult` with:

- `request_type` — one of the 11 types above
- `params` — type-specific parameters, validated against the corresponding
  Pydantic schema from `schemas.py` (e.g., `FindJobsParams`, `TrackCrudParams`)
- `entity_refs` — job names, IDs, URLs referenced by the user
- `acknowledgment` — brief message streamed immediately as `text_delta` so
  the user sees feedback before the pipeline starts executing

### Validation and Fallback

1. The `route()` function in `routing.py` invokes the `RoutingModule` and
   validates the extracted params against `PARAM_SCHEMAS` (a dict mapping
   each request type to its Pydantic model).
2. If validation fails, it retries once (`MAX_PARAM_RETRIES = 1`) with
   the error appended to context.
3. If routing or validation still fails, it falls back to the `general`
   pipeline (a single unconstrained LLM call).

---

## Pipeline Architecture

Each pipeline is a sequence of **steps**. Steps are either:

- **Programmatic** — pure Python (DB query, API call, data transform, template)
- **Micro-agent** — a scoped LLM call with a specific prompt and output schema

All pipelines extend the `Pipeline` base class (`pipeline_base.py`) which
provides:

- `exec_tool(name, arguments)` — programmatically calls a tool via
  `execute_tool_with_events()` and yields SSE events
- `text(content)` — helper to yield a `text_delta` event
- `execute()` — abstract method that subclasses override (a generator
  yielding SSE event dicts)

The `ToolResult` container class stores tool outputs and exposes `is_error`
and `error` properties for pipeline control flow.

### Pipeline Registry

All pipelines are registered in `PIPELINE_REGISTRY` (`pipelines/__init__.py`),
a dict mapping request type strings to pipeline classes. The main agent
looks up the pipeline by the routing result's `request_type`.

### Key: Reading Pipeline Diagrams

```
[step name]          — programmatic step (no LLM)
«Micro-Agent Name»   — LLM-powered step
──►                  — data flow
~~►                  — optional/conditional
```

---

### `find_jobs`

Find jobs matching user-specified criteria via job board APIs.

**Params:** `FindJobsParams` — `query`, `location`, `remote_type`,
`salary_min/max`, `company_type`, `employment_type`, `date_posted`,
`num_results`, `user_intent`, `soft_constraints`

```
[load user profile + resume summary]
    │
    ▼
«Query Generator» (DSPy: QueryGeneratorModule)
    Input:  FindJobsParams + user profile summary
    Output: QueryGeneratorResult (1-4 query variations)
    [records query_generator training example]
    │
    ▼
[execute job_search() for each query]  ──► raw API results
    │
    ▼
[deduplicate results by URL, then by company+title]
    │
    ▼
«Evaluator» (DSPy: EvaluatorModule)
    Input:  deduplicated results + user profile + resume + soft_constraints
    Output: JobEvaluationResult with job_fit (0-5) + fit_reason per job
    [records evaluator training example]
    │
    ▼
[filter: keep jobs with job_fit >= 3, up to num_results]
    │
    ▼
[for each passing job: call add_search_result() — emits SSE event]
    │
    ▼
«Results Summary» (streaming text)
    Input:  all added results + search params
    Output: narrative summary for the user
```

---

### `research_url`

Analyze a URL provided by the user (job posting, company page, etc.).

**Params:** `ResearchUrlParams` — `url`, `intent` (`"analyze"` or
`"add_to_tracker"`)

```
[scrape_url(url)]  ──► raw page content
    │
    ▼
«Detail Extraction» (DSPy: DetailExtractionModule)
    Input:  raw page content + URL
    Output: JobDetails (company, title, salary, requirements, etc.)
    │
    ▼
[load user profile + resume]
    │
    ▼
«Fit Evaluator» (DSPy: FitEvaluatorModule)
    Input:  extracted details + profile + resume
    Output: FitEvaluation (job_fit, fit_reason, strengths, gaps)
    │
    ▼
[if intent == "add_to_tracker": create_job() with extracted fields]
    │
    ▼
«Analysis Summary» (streaming text)
    Input:  extracted details + fit evaluation
    Output: narrative analysis for the user
```

---

### `track_crud`

Create, update, or delete jobs in the tracker. Mostly programmatic.

**Params:** `TrackCrudParams` — `action` (`create`/`edit`/`delete`),
`job_ref`, `job_id`, `fields`

```
[resolve entity: job_ref → job_id via entity_resolution]
    │ If ambiguous: ask user to clarify (yield text with options)
    │
    ▼
[execute tool:]
    ├── create → create_job(fields)
    ├── edit   → edit_job(job_id, fields)
    └── delete → remove_job(job_id)
    │
    ▼
[template confirmation message with salary/location formatting]
```

No micro-agents needed. The Routing Agent handles natural-language field
extraction (e.g., "salary about 180" → `salary_min: 170000`).

---

### `query_jobs`

Query, filter, and summarize tracked jobs.

**Params:** `QueryJobsParams` — `filters`, `question`, `format`
(`list`/`summary`/`count`)

```
[list_jobs(filters)]  ──► job records
    │
    ├── Simple (list/count/summary):
    │       [format using template with status emojis + job details]
    │
    └── Complex ("best fit", "recommend", etc.):
            «Analysis» (streaming text)
                Input:  job records + profile + question
```

---

### `todo_mgmt`

Manage application todos.

**Params:** `TodoMgmtParams` — `action` (`list`/`toggle`/`create`/
`generate`/`delete`), `job_ref`, `job_id`, `todo_id`, `todo_data`

```
[resolve job_ref → job_id]
    │
    ├── list:     [list_job_todos → format checklist]
    ├── toggle:   [edit_job_todo(completed=!) → confirm]
    ├── create:   [add_job_todo(todo_data) → confirm]
    ├── delete:   [remove_job_todo → confirm]
    └── generate:
            «Todo Generator» (DSPy: TodoGeneratorModule)
                Input:  job details + profile + resume
                Output: TodoGeneratorResult (5-10 tasks)
            [add_job_todo() × N → confirm]
```

---

### `profile_mgmt`

Read or update the user profile.

**Params:** `ProfileMgmtParams` — `action` (`read`/`update`), `section`,
`content`, `natural_update`

```
├── read:    [read_user_profile → present]
└── update:
        ├── Simple (section + content): [update_user_profile → confirm]
        └── Complex (natural language):
                «Profile Update» (DSPy: ProfileUpdateModule)
                    Input:  current profile + update text
                    Output: ProfileUpdateResult (section updates)
                [apply updates → confirm]
```

---

### `prepare`

Interview prep, cover letters, resume tailoring, question prep.

**Params:** `PrepareParams` — `prep_type` (`interview`/`cover_letter`/
`resume_tailor`/`questions`/`general`), `job_ref`, `job_id`, `specifics`

```
[resolve job_ref → Job record]
[gather: profile + resume + job details]
    │
    ├── interview:     «Interview Prep» (streaming)
    ├── cover_letter:  «Cover Letter» (streaming)
    ├── resume_tailor: «Resume Tailor» (streaming, uses full resume)
    ├── questions:     «Question Generator» (streaming)
    └── general:       «Interview Prep» (streaming, fallback)
```

---

### `compare`

Compare or rank multiple jobs.

**Params:** `CompareParams` — `job_refs`, `job_ids`, `dimensions`, `mode`
(`compare`/`rank`/`pros_cons`)

```
[resolve all job_refs → Job records]
[load user profile]
    │
    ├── compare:   «Comparison» (streaming) — side-by-side analysis
    ├── rank:      «Ranking» (streaming) — scored list
    └── pros_cons: «Analysis» (streaming) — single job deep dive
```

---

### `research`

General research — company culture, salary data, interview processes.

**Params:** `ResearchParams` — `topic`, `research_type` (`company`/`salary`/
`interview_process`/`industry`/`general`), `company`, `role`

```
«Research Query Generator» (DSPy: ResearchQueryModule)
    Output: SearchQueryList (2-4 queries)
    │
    ▼
[web_search() for each query, up to 4]
    │
    ▼
«Research Synthesizer» (streaming)
    Input:  search results + topic + profile
    Output: narrative report with citations
```

---

### `general`

Catch-all for career advice, app guidance, and open-ended questions.

**Params:** `GeneralParams` — `question`, `needs_job_context`,
`needs_profile`, `job_ref`

```
[conditionally load: profile, resume_summary, jobs, conversation history]
    │
    ▼
«Advisor» (streaming)
    Input:  question + context + last 6 messages of history
```

This is the **fallback pipeline**. If routing fails or the request doesn't
fit any specific pipeline, it lands here.

---

### `multi_step`

Composite requests that chain multiple pipelines.

**Params:** `MultiStepParams` — `steps` (list of `{type, params}` dicts)

```
[for each step:]
    [stream "Step N/total" divider]
    [dispatch to PIPELINE_REGISTRY → execute sub-pipeline]
    [catch per-step exceptions without stopping]
[stream "All steps complete"]
```

---

## Micro-Agent Architecture

Micro-agents come in two flavors, both defined in `micro_agents.py`:

### Structured-Output Agents (via DSPy)

These use DSPy `ChainOfThought` modules for reliable structured output.
Each has a corresponding DSPy signature (`dspy_signatures.py`) and module
(`dspy_modules.py`). The `BaseMicroAgent.invoke()` method handles:

1. Calling `model.with_structured_output(schema)` for providers that
   support it
2. Falling back to JSON-in-text parsing for Ollama
3. Retrying once on validation failure

| Agent Class | DSPy Module | Output Schema | Used By |
|---|---|---|---|
| `QueryGeneratorAgent` | `QueryGeneratorModule` | `QueryGeneratorResult` | find_jobs |
| `EvaluatorAgent` | `EvaluatorModule` | `JobEvaluationResult` | find_jobs |
| `DetailExtractionAgent` | `DetailExtractionModule` | `JobDetails` | find_jobs, research_url |
| `FitEvaluatorAgent` | `FitEvaluatorModule` | `FitEvaluation` | research_url |
| `ProfileUpdateAgent` | `ProfileUpdateModule` | `ProfileUpdateResult` | profile_mgmt |
| `TodoGeneratorAgent` | `TodoGeneratorModule` | `TodoGeneratorResult` | todo_mgmt |
| `ResearchQueryAgent` | `ResearchQueryModule` | `SearchQueryList` | research |

### Text-Streaming Agents

These use `BaseMicroAgent.stream()` for free-form text responses. The
pipeline yields `text_delta` events as chunks arrive from `model.stream()`.

| Agent Class | Prompt Constant | Used By |
|---|---|---|
| `AdvisorAgent` | `ADVISOR_PROMPT` | general |
| `AnalysisAgent` | `ANALYSIS_PROMPT` | query_jobs, compare |
| `ResultsSummaryAgent` | `RESULTS_SUMMARY_PROMPT` | find_jobs |
| `AnalysisSummaryAgent` | `ANALYSIS_SUMMARY_PROMPT` | research_url |
| `InterviewPrepAgent` | `INTERVIEW_PREP_PROMPT` | prepare |
| `CoverLetterAgent` | `COVER_LETTER_PROMPT` | prepare |
| `ResumeTailorAgent` | `RESUME_TAILOR_PROMPT` | prepare |
| `QuestionGeneratorAgent` | `QUESTION_GENERATOR_PROMPT` | prepare |
| `ComparisonAgent` | `COMPARISON_PROMPT` | compare |
| `RankingAgent` | `RANKING_PROMPT` | compare |
| `ResearchSynthesizerAgent` | `RESEARCH_SYNTHESIZER_PROMPT` | research |

---

## DSPy Integration

The fixed pipeline uses DSPy for structured-output micro-agents and supports
BootstrapFewShot optimization to improve quality over time.

### LangChain ↔ DSPy Bridge (`dspy_lm.py`)

`LangChainLM` extends `dspy.BaseLM` to adapt LangChain's `BaseChatModel` to
DSPy's LM interface. The `create_dspy_lm()` factory wraps a LangChain model
and DSPy calls run via `dspy.context(lm=...)` for thread-safe execution.

### DSPy Signatures (`dspy_signatures.py`)

Eight signatures define the input/output contracts for structured agents:
`RouteRequest`, `GenerateSearchQueries`, `EvaluateJobs`, `UpdateProfile`,
`GenerateTodos`, `ExtractJobDetails`, `EvaluateFit`, `GenerateResearchQueries`.
Each includes detailed docstrings that serve as DSPy instructions.

### DSPy Modules (`dspy_modules.py`)

Each module wraps a `ChainOfThought(Signature)` call. Two modules —
`QueryGeneratorModule` and `EvaluatorModule` — load saved optimized state
on initialization via `module_store.py`.

### Module State Persistence (`module_store.py`)

Compiled DSPy modules are saved/loaded from `dspy_modules/{name}.json`.
Functions: `save_module()`, `load_module_state()`, `has_optimized_module()`,
`get_last_modified()`.

### Feedback Collection (`feedback.py`)

Training examples are recorded passively from pipeline runs:

- `record_evaluator_example()` — saves evaluator inputs/outputs as
  `DspyExample` rows
- `record_query_generator_example()` — saves query generator inputs/outputs

Examples are scored based on user actions:

- `score_from_tracker_add()` — when user adds a search result to their
  tracker, scores both evaluator accuracy and query generator relevance
- `score_from_job_edit()` — when user edits a job's fit rating, penalizes
  evaluator proportionally to the distance from the agent's prediction

Metric functions (`evaluator_metric`, `query_gen_metric`) return the stored
score for BootstrapFewShot. The `/api/optimize` endpoint triggers optimization
and compiled modules persist in `dspy_modules/` for auto-load on startup.

---

## SSE Streaming

The frontend expects the same SSE events as the default agent. The
`streaming.py` module provides helper functions that produce SSE event dicts:

| Helper Function | SSE Event | When Emitted |
|---|---|---|
| `yield_text()` | `text_delta` | Routing acknowledgment; progress updates; micro-agent streamed text |
| `yield_tool_start()` | `tool_start` | Before executing any programmatic tool call |
| `yield_tool_result()` | `tool_result` | After a programmatic tool call completes |
| `yield_tool_error()` | `tool_error` | If a tool call fails |
| — | `search_result_added` | When `add_search_result()` is called (flushed from tool pending events) |
| `yield_done()` | `done` | Pipeline complete — includes full accumulated text |
| `yield_error()` | `error` | Fatal pipeline error |

`execute_tool_with_events()` is the main tool execution function — it calls
the tool via `AgentTools`, yields start/result/error events, and flushes any
pending callback events (like `search_result_added`).

---

## Entity Resolution

`entity_resolution.py` resolves natural-language job references ("the Google
job", "my Stripe application", "job #5") to a `job_id` using tiered string
matching:

1. **Numeric patterns** — `#5`, `job 5`, `id #5` → direct ID lookup
2. **Text scoring** — scores all jobs by company and title match:
   - 100 = exact match, 80 = prefix, 60 = word boundary, 40 = substring
   - +10 bonus if both company and title match
3. **Auto-selection** — picks the top match if it scores ≥ 100 (exact) or
   has a clear gap (≥ 20 points) over the runner-up
4. **Ambiguity** — returns all matches if scores are too close (pipeline
   asks user to clarify)

`resolve_job_ref_or_fail()` wraps this with user-facing error messages for
pipeline use.

---

## Context Caching

`RequestContext` (`context.py`) is a per-request dataclass that lazily loads
and caches shared data to avoid redundant tool calls within a pipeline:

- `ensure_profile()` — loads the user profile once via `read_user_profile`
- `ensure_resume()` — loads resume data once via `read_resume`
- `ensure_jobs(**filters)` — loads the job list once via `list_jobs`
- `get_resume_summary()` — formats a text summary from parsed resume JSON
  (name, summary, skills, experience), falling back to first 2000 chars of
  raw text

---

## Error Handling & Fallback

1. **Routing failure** — If the Routing Agent returns an invalid type or
   fails param validation after retry, falls back to the `general` pipeline.

2. **Micro-agent failure** — If a structured-output micro-agent call fails
   (timeout, invalid output, rate limit):
   - Retries once (non-Ollama providers)
   - If still failing, the pipeline continues with degraded output or skips
     that step

3. **Tool failure** — Captured in `tool_error` SSE events via
   `execute_tool_with_events()`. The pipeline continues if possible.

4. **Full fallback** — If the pipeline itself throws an unrecoverable
   exception, `FixedPipelineAgent._run_inner()` catches it and falls back
   to the `general` pipeline to give the user some response.

---

## File Structure

```
backend/agent/fixed_pipeline/
    __init__.py              # Exports FixedPipelineAgent, reuses DefaultOnboardingAgent
    │                        #   and DefaultResumeParser from the default design
    DESIGN.md                # This document
    │
    # ── Core machinery ──
    agent.py                 # FixedPipelineAgent — main entry point, DSPy context mgmt
    routing.py               # route() function — invokes RoutingModule, validates params
    context.py               # RequestContext — lazy-loaded profile/resume/jobs cache
    entity_resolution.py     # resolve_job_ref() — tiered string matching for job refs
    streaming.py             # SSE event helpers + execute_tool_with_events()
    schemas.py               # RoutingResult + per-pipeline param Pydantic schemas
    prompts.py               # All system prompts for routing + micro-agents
    │
    # ── Micro-agents ──
    micro_agents.py          # BaseMicroAgent + 18 concrete agent classes
    │                        #   (7 structured-output, 11 text-streaming)
    │
    # ── DSPy layer ──
    dspy_signatures.py       # 8 DSPy Signature definitions (input/output contracts)
    dspy_modules.py          # 8 DSPy Module classes (ChainOfThought wrappers)
    dspy_lm.py               # LangChainLM adapter (LangChain BaseChatModel → DSPy BaseLM)
    module_store.py          # Save/load compiled DSPy modules to dspy_modules/ directory
    feedback.py              # Training example recording + scoring for optimization
    │
    # ── Pipelines ──
    pipeline_base.py         # Pipeline base class + ToolResult container
    pipelines/
        __init__.py          # PIPELINE_REGISTRY mapping request types → pipeline classes
        find_jobs.py         # FindJobsPipeline — query gen → search → evaluate → results
        research_url.py      # ResearchUrlPipeline — scrape → extract → evaluate → summarize
        track_crud.py        # TrackCrudPipeline — entity resolve → tool exec → confirm
        query_jobs.py        # QueryJobsPipeline — list → format or analyze
        todo_mgmt.py         # TodoMgmtPipeline — CRUD + AI-generated task lists
        profile_mgmt.py      # ProfileMgmtPipeline — read or NL-interpreted update
        prepare.py           # PreparePipeline — dispatches to prep-type-specific agents
        compare.py           # ComparePipeline — compare, rank, or pros/cons
        research.py          # ResearchPipeline — query gen → web search → synthesize
        general.py           # GeneralPipeline — fallback advisor with optional context
        multi_step.py        # MultiStepPipeline — sequential sub-pipeline dispatch
```

---

## What Stays the Same

- **`AgentTools`** — All existing tools are reused. The fixed pipeline calls
  `tools.execute(name, args)` from pipeline steps rather than letting the
  LLM decide when to call them.

- **`OnboardingAgent`** — Reuses `DefaultOnboardingAgent` from the default
  design. The onboarding interview is inherently conversational and doesn't
  benefit from pipeline routing.

- **`ResumeParser`** — Reuses `DefaultResumeParser` from the default design.
  Single-shot structured extraction.

- **SSE protocol** — Identical event types and `data` shapes.

- **Frontend** — No changes required. The fixed pipeline is a drop-in
  replacement from the frontend's perspective.
