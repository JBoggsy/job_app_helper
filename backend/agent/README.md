# Agent Designs

This directory contains the agent framework for Shortlist. The application uses
a pluggable **design/strategy** pattern — each agent design is a self-contained
sub-package that implements the three abstract base classes defined in `base.py`.

The active design is selected via the `agent.design` config key (or
`AGENT_DESIGN` env var) and defaults to `"default"`.

---

## Creating a New Agent Design

### 1. Create the sub-package

Add a new folder under `backend/agent/` named after your design in
**snake_case**:

```
backend/agent/my_design/
    __init__.py
```

### 2. Implement the three required classes

Your `__init__.py` must export exactly three classes, named using the
**PascalCase** form of the folder name:

| Folder name   | Required exports                                                  |
|---------------|-------------------------------------------------------------------|
| `my_design`   | `MyDesignAgent`, `MyDesignOnboardingAgent`, `MyDesignResumeParser`|
| `default`     | `DefaultAgent`, `DefaultOnboardingAgent`, `DefaultResumeParser`   |
| `react_agent` | `ReactAgentAgent`, `ReactAgentOnboardingAgent`, `ReactAgentResumeParser` |

Each class must extend the corresponding ABC from `base.py`:

```python
# backend/agent/my_design/__init__.py

from backend.agent.base import Agent, OnboardingAgent, ResumeParser

class MyDesignAgent(Agent):
    def __init__(self, model, search_api_key="", adzuna_app_id="",
                 adzuna_app_key="", adzuna_country="us",
                 jsearch_api_key="", conversation_id=None):
        self.model = model
        # ... store other args ...

    def run(self, messages):
        # Yield SSE event dicts — see base.py for the full protocol
        yield {"event": "text_delta", "data": {"content": "Hello!"}}
        yield {"event": "done", "data": {"content": "Hello!"}}


class MyDesignOnboardingAgent(OnboardingAgent):
    def __init__(self, model):
        self.model = model

    def run(self, messages):
        # Same SSE protocol as Agent.run(), plus "onboarding_complete"
        yield {"event": "text_delta", "data": {"content": "Welcome!"}}
        yield {"event": "onboarding_complete", "data": {}}
        yield {"event": "done", "data": {"content": "Welcome!"}}


class MyDesignResumeParser(ResumeParser):
    def __init__(self, model):
        self.model = model

    def parse(self, raw_text):
        # Return structured resume data as a dict
        return {"name": "...", "experience": []}
```

#### ABC reference

| ABC               | Constructor args                                                                 | Abstract method          |
|-------------------|----------------------------------------------------------------------------------|--------------------------|
| `Agent`           | `model`, `search_api_key`, `adzuna_app_id`, `adzuna_app_key`, `adzuna_country`, `jsearch_api_key`, `conversation_id` | `run(messages) → Generator[dict]` |
| `OnboardingAgent` | `model`                                                                          | `run(messages) → Generator[dict]` |
| `ResumeParser`    | `model`                                                                          | `parse(raw_text) → dict`          |

See `base.py` docstrings for the full SSE event protocol that `run()` must yield.

### 3. Use shared tools

Agent tools live in `backend/agent/tools/` and are available to all designs.
Call `get_tool_definitions()` to retrieve tool metadata and `execute(name, args)`
to run a tool. Your design is responsible for adapting tool definitions to
whatever format your LLM framework expects (e.g. OpenAI function-calling
schema, Anthropic tool-use blocks, etc.).

### 4. Activate your design

Set the config value — either in `config.json`:

```json
{
  "agent": {
    "design": "my_design"
  }
}
```

or via the environment variable:

```bash
export AGENT_DESIGN=my_design
```

The application must be restarted for a design change to take effect (the
classes are resolved at import time).

---

## Extant Designs

| Design name      | Folder                            | Description                                  |
|------------------|-----------------------------------|----------------------------------------------|
| `default`        | `backend/agent/default/`          | Monolithic ReAct loop (reason → act → observe). Each agent streams a tool-calling loop powered by LangChain `bind_tools`. This is the simplest possible design and the default. |
| `fixed_pipeline` | `backend/agent/fixed_pipeline/`   | Structured routing + deterministic pipelines with micro-agents. A Routing Agent classifies user intent, then a pipeline dispatcher executes the right sequence of programmatic steps and scoped LLM calls. Faster, cheaper, and more predictable than ReAct. |

### `default` — Monolithic ReAct Loop

**Files:**

| File                  | Class                      | Description                              |
|-----------------------|----------------------------|------------------------------------------|
| `agent.py`            | `DefaultAgent`             | Main chat agent — multi-turn ReAct loop with all tools |
| `onboarding_agent.py` | `DefaultOnboardingAgent`   | Onboarding interview — ReAct loop, emits `[ONBOARDING_COMPLETE]` marker |
| `resume_parser.py`    | `DefaultResumeParser`      | Single-shot LLM call — parses raw text to structured JSON, no tools |
| `prompts.py`          | —                          | System prompt templates for all three agents |

**How it works:**

1. The agent converts all `AgentTools` definitions to LangChain `StructuredTool`
   objects and calls `model.bind_tools(tools)`.
2. On each `run()` call, it builds a message list (system prompt + conversation
   history) and enters a loop (max 15 iterations).
3. Each iteration streams the LLM response, yielding `text_delta` SSE events.
4. If the response includes tool calls, they are executed via `AgentTools.execute()`,
   results are appended as `ToolMessage`s, and the loop continues.
5. When the LLM responds without tool calls, the loop exits and a `done` event
   is yielded.

### `fixed_pipeline` — Structured Routing + Deterministic Pipelines

**Files:**

| File                  | Class / Purpose                     | Description                              |
|-----------------------|-------------------------------------|------------------------------------------|
| `__init__.py`         | Module exports                      | Exports `FixedPipelineAgent`; re-exports `DefaultOnboardingAgent`, `DefaultResumeParser` |
| `agent.py`            | `FixedPipelineAgent`                | Main entry — route → acknowledge → dispatch pipeline → done |
| `routing.py`          | `route()`                           | Intent classification via `with_structured_output(RoutingResult)` |
| `schemas.py`          | Pydantic models                     | `RoutingResult`, per-pipeline param schemas, micro-agent output schemas |
| `context.py`          | `RequestContext`                    | Per-request cache for profile, resume, jobs; avoids redundant tool calls |
| `streaming.py`        | SSE helpers                         | `yield_text`, `yield_tool_start/result/error`, `execute_tool_with_events` |
| `prompts.py`          | Prompt templates                    | System prompts for routing agent and all 18 micro-agents |
| `micro_agents.py`     | `BaseMicroAgent` + implementations  | `invoke()` for structured output, `stream()` for text; 18 concrete agents |
| `dspy_modules.py`     | DSPy Module wrappers                | Structured-output modules with `forward()` + backward-compat `run()` |
| `dspy_signatures.py`  | DSPy Signature definitions          | Input/output field specs for each DSPy module |
| `dspy_lm.py`          | `LangChainLM`                       | DSPy ↔ LangChain adapter (avoids LiteLLM dependency) |
| `feedback.py`         | Recording + scoring                 | Collects training examples, scores from user actions, metric functions |
| `module_store.py`     | `save_module()` / `load_module_state()` | Persist compiled DSPy modules to `dspy_modules/` |
| `entity_resolution.py`| `resolve_job_ref()`                 | Resolves "the Google job" → Job record by ID, company, or title |
| `pipeline_base.py`    | `Pipeline` + `ToolResult`           | Base class for pipeline subclasses with `exec_tool()` and `text()` helpers |
| `pipelines/`          | Pipeline subclasses                 | One `Pipeline` subclass with `run()` wrapper per request type (11 total) |

**How it works:**

1. User message arrives at `FixedPipelineAgent.run()`.
2. **Routing** — A single LLM call with `with_structured_output(RoutingResult)`
   classifies the message into one of 11 request types and extracts structured
   parameters. Falls back to `general` on failure.
3. **Acknowledgment** — The routing result includes a brief acknowledgment
   string, streamed immediately as `text_delta`.
4. **Pipeline dispatch** — A pure Python registry maps the request type to a
   pipeline function in `pipelines/`.
5. **Pipeline execution** — Each pipeline is a deterministic sequence of:
   - **Programmatic steps** (DB queries, API calls, filtering, templating)
   - **Micro-agent steps** (scoped LLM calls with focused prompts and minimal context)
6. **SSE streaming** — Same event protocol as the default design (`text_delta`,
   `tool_start`, `tool_result`, `done`, etc.). No frontend changes required.

**Request types / pipelines:**

| Type | Pipeline | Description |
|------|----------|-------------|
| `find_jobs` | Query generation → job_search → deduplicate → evaluate fit → add_search_result → summarize | Full job search workflow |
| `research_url` | scrape_url → extract details → evaluate fit → optionally create_job → summarize | Analyze a job posting URL |
| `track_crud` | resolve entity → validate → create/edit/delete job → template confirmation | Job tracker CRUD |
| `query_jobs` | list_jobs → format or analyze (complex questions use AnalysisAgent) | Query tracked jobs |
| `todo_mgmt` | resolve job → branch by action → execute tool(s) → confirm | Todo CRUD + AI generation |
| `profile_mgmt` | read or update profile (complex updates use ProfileUpdateAgent) | Profile management |
| `prepare` | resolve job → gather context → branch by prep_type → stream content | Interview prep, cover letters, etc. |
| `compare` | resolve jobs → branch by mode → comparison/ranking analysis | Compare or rank jobs |
| `research` | generate queries → web_search → synthesize report | General research |
| `general` | load context → stream AdvisorAgent response | Career advice, fallback |
| `multi_step` | execute sub-pipelines sequentially | Compound requests |

**Key advantages over default:**

- **Speed**: Pipelines know the plan; LLM only runs at reasoning-critical steps
- **Cost**: Micro-agents receive minimal context (not the entire tool set)
- **Predictability**: Fixed ordering prevents suboptimal tool sequences
- **Debuggability**: Clear inputs/outputs at each pipeline step
- **Quality**: Pipeline guarantees each step runs (no skipping due to LLM reasoning)
