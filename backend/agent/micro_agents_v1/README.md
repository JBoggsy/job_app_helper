# Micro Agents v1

A workflow-orchestrated agent design where user requests are decomposed into
discrete outcomes, each mapped to a hand-crafted workflow, and executed in
dependency order. Complex reasoning steps within workflows are handled by small,
focused DSPy modules ("micro-agents") that can be optimized independently.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     User Request                        │
└────────────────────────┬────────────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │  Outcome Planner    │
              │  (DSPy module)      │
              └─────────┬───────────┘
                        ▼
              ┌─────────────────────┐
              │  Outcome list with  │
              │  dependency graph   │
              └─────────┬───────────┘
                        ▼
              ┌─────────────────────┐
              │  Workflow Mapper    │
              │  (DSPy module)      │
              └─────────┬───────────┘
                        ▼
              ┌─────────────────────┐
              │  Workflow schedule  │
              │  with parameters    │
              └─────────┬───────────┘
                        ▼
              ┌─────────────────────┐
              │  Workflow Executor  │
              │  (orchestrator)     │
              │                     │
              │  ┌───┐ ┌───┐ ┌───┐  │
              │  │W1 │→│W2 │→│W3 │  │
              │  └───┘ └───┘ └───┘  │
              └─────────┬───────────┘
                        ▼
              ┌─────────────────────┐
              │  Result Collator    │
              │  (DSPy module)      │
              └─────────┬───────────┘
                        ▼
              ┌─────────────────────┐
              │  Final response     │
              │  streamed to user   │
              └─────────────────────┘
```

The top-level agent (`MicroAgentsV1Agent`) is itself a DSPy module, composing
the stages above as sub-modules. This makes the entire pipeline eligible for
DSPy optimization (prompt tuning, few-shot bootstrapping, etc.) while keeping
each stage independently testable and swappable.

---

## Stages

### 1. Outcome Planning

The **Outcome Planner** receives the user's message (plus conversation history
and user profile context) and produces a structured list of *outcomes* — the
concrete results the user expects to see when their request is fulfilled. Each
outcome is a short, action-oriented statement.

Along with the outcomes, the planner identifies **dependencies** between them.
A dependency means one outcome requires the result of another before it can be
pursued. The output is a directed acyclic graph (DAG) of outcomes.

**Example:**

> User: "Look at the job posting here (link), add to my tracker, and then help
> me write a cover letter for it."

| # | Outcome | Depends on |
|---|---------|------------|
| 1 | Extract all possible job details from the listing | — |
| 2 | Create new tracker entry populated with job details | 1 |
| 3 | Interactive cover letter writing with user | 1, 2 |

Outcomes that share no dependency edges may execute in parallel in future
iterations, but v1 will execute them sequentially in topological order.

### 2. Workflow Mapping

Each outcome is matched to a **workflow** — a hand-crafted, deterministic
execution plan that knows exactly which tools and micro-agents to invoke and in
what order.

The **Workflow Mapper** compares each outcome against the set of registered
workflows and selects the best match. If no workflow fits, the outcome is
assigned to a **General workflow** — a fallback ReAct loop that can handle
arbitrary requests through open-ended tool use.

At this stage the mapper also performs **parameter extraction**: it pulls the
concrete inputs each workflow needs (URLs, locations, filters, etc.) from the
user's request. When a workflow depends on a prior outcome, some parameters may
not yet be available. These are marked as *deferred* and will be resolved from
the upstream workflow's output at execution time.

### 3. Workflow Execution

The **Workflow Executor** walks the outcome DAG in topological order, running
each workflow in turn. For each workflow it:

1. Resolves any deferred parameters using the outputs of completed upstream
   workflows.
2. Executes the workflow's steps, which may involve tool calls, micro-agent
   invocations, or a combination of both.
3. Streams **progress events** to the user throughout execution — status
   updates, tool activity, and intermediate results — so the user always knows
   work is happening.
4. Captures the workflow's output for use by downstream workflows and the final
   collation step.

### 4. Result Collation

Once all workflows have completed, the **Result Collator** synthesises their
outputs into a coherent final response. This stage exists because the user made
a single request and expects a single, unified answer — not a disconnected list
of workflow outputs. The collator summarises what was accomplished, highlights
key results, and calls out any outcomes that could not be fully achieved.

---

## Workflow System

Workflows are the core building blocks of this design. Each workflow is a
self-contained procedure that knows how to achieve a specific kind of outcome.

```
┌──────────────────────────────────────────────────┐
│                   Workflow                       │
│                                                  │
│  Inputs:   parameters (from user or upstream)    │
│  Steps:    ordered sequence of tool calls and    │
│            micro-agent invocations               │
│  Outputs:  structured result for downstream use  │
│                                                  │
│  Progress: streams SSE events throughout         │
└──────────────────────────────────────────────────┘
```

Workflows are registered in a central catalog. Adding a new workflow means
writing a new class and registering it — the orchestration layer picks it up
automatically without changes to the core agent loop.

The **General workflow** serves as the universal fallback. It runs a
conventional ReAct loop: the LLM reasons about the outcome, selects tools,
observes results, and iterates until the outcome is met. Any outcome that
doesn't match a specialised workflow lands here, so the agent is never stuck.

### Registered Workflows

| Key | Class | Description |
|-----|-------|-------------|
| `general` | `GeneralWorkflow` | Fallback ReAct loop with full tool-set for arbitrary outcomes |
| `job_search` | `JobSearchWorkflow` | Generate diverse search queries, execute them, evaluate fit (0–5★), filter < 3★, return curated results |
| `add_to_tracker` | `AddToTrackerWorkflow` | Identify referenced search results and promote them to the job tracker |
| `edit_job` | `EditJobWorkflow` | Identify referenced tracker job, extract field updates, apply them |
| `remove_jobs` | `RemoveJobsWorkflow` | Identify referenced tracker job(s) and delete them |
| `scrape_job_posting` | `ScrapeJobPostingWorkflow` | Scrape a URL, extract structured job fields, assess fit |
| `compare_jobs` | `CompareJobsWorkflow` | Side-by-side comparison of multiple jobs (compensation, fit, pros/cons) |
| `specialize_resume` | `SpecializeResumeWorkflow` | Interactive resume tailoring for a target job |
| `write_cover_letter` | `WriteCoverLetterWorkflow` | Interactive cover letter writing for a target job |
| `prep_interview` | `PrepInterviewWorkflow` | Generate tailored interview prep (questions, STAR answers, research topics) |
| `application_todos` | `ApplicationTodosWorkflow` | Manage application step checklists for a tracked job |
| `update_profile` | `UpdateProfileWorkflow` | Interactively update the user's job search profile |

### Shared Resolvers

Many workflows need to identify which job(s) or search result(s) the user is
referring to. Rather than re-implementing this logic per-workflow, the
`workflows/resolvers.py` module provides reusable DSPy modules:

- **`JobResolver`** — resolves user references to jobs in the tracker
  (by company name, title, URL, position in list, etc.). Returns a list of
  `ResolvedJob` objects with confidence scores.
- **`SearchResultResolver`** — resolves user references to search results
  in the current conversation. Returns a list of `ResolvedSearchResult`
  objects with confidence scores.

---

## Micro-Agents

Micro-agents are small DSPy modules responsible for a single reasoning or
knowledge task within a workflow. Examples might include:

- Deciding whether a job listing is a good fit for the user
- Extracting structured fields from unstructured job posting text
- Generating a cover letter paragraph given a user profile and job description

Because they are DSPy modules, micro-agents can be individually optimized —
their prompts tuned, few-shot examples bootstrapped, or even their underlying
model swapped — without touching the workflow logic that invokes them.

---

## User Feedback & Streaming

The agent streams SSE events to the frontend throughout the entire process, not
just during the final response. Specifically:

- **Outcome planning** emits a brief status message ("Planning approach...") so
  the user sees immediate activity.
- **Workflow execution** emits `tool_start`/`tool_result` events for each tool
  call and `text_delta` events for progress narration ("Searching for jobs in
  San Francisco...", "Found 12 listings, evaluating fit...").
- **Result collation** streams the final summary as `text_delta` events,
  followed by a `done` event.

The goal is that the user never stares at a blank screen — there is always
visible forward progress.

---

## DSPy Integration

All three top-level agents (`MicroAgentsV1Agent`, `MicroAgentsV1OnboardingAgent`,
`MicroAgentsV1ResumeParser`) are DSPy modules. The internal stages (outcome
planner, workflow mapper, result collator) and the micro-agents within workflows
are also DSPy modules, composed together.

This means the full agent pipeline — or any subset of it — can be optimized
using DSPy's built-in optimizers (e.g. `BootstrapFewShot`, `MIPROv2`). In
practice, optimization would look like:

1. Collect example traces (user request → expected outcomes → expected workflow
   mapping → expected output).
2. Run a DSPy optimizer over the composed module to tune prompts and few-shot
   demonstrations at each stage.
3. Deploy the optimized module with no code changes — only the learned
   parameters change.

This is a future concern; v1 focuses on getting the architecture right with
zero-shot prompting and iterating from there.