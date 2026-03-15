# Telemetry Design: Data Collection & Storage for DSPy Optimization

> Design report for collecting training data during normal app usage to enable DSPy module optimization.

## Table of Contents

- [Background](#background)
- [Part 1: Existing Libraries Considered](#part-1-existing-libraries-considered)
- [Part 2: Collection Architecture](#part-2-collection-architecture)
  - [2.1 TelemetryCollector (Core)](#21-telemetrycollector-core)
  - [2.2 Context Propagation via contextvars](#22-context-propagation-via-contextvars)
  - [2.3 TracedModule Mixin (DSPy Module Capture)](#23-tracedmodule-mixin-dspy-module-capture)
  - [2.4 Tool Call Capture](#24-tool-call-capture)
  - [2.5 Workflow Lifecycle Capture](#25-workflow-lifecycle-capture)
  - [2.6 Run Lifecycle (Context Manager)](#26-run-lifecycle-context-manager)
  - [2.7 User Feedback (API Endpoints)](#27-user-feedback-api-endpoints)
  - [2.8 LiteLLM Callback (Token/Cost Capture)](#28-litellm-callback-tokencost-capture)
- [Part 3: Storage Design](#part-3-storage-design)
  - [3.1 Why a Separate SQLite File](#31-why-a-separate-sqlite-file)
  - [3.2 Schema](#32-schema)
  - [3.3 Compactness Strategies](#33-compactness-strategies)
  - [3.4 Shareability & Export](#34-shareability--export)
- [Part 4: Integration Summary](#part-4-integration-summary)
- [Part 5: DSPy Optimization Methods](#part-5-dspy-optimization-methods)
  - [5.1 Available Methods](#51-available-methods)
  - [5.2 Data Requirements per Method](#52-data-requirements-per-method)
  - [5.3 Recommended Optimization Roadmap](#53-recommended-optimization-roadmap)
- [Part 6: Implementation Plan](#part-6-implementation-plan)

---

## Background

The `micro_agents_v1` agent design uses **25+ DSPy modules** across a 4-stage pipeline (OutcomePlanner -> WorkflowMapper -> WorkflowExecutor -> ResultCollator) plus 12 workflows, an onboarding agent, and a resume parser. All modules currently run **zero-shot** — no optimization, metrics, or training data collection exists yet.

DSPy optimizers (BootstrapFewShot, MIPROv2, COPRO, etc.) require training examples: input/output pairs for individual modules, ideally with quality metrics. The goal of this system is to **passively collect that training data during normal app usage** so that optimization can be applied later — both offline (batch) and online (at inference time via KNNFewShot).

### Design Constraints

**Collection:**
- Clean & simple integration — decorators/mixins, minimal changes to existing code
- Cross-design — not specific to `micro_agents_v1`, reusable by future agent designs
- Lightweight — no user-visible impact on performance or UX
- Error-resilient — telemetry failures never break the app
- Multi-signal — traces, tool calls, user actions, user feedback, LLM metrics
- Easily extensible — new signal types require minimal code changes

**Storage:**
- Compact — efficient storage for high-volume data
- Scalable — handles large volumes without degradation
- Logical representations — relational schema for complex, interrelated data
- Shareable — easy for users to export and send for app improvement

---

## Part 1: Existing Libraries Considered

| Library/Tool | What It Does | Verdict |
|---|---|---|
| **DSPy `module.history`** | In-memory per-module execution history | Useful for reading traces after calls, but volatile (cleared on restart). Use as a *source* to read from, not a sink. |
| **DSPy `bootstrap_trace_data()`** | Runs a program on examples, collects traces + scores | Designed for batch optimization, not continuous collection. Useful reference for the trace format DSPy optimizers expect. |
| **LiteLLM callbacks** | Hook system (`litellm.callbacks`) for logging LLM calls (tokens, latency, cost, model) | Lightweight, already in the stack. Can capture per-LLM-call metrics that DSPy modules don't expose. Worth integrating. |
| **OpenTelemetry / OpenLLMetry** | Distributed tracing standard; OpenLLMetry auto-instruments LiteLLM | Too heavy for a local desktop app. Designed for distributed microservices. Pulls in 5+ packages. |
| **Langfuse / LangSmith / Braintrust** | Cloud LLM observability platforms | Cloud-dependent. Violates local-first and shareability constraints. Users shouldn't need accounts. |
| **MLflow** | ML experiment tracking | Heavyweight server + UI. Overkill for trace collection in a desktop app. |
| **Arize Phoenix** | Open-source LLM observability | Full server process, heavy dependencies (~200MB). Not embeddable. |
| **SQLite (stdlib `sqlite3`)** | Embedded relational database | Already in the stack, zero extra deps, single-file, relational, shareable, battle-tested at scale. **Primary storage recommendation.** |
| **Python `contextvars`** | Thread-safe context propagation (stdlib) | Perfect for propagating `run_id` / `trace_id` through the call stack without passing arguments. Zero deps. |

**Bottom line:** No existing library fits all the constraints. The best approach is a **custom lightweight system** built on stdlib (`sqlite3`, `contextvars`, `threading`, `queue`) plus hooks into DSPy's module history and LiteLLM's callback system. This avoids new dependencies entirely.

---

## Part 2: Collection Architecture

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                       TelemetryCollector                         │
│                  (singleton, background writer)                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Sources (how data enters):                                      │
│  ├── TracedModule mixin ──── DSPy module inputs/outputs/CoT     │
│  ├── AgentTools.execute() ── tool calls (tap existing events)   │
│  ├── Workflow hooks ──────── workflow start/end/result           │
│  ├── Run context manager ─── run lifecycle (start/end/error)    │
│  ├── API endpoints ───────── user feedback (thumbs, corrections)│
│  └── LiteLLM callback ───── token counts, latency, cost        │
│                                                                  │
│  Context Propagation:                                            │
│  └── contextvars (run_id, parent_trace_id)                      │
│                                                                  │
│  Write Path:                                                     │
│  └── queue.Queue → background thread → SQLite batch writes      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 TelemetryCollector (Core)

A singleton that receives structured events and persists them asynchronously.

```python
# backend/telemetry/collector.py  (conceptual)

class TelemetryCollector:
    """Singleton. Receives telemetry events, writes to SQLite in background."""

    def __init__(self, db_path: Path):
        self._queue = queue.Queue()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

    # ── Public API (called from any thread) ──

    def record_run_start(self, run_id, conversation_id, design_name, user_message): ...
    def record_run_end(self, run_id, success, error, final_response, duration_ms): ...
    def record_module_trace(self, trace_id, run_id, parent_trace_id, module_class,
                            signature_name, inputs, outputs, reasoning,
                            duration_ms, success, error): ...
    def record_tool_call(self, call_id, run_id, module_trace_id, tool_name,
                         arguments, result, duration_ms, success, error): ...
    def record_workflow_trace(self, trace_id, run_id, workflow_name, outcome_id,
                              params, result, duration_ms, success, error): ...
    def record_signal(self, run_id, conversation_id, signal_type, data): ...
    def record_llm_call(self, run_id, module_trace_id, model, tokens_in,
                        tokens_out, latency_ms, cost): ...

    # ── Internal ──

    def _writer_loop(self):
        """Drains queue, batch-inserts into SQLite every 500ms or 50 events."""
        ...
```

**Key properties:**
- Every `record_*` method is a **non-blocking `queue.put()`** — producers never wait on I/O
- The writer thread batch-inserts (50 events or 500ms, whichever comes first) for efficiency
- All `record_*` calls are wrapped in try/except at the call site — telemetry errors are logged, never propagated
- The collector is **disabled by default** and enabled via a config flag (`telemetry.enabled` in `config.json`), giving users control

### 2.2 Context Propagation via `contextvars`

The challenge: when a DSPy module deep inside a workflow calls another module, how does the trace know which run and parent trace it belongs to? Answer: `contextvars`.

```python
# backend/telemetry/context.py

import contextvars

current_run_id = contextvars.ContextVar('telemetry_run_id', default=None)
current_trace_id = contextvars.ContextVar('telemetry_trace_id', default=None)
```

This propagates automatically through the call stack (including into `ThreadPoolExecutor` workers if you copy the context). No function signature changes needed anywhere.

### 2.3 TracedModule Mixin (DSPy Module Capture)

The primary integration point for DSPy modules. A mixin class that wraps `__call__` to capture inputs, outputs, and reasoning.

```python
# backend/telemetry/traced_module.py

class TracedModule:
    """Mixin for dspy.Module subclasses. Captures I/O to telemetry.

    Usage:
        class OutcomePlanner(TracedModule, dspy.Module):
            ...
    """

    def __call__(self, *args, **kwargs):
        collector = get_collector()
        if collector is None:
            return super().__call__(*args, **kwargs)

        run_id = current_run_id.get()
        parent_id = current_trace_id.get()
        trace_id = uuid4_short()
        token = current_trace_id.set(trace_id)  # push onto stack

        t0 = time.monotonic()
        try:
            result = super().__call__(*args, **kwargs)
            collector.record_module_trace(
                trace_id=trace_id, run_id=run_id, parent_trace_id=parent_id,
                module_class=type(self).__name__,
                signature_name=self._get_signature_name(),
                inputs=kwargs, outputs=self._extract_outputs(result),
                reasoning=self._extract_reasoning(),
                duration_ms=elapsed(t0), success=True, error=None,
            )
            return result
        except Exception as e:
            collector.record_module_trace(
                trace_id=trace_id, run_id=run_id, parent_trace_id=parent_id,
                module_class=type(self).__name__,
                signature_name=self._get_signature_name(),
                inputs=kwargs, outputs=None, reasoning=None,
                duration_ms=elapsed(t0), success=False, error=str(e),
            )
            raise
        finally:
            current_trace_id.reset(token)  # pop from stack

    def _extract_reasoning(self):
        """Pull CoT reasoning from DSPy module history if available."""
        if hasattr(self, 'history') and self.history:
            last = self.history[-1]
            return getattr(last, 'reasoning', None) or getattr(last, 'rationale', None)
        return None
```

**Integration cost:** Change `class OutcomePlanner(dspy.Module)` to `class OutcomePlanner(TracedModule, dspy.Module)`. One line per module. No other changes needed.

For modules you don't control (like `dspy.ReAct`), the traces are captured when the *parent* module that contains them is traced. The parent's inputs/outputs bracket the full ReAct execution.

### 2.4 Tool Call Capture

Tools already emit `tool_start`/`tool_result`/`tool_error` events through the EventBus. Add a small telemetry hook to `AgentTools.execute()`:

```python
# In AgentTools.execute(), after the existing event emission:
if collector := get_collector():
    collector.record_tool_call(
        call_id=call_id, run_id=current_run_id.get(),
        module_trace_id=current_trace_id.get(),
        tool_name=tool_name, arguments=arguments,
        result=result, duration_ms=elapsed, success="error" not in result,
        error=result.get("error"),
    )
```

Alternatively, this could be a decorator on `execute()` that adds telemetry without touching the method body at all.

### 2.5 Workflow Lifecycle Capture

A decorator for workflow `run()` methods, applied **automatically** via `BaseWorkflow.__init_subclass__`:

```python
# backend/telemetry/decorators.py

def traced_workflow(fn):
    """Decorator for BaseWorkflow.run() methods."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        collector = get_collector()
        if collector is None:
            return fn(self, *args, **kwargs)

        trace_id = uuid4_short()
        t0 = time.monotonic()
        try:
            result = fn(self, *args, **kwargs)
            collector.record_workflow_trace(
                trace_id=trace_id, run_id=current_run_id.get(),
                workflow_name=type(self).__name__,
                outcome_id=self.outcome_id, params=self.params,
                result=result.data if result else None,
                summary=result.summary if result else None,
                duration_ms=elapsed(t0),
                success=result.success if result else False, error=None,
            )
            return result
        except Exception as e:
            collector.record_workflow_trace(
                trace_id=trace_id, run_id=current_run_id.get(),
                workflow_name=type(self).__name__,
                outcome_id=self.outcome_id, params=self.params,
                result=None, summary=None,
                duration_ms=elapsed(t0), success=False, error=str(e),
            )
            raise
    return wrapper
```

**Auto-application in BaseWorkflow:**

```python
class BaseWorkflow(ABC):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'run') and not getattr(cls.run, '_traced', False):
            cls.run = traced_workflow(cls.run)
```

**Integration cost:** Zero per-workflow. One change in `BaseWorkflow`. All existing and future workflows are automatically traced.

### 2.6 Run Lifecycle (Context Manager)

```python
# backend/telemetry/context.py

@contextmanager
def telemetry_run(conversation_id, user_message, design_name):
    """Wraps an entire agent run. Sets contextvars for child traces."""
    collector = get_collector()
    if collector is None:
        yield None
        return

    run_id = uuid4_short()
    token = current_run_id.set(run_id)
    collector.record_run_start(run_id, conversation_id, design_name, user_message)
    t0 = time.monotonic()
    try:
        yield run_id
        collector.record_run_end(run_id, success=True, duration_ms=elapsed(t0))
    except Exception as e:
        collector.record_run_end(run_id, success=False, error=str(e), duration_ms=elapsed(t0))
        raise
    finally:
        current_run_id.reset(token)
```

**Integration in any agent's run method:**

```python
def run(self, messages):
    with telemetry_run(self.conversation_id, messages[-1], "micro_agents_v1"):
        # ... existing pipeline code unchanged ...
```

### 2.7 User Feedback (API Endpoints)

New endpoint in the chat blueprint:

```
POST /api/chat/conversations/:id/messages/:msg_id/feedback
Body: {"signal": "thumbs_up"|"thumbs_down", "comment": "..."}
```

Implicit signals captured from existing actions:
- `add_to_tracker_click` — already exists as a POST endpoint; add one line to record the signal
- `follow_up_correction` — detect in the chat route when a user's follow-up message contains corrective language (heuristic, or log all follow-ups and label later)
- `document_edit_after_generation` — detect when user edits a cover letter/resume shortly after the agent generated it

### 2.8 LiteLLM Callback (Token/Cost Capture)

LiteLLM has a built-in callback system. One-time setup at app startup:

```python
# backend/telemetry/litellm_hook.py

import litellm

class TelemetryLiteLLMCallback(litellm.integrations.custom_logger.CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        if collector := get_collector():
            collector.record_llm_call(
                run_id=current_run_id.get(),
                module_trace_id=current_trace_id.get(),
                model=kwargs.get("model"),
                tokens_in=response_obj.usage.prompt_tokens,
                tokens_out=response_obj.usage.completion_tokens,
                latency_ms=(end_time - start_time).total_seconds() * 1000,
                cost=response_obj._hidden_params.get("response_cost"),
            )

# Register once at startup:
litellm.callbacks = [TelemetryLiteLLMCallback()]
```

**Integration cost:** Two lines at app startup. Captures every LLM call automatically, including those inside DSPy modules and raw `litellm.completion()` calls (like the result collator).

---

## Part 3: Storage Design

### 3.1 Why a Separate SQLite File

Store telemetry in `telemetry.db` (in `get_data_dir()`), separate from `app.db`:

| Concern | Benefit of Separation |
|---|---|
| **Shareability** | User sends one file. No risk of leaking job data, conversations, or profile. |
| **Write contention** | Telemetry writes (high frequency, batched) don't compete with app queries. |
| **Lifecycle** | Can be deleted/reset without touching app state. Can be rotated or archived independently. |
| **Size management** | Easy to monitor, cap, or prune independently. |

### 3.2 Schema

```sql
-- Schema version for future migrations
CREATE TABLE _meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
INSERT INTO _meta VALUES ('schema_version', '1');
INSERT INTO _meta VALUES ('created_at', '...');
INSERT INTO _meta VALUES ('app_version', '...');

-- Complete agent runs (one per user message -> response cycle)
CREATE TABLE runs (
    id              TEXT PRIMARY KEY,
    conversation_id INTEGER,
    design_name     TEXT NOT NULL,
    user_message    TEXT,
    final_response  TEXT,
    started_at      TEXT NOT NULL,   -- ISO 8601
    ended_at        TEXT,
    duration_ms     INTEGER,
    success         INTEGER NOT NULL DEFAULT 1,
    error           TEXT
);

-- DSPy module invocations (nested tree via parent_trace_id)
CREATE TABLE module_traces (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    parent_trace_id TEXT REFERENCES module_traces(id),  -- NULL = top-level
    module_class    TEXT NOT NULL,       -- e.g. "OutcomePlanner"
    signature_name  TEXT,               -- e.g. "PlanOutcomesSig"
    inputs          TEXT,               -- JSON
    outputs         TEXT,               -- JSON
    reasoning       TEXT,               -- CoT text if available
    started_at      TEXT NOT NULL,
    duration_ms     INTEGER,
    success         INTEGER NOT NULL DEFAULT 1,
    error           TEXT
);

-- Tool invocations
CREATE TABLE tool_calls (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    module_trace_id TEXT REFERENCES module_traces(id),
    tool_name       TEXT NOT NULL,
    arguments       TEXT,               -- JSON
    result          TEXT,               -- JSON
    started_at      TEXT NOT NULL,
    duration_ms     INTEGER,
    success         INTEGER NOT NULL DEFAULT 1,
    error           TEXT
);

-- Workflow-level traces
CREATE TABLE workflow_traces (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(id),
    workflow_name       TEXT NOT NULL,
    outcome_id          INTEGER,
    outcome_description TEXT,
    params              TEXT,           -- JSON
    result_data         TEXT,           -- JSON (WorkflowResult.data)
    summary             TEXT,
    started_at          TEXT NOT NULL,
    duration_ms         INTEGER,
    success             INTEGER NOT NULL DEFAULT 1,
    error               TEXT
);

-- Raw LLM call metrics (from LiteLLM callback)
CREATE TABLE llm_calls (
    id              TEXT PRIMARY KEY,
    run_id          TEXT REFERENCES runs(id),
    module_trace_id TEXT REFERENCES module_traces(id),
    model           TEXT,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    latency_ms      INTEGER,
    cost_usd        REAL,
    called_at       TEXT NOT NULL
);

-- User signals (feedback, implicit actions)
CREATE TABLE user_signals (
    id              TEXT PRIMARY KEY,
    run_id          TEXT REFERENCES runs(id),
    conversation_id INTEGER,
    signal_type     TEXT NOT NULL,
    data            TEXT,               -- JSON (flexible payload)
    created_at      TEXT NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX idx_module_traces_run   ON module_traces(run_id);
CREATE INDEX idx_module_traces_class ON module_traces(module_class);
CREATE INDEX idx_tool_calls_run      ON tool_calls(run_id);
CREATE INDEX idx_workflow_traces_run ON workflow_traces(run_id);
CREATE INDEX idx_llm_calls_run       ON llm_calls(run_id);
CREATE INDEX idx_user_signals_run    ON user_signals(run_id);
CREATE INDEX idx_user_signals_type   ON user_signals(signal_type);
CREATE INDEX idx_runs_conversation   ON runs(conversation_id);
CREATE INDEX idx_runs_design         ON runs(design_name);
```

### 3.3 Compactness Strategies

1. **JSON columns instead of normalized sub-tables.** Module inputs/outputs are stored as JSON text, not broken into rows. This avoids join-heavy schemas and reduces row count dramatically. SQLite's `json_extract()` still allows queries into these fields.

2. **Truncation policy for large payloads.** Tool results (especially `scrape_url`, `job_search`) can be enormous. The collector truncates `result` JSON to a configurable max (default 8KB) and stores a `"_truncated": true` flag. Full data is available in `app.db` if needed.

3. **Periodic compaction.** A background job (or on-startup check) prunes telemetry older than a configurable retention period (default 90 days). Runs `DELETE` + `VACUUM`.

4. **WAL mode.** `PRAGMA journal_mode=WAL` gives concurrent reads during batch writes without blocking the writer thread.

5. **Estimated storage:** A typical run produces ~1 run row, ~5-15 module traces, ~3-10 tool calls, ~1-3 workflow traces, ~5-20 LLM calls. At ~500 bytes/row average, that's roughly **5-15 KB per user message**. At 100 messages/day, that's ~1.5 MB/day or ~135 MB over 90 days.

### 3.4 Shareability & Export

**Primary method: copy the file.** `telemetry.db` is a single, self-contained SQLite file.

**Privacy-aware export modes** via `/api/telemetry/export`:
- **Full export** — the raw file (for users who consent to sharing everything)
- **Anonymized export** — strips `user_message`, `final_response`, tool `arguments`/`result` content; keeps only structural data (module names, durations, success/failure, token counts, signal types)

**DSPy-native export** for optimization:

```python
def export_examples(module_class: str, min_score: float = None) -> list[dspy.Example]:
    """Extract successful traces for a module as DSPy training examples."""
    rows = db.execute("""
        SELECT mt.inputs, mt.outputs FROM module_traces mt
        JOIN runs r ON mt.run_id = r.id
        WHERE mt.module_class = ? AND mt.success = 1
    """, [module_class])
    return [dspy.Example(**json.loads(r['inputs'])).with_inputs(...) for r in rows]
```

---

## Part 4: Integration Summary

### Changes to Existing Code

| File | Change | Effort |
|---|---|---|
| `backend/telemetry/` (new package) | `collector.py`, `context.py`, `traced_module.py`, `decorators.py`, `litellm_hook.py`, `schema.py`, `export.py` | New code (core system) |
| `backend/app.py` | Initialize collector at startup, register LiteLLM callback | ~5 lines |
| `backend/config_manager.py` | Add `telemetry.enabled` and `telemetry.retention_days` config fields | ~3 lines |
| `backend/agent/micro_agents_v1/agent.py` | Wrap run body in `with telemetry_run(...)` | ~2 lines |
| `backend/agent/micro_agents_v1/stages/*.py` | Change `dspy.Module` to `TracedModule, dspy.Module` in class definitions | 1 line each (4 files) |
| `backend/agent/micro_agents_v1/workflows/resolvers.py` | Same mixin change | 1 line each (2 classes) |
| `backend/agent/micro_agents_v1/workflows/*.py` | Nothing — `BaseWorkflow.__init_subclass__` auto-applies tracing | **0 lines** |
| `backend/agent/micro_agents_v1/resume_stages/*.py` | Same mixin change | 1 line each (5 classes) |
| `backend/agent/tools/__init__.py` | Add telemetry hook in `execute()` | ~5 lines |
| `backend/routes/chat.py` | Add feedback endpoint, record implicit signals | ~20 lines |

**Total touch points in existing code:** ~15 one-line changes + ~30 lines of glue code.

### Error Isolation Pattern

Every integration point follows this pattern:

```python
try:
    collector.record_whatever(...)
except Exception:
    logger.debug("Telemetry recording failed", exc_info=True)
    # Never propagate — user experience is unaffected
```

The `TracedModule.__call__` wrapper re-raises the original exception from `super().__call__()` — it only swallows telemetry-specific errors.

### Cross-Design Generality

Nothing in this system is `micro_agents_v1`-specific:
- `TracedModule` works with any `dspy.Module` subclass in any design
- `traced_workflow` works with any class that has a `run()` returning a result with `.success`/`.data`/`.summary`
- `telemetry_run()` context manager works with any agent that has a run loop
- `contextvars` propagation is design-agnostic
- The LiteLLM callback captures all LLM calls regardless of which agent triggered them

---

## Part 5: DSPy Optimization Methods

### 5.1 Available Methods

DSPy 3.1.3 provides these optimization methods:

#### BootstrapFewShot
- **Type:** Offline
- **Mechanism:** Runs the module on training examples, uses a metric to identify successful traces, inserts those traces as few-shot demonstrations into the prompt
- **Best targets:** OutcomePlanner, WorkflowMapper, JobResolver, SearchResultResolver, ExtractJobEditsSig, SectionSegmenter
- **Training data:** 10-30 examples per module (inputs + expected outputs, or inputs + metric function)

#### BootstrapFewShotWithRandomSearch
- **Type:** Offline
- **Mechanism:** Like BootstrapFewShot but tries multiple random subsets of demonstrations, evaluates each on a validation set, picks the best combination
- **Best targets:** GenerateSearchQueriesSig, WriteCoverLetterWorkflow (all 4 stages), SpecializeResumeWorkflow (5 stages)
- **Training data:** Same as BootstrapFewShot + a separate validation set (20-50 examples)

#### MIPROv2
- **Type:** Offline
- **Mechanism:** Jointly optimizes instruction text and few-shot demonstrations using Bayesian optimization. Can optimize multi-module pipelines end-to-end.
- **Best targets:** OutcomePlanner->WorkflowMapper pipeline, JobSearchWorkflow pipeline, Resume parsing pipeline
- **Training data:** 50-200 labeled examples with end-to-end quality metrics; a teacher model for instruction proposal

#### COPRO
- **Type:** Offline
- **Mechanism:** Iteratively generates and refines instruction text only (no few-shot demos). Uses the LLM to critique and improve its own instructions based on failure cases.
- **Best targets:** EvaluateJobFitSig (job fit rubric), VerifyJobUrlsSig, ResultCollator (if converted to DSPy module)
- **Training data:** 20-50 labeled examples with a programmatic metric function

#### KNNFewShot
- **Type:** Online (at inference time)
- **Mechanism:** At inference time, retrieves the k most similar past examples to the current input and uses them as few-shot demonstrations. Different inputs get different demos.
- **Best targets:** WorkflowMapper, JobResolver, SearchResultResolver, OutcomePlanner
- **Training data:** A vectorstore of past successful examples (50+ minimum, accumulates over time from production)

#### BootstrapFinetune
- **Type:** Offline
- **Mechanism:** Bootstraps successful traces then fine-tunes the underlying LLM instead of inserting in-context demonstrations. Produces a specialized model.
- **Best targets:** Resume parsing pipeline, EvaluateJobFitSig (high-volume tasks where per-call cost matters)
- **Training data:** 100-500+ successful traces; access to a fine-tuning API

#### BetterTogether
- **Type:** Offline
- **Mechanism:** Jointly optimizes prompt-based and fine-tuning-based components. Decides which modules to fine-tune vs. few-shot, finding the Pareto-optimal mix.
- **Best targets:** The entire micro_agents_v1 pipeline (capstone optimization)
- **Training data:** 200+ end-to-end examples with quality metrics; fine-tuning API access

#### SIMBA / GEPA
- **Type:** Offline
- **SIMBA:** Finds simpler prompts that still perform well (reduces prompt length and cost)
- **GEPA:** Uses evolutionary algorithms to optimize prompts
- **Best targets:** Post-MIPROv2 compression (SIMBA); alternative to MIPROv2 for pipeline-level optimization (GEPA)
- **Training data:** Same as MIPROv2 (50-200 labeled examples)

### 5.2 Data Requirements per Method

| Method | Type | Min Examples | Needs Validation Set | Needs Metric | Needs Fine-tune API |
|---|---|---|---|---|---|
| BootstrapFewShot | Offline | 10-30 | No | Yes | No |
| BootstrapFewShotWithRandomSearch | Offline | 30-50 | Yes (20-50) | Yes | No |
| MIPROv2 | Offline | 50-200 | Yes | Yes | No |
| COPRO | Offline | 20-50 | No | Yes | No |
| KNNFewShot | Online | 50+ (grows) | No | No (uses past successes) | No |
| BootstrapFinetune | Offline | 100-500 | No | Yes | Yes |
| BetterTogether | Offline | 200+ | Yes | Yes | Yes |
| SIMBA / GEPA | Offline | 50-200 | Yes | Yes | No |

### 5.3 Recommended Optimization Roadmap

| Phase | Method | Target Modules | Data Needed | Type |
|---|---|---|---|---|
| **1** | BootstrapFewShot | OutcomePlanner, WorkflowMapper, JobResolver, SearchResultResolver | 10-30 curated examples each | Offline |
| **2** | COPRO | EvaluateJobFitSig, VerifyJobUrlsSig, SectionSegmenter | 20-50 examples with metrics | Offline |
| **3** | BootstrapFewShotWithRandomSearch | WriteCoverLetterWorkflow, SpecializeResumeWorkflow, GenerateSearchQueriesSig | 30-50 examples + validation set | Offline |
| **4** | KNNFewShot | WorkflowMapper, resolvers (wrap Phase 1 modules) | Accumulated production traces (50+) | Online |
| **5** | MIPROv2 | OutcomePlanner->WorkflowMapper pipeline, JobSearchWorkflow pipeline, Resume parser pipeline | 50-200 examples per pipeline | Offline |
| **6** | BootstrapFinetune | High-volume modules (resume parser, job fit scorer) if cost is a concern | 100-500 traces | Offline |

Phases 1-2 are low-effort, high-impact. Phase 4 (KNNFewShot) is the natural "system gets smarter over time" path once you have a trace collection pipeline.

---

## Part 6: Implementation Plan

### Phase 1: Core Telemetry Infrastructure [DONE]

> Goal: Build the foundational `backend/telemetry/` package — storage, collector, context propagation — with no integration into the app yet. Fully testable in isolation.

**Step 1.1: Schema and database initialization** [DONE]
- Created `backend/telemetry/__init__.py` with package-level exports
- Created `backend/telemetry/schema.py` with `SCHEMA_VERSION = 1`, `init_db()`, `_migrate_db()`
- Full schema with all 6 tables, indexes, WAL mode, `_meta` tracking

**Step 1.2: TelemetryCollector** [DONE]
- Created `backend/telemetry/collector.py` with background writer thread, batch flush (500ms/50 events), all `record_*` methods, JSON serialization with Pydantic/dataclass support, 8KB truncation, `init_collector()`/`get_collector()`/`shutdown_collector()` singleton accessors, `compact()` for retention

**Step 1.3: Context propagation** [DONE]
- Created `backend/telemetry/context.py` with `current_run_id`/`current_trace_id` ContextVars, `telemetry_run()` context manager, `copy_telemetry_context()` for ThreadPoolExecutor

### Phase 2: Collection Hooks (Decorators & Mixin) [DONE]

> Goal: Build the TracedModule mixin and workflow decorator — the reusable pieces that any agent design can adopt.

**Step 2.1: TracedModule mixin** [DONE]
- Created `backend/telemetry/traced_module.py` with `TracedModule` class, `__call__` override with context push/pop, error isolation, `_get_signature_name()`, `_extract_outputs()` (handles DSPy Prediction `.toDict()`), `_extract_reasoning()` (reads CoT from prediction attrs)

**Step 2.2: Workflow decorator** [DONE]
- Created `backend/telemetry/decorators.py` with `traced_workflow(fn)` decorator and `_traced` sentinel

**Step 2.3: LiteLLM callback** [DONE]
- Created `backend/telemetry/litellm_hook.py` with `TelemetryLiteLLMCallback` (success + failure events), `register_litellm_callback()` with duplicate protection

### Phase 3: Integration into Existing Code [DONE]

> Goal: Wire the telemetry system into the app with minimal changes to existing files.

**Step 3.1: App startup / shutdown** [DONE]
- Added `_init_telemetry()` to `backend/app.py` — reads config, initializes collector, registers LiteLLM callback, runs compaction on startup, registers atexit handler
- Added `telemetry` section to `DEFAULT_CONFIG` in `backend/config_manager.py`: `{"enabled": true, "retention_days": 90}`

**Step 3.2: Agent run lifecycle** [DONE]
- Wrapped `_pipeline()` body in `with telemetry_run(...)` in `agent.py`
- Wrapped `_worker()` body in `with telemetry_run(...)` in `onboarding_agent.py`

**Step 3.3: DSPy module tracing (TracedModule mixin)** [DONE]
- Added `TracedModule` mixin to all 10 dspy.Module subclasses: OutcomePlanner, WorkflowMapper, DeferredParamExtractor, JobResolver, SearchResultResolver, SectionSegmenter, ContactExtractor, ExperienceEducationExtractor, SkillsExtractor, SkillInferrer
- Inner workflow DSPy calls (inline `dspy.ChainOfThought(...)`) are not wrapped — they're captured at the workflow level via `traced_workflow` and at the LLM level via the LiteLLM callback

**Step 3.4: Workflow tracing (auto-applied)** [DONE]
- Added `__init_subclass__` to `BaseWorkflow` in `registry.py` that auto-wraps `run()` with `traced_workflow` — all 12 workflows traced with zero per-workflow changes

**Step 3.5: Tool call tracing** [DONE]
- Added telemetry recording to `AgentTools.execute()` with timing, error isolation, and contextvar-based run/trace linking

**Step 3.6: ThreadPoolExecutor context propagation** [DONE — utility provided]
- Added `TracedThreadPoolExecutor` and `copy_telemetry_context()` to `backend/telemetry/context.py` as opt-in utilities. Workflows can adopt these when needed — the main traces are already captured at workflow and run level without them.

### Phase 4: User Feedback & Signals [DONE]

> Goal: Add API endpoints and frontend components for collecting explicit user feedback, plus implicit signal capture from existing user actions.

**Step 4.1: Feedback API endpoint** [DONE]
- Added `POST /api/chat/conversations/<id>/messages/<msg_id>/feedback` endpoint accepting `{"signal": "thumbs_up"|"thumbs_down", "comment": "..."}`

**Step 4.2: Implicit signal capture** [DONE]
- Added `add_to_tracker` signal recording to the existing `add_search_result_to_tracker` endpoint

**Step 4.3: Frontend feedback UI** [DONE]
- Added `sendMessageFeedback()` to `frontend/src/api.js`
- Added thumbs up/down buttons on completed assistant messages in `ChatPanel.jsx` with color state tracking

**Step 4.4: Message-to-run linking** [DEFERRED]
- Deferred to a future phase — current approach stores `conversation_id` on signals which is sufficient for correlating feedback to runs via the `runs` table

### Phase 5: Export & Maintenance [DONE]

> Goal: Add export functionality for sharing telemetry data and DSPy optimization, plus retention/compaction.

**Step 5.1: Export utilities** [DONE]
- Created `backend/telemetry/export.py` with `export_full()`, `export_anonymized()`, `export_dspy_examples()`, `export_jsonl()`, and `get_stats()`

**Step 5.2: Export API endpoints** [DONE]
- Added `GET /api/telemetry/stats` and `GET /api/telemetry/export?mode=full|anonymized` to `backend/routes/config.py`

**Step 5.3: Retention & compaction** [DONE]
- `compact()` method on TelemetryCollector, called at startup in `_init_telemetry()` with configurable retention days

**Step 5.4: Settings UI for telemetry** [DONE]
- Added `TelemetrySection` component to SettingsPage showing run count, total records, size, and full/anonymized export buttons

### Phase 6: Verification & Documentation [DONE]

> Goal: Ensure the system works end-to-end, document it, and update project files.

**Step 6.1: Automated integration test** [DONE]
- Verified: app creates with telemetry initialized, collector running, telemetry.db created, TracedModule in MRO for all DSPy modules, workflows auto-traced, LiteLLM callback registered, context propagation works, runs table populated from context manager test
- Full live testing (with LLM calls) deferred to manual QA

**Step 6.2: Error resilience testing** [DONE — by design]
- All telemetry recording wrapped in try/except at every integration point
- Collector returns None when disabled (fast no-op path)
- Writer thread is daemon (won't block app shutdown)

**Step 6.3: Documentation updates** [DONE]
- Updated `CLAUDE.md`: telemetry package in project structure [DONE], config fields [DONE], API endpoints [DONE]
- Updated `docs/CHANGELOG.md` with telemetry feature entry [DONE]
