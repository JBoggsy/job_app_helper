# LangChain Migration Plan

## Context

The Shortlist app currently has ~84KB of hand-rolled LLM/agent code: 4 custom provider implementations (Anthropic, OpenAI, Gemini, Ollama) each with different streaming patterns, message format translation, and tool schema normalization, plus a custom agent loop with iterative tool calling. ~30% of the provider code is duplicated message format translation. LangChain provides battle-tested abstractions that unify all 4 providers behind a single interface, eliminating this boilerplate while preserving full control over the agent loop and SSE streaming.

### Current Architecture

| Component | File(s) | Responsibility |
|-----------|---------|----------------|
| `LLMProvider` ABC | `backend/llm/base.py` | Defines `stream_with_tools(messages, tools, system_prompt)` + `StreamChunk`/`ToolCall` dataclasses |
| 4 provider implementations | `backend/llm/anthropic_provider.py`, `openai_provider.py`, `gemini_provider.py`, `ollama_provider.py` | SDK-specific message/tool conversion, streaming, `list_models()` |
| Provider factory | `backend/llm/factory.py` | `PROVIDERS` registry, `create_provider(name, api_key, model)` |
| `Agent` | `backend/agent/agent.py` | Main agent loop (25 iterations max, 8 tools), SSE event generation, Anthropic-format tool history |
| `OnboardingAgent` | `backend/agent/agent.py` | Interview loop (6 iterations max, 2 tools), `[ONBOARDING_COMPLETE]` marker detection |
| `ResumeParsingAgent` | `backend/agent/agent.py` | Non-streaming, 0 tools, JSON extraction from LLM response |
| `AgentTools` | `backend/agent/tools.py` | 8 tool methods + `TOOL_DEFINITIONS` (JSON schema dicts), `execute()` dispatcher |

### What LangChain Replaces

| Current Code | LangChain Replacement |
|---|---|
| `LLMProvider` ABC + 4 implementations | `ChatAnthropic`, `ChatOpenAI`, `ChatGoogleGenerativeAI`, `ChatOllama` — all implement `BaseChatModel` |
| `StreamChunk` / `ToolCall` dataclasses | `AIMessageChunk` with `.content` and `.tool_call_chunks` |
| Per-provider message format translation | LangChain's `HumanMessage`, `AIMessage`, `SystemMessage`, `ToolMessage` — each provider adapter handles serialization internally |
| Per-provider tool schema conversion | `model.bind_tools(tools)` — each adapter converts LangChain tool schemas to native format |
| `TOOL_DEFINITIONS` (JSON schema dicts) | `StructuredTool` with Pydantic `BaseModel` input schemas |

### What LangChain Does NOT Replace

| Component | Reason |
|---|---|
| `AgentTools` business logic | Web scraping, DB writes, API calls — unchanged |
| Custom agent loop (`Agent.run()`) | We need fine-grained SSE events (`text_delta`, `tool_start`, `tool_result`) that LangChain's `AgentExecutor` doesn't emit |
| `list_models()` static methods | LangChain has no universal model listing API — keep raw SDK calls |
| Flask SSE routes | No framework change needed; routes just iterate the agent generator |
| Frontend | Zero changes — SSE event contract is preserved exactly |

---

## Key Design Decisions

1. **Keep Flask** — no migration to FastAPI. Use LangChain's synchronous `.stream()` method (all `BaseChatModel` subclasses support it), avoiding async complexity entirely.

2. **Custom agent loop, not `AgentExecutor`** — we need fine-grained SSE events (`text_delta`, `tool_start`, `tool_result`) that `AgentExecutor` doesn't emit. Keep our own iteration loop but swap the LLM call from `provider.stream_with_tools()` to `langchain_model.stream()`.

3. **Wrap existing `AgentTools`** — the business logic (web scraping, DB writes, API calls) stays unchanged. Only the tool registration layer changes (JSON schema dicts → LangChain `StructuredTool`).

4. **Keep old providers for `list_models()` only** — LangChain has no universal model listing API. Extract `list_models()` into a standalone module that uses the raw SDKs (anthropic, openai, google-genai, requests).

5. **LangChain native message types in agent loop** — during the agent loop, use LangChain native types (`AIMessage` with `tool_calls`, `ToolMessage`) instead of the current Anthropic-format content blocks (`tool_use`/`tool_result`). This is actually simpler than the current approach, which manually constructs Anthropic-style content block lists.

---

## Phase 1: Add Dependencies & LangChain Factory

**Goal:** Install LangChain packages and create a new factory, without touching existing code.

### Files to Create

#### `backend/llm/langchain_factory.py`

Factory function that returns a configured LangChain `BaseChatModel` instance:

```python
def create_langchain_model(provider_name: str, api_key: str, model: str = "") -> BaseChatModel:
    """
    Create a LangChain ChatModel for the given provider.

    Args:
        provider_name: One of "anthropic", "openai", "gemini", "ollama"
        api_key: API key (ignored for Ollama)
        model: Optional model override; each provider has a sensible default

    Returns:
        A BaseChatModel instance (ChatAnthropic, ChatOpenAI, etc.)
    """
```

Provider defaults (matching current behavior):

| Provider | Class | Default Model | Key Config |
|----------|-------|---------------|------------|
| `anthropic` | `ChatAnthropic` | `claude-sonnet-4-20250514` | `api_key`, `max_tokens=8096` |
| `openai` | `ChatOpenAI` | `gpt-4o` | `api_key` |
| `gemini` | `ChatGoogleGenerativeAI` | `gemini-2.0-flash` | `google_api_key` |
| `ollama` | `ChatOllama` | `llama3.1` | `base_url="http://localhost:11434"` |

All models should be created with `streaming=True` to enable `.stream()`.

### Files to Modify

#### `pyproject.toml`

Add dependencies:

```toml
dependencies = [
    # ... existing deps ...
    "langchain-core>=0.3",
    "langchain>=0.3",
    "langchain-anthropic>=0.3",
    "langchain-openai>=0.3",
    "langchain-google-genai>=2.0",
    "langchain-ollama>=0.3",
]
```

> **Note:** The existing raw SDK packages (`anthropic`, `openai`, `google-genai`) must remain — they're still used by `list_models()` and potentially by LangChain adapters as transitive dependencies.

### Verification

```bash
uv sync                                           # Dependencies install cleanly
uv run python -c "from backend.llm.langchain_factory import create_langchain_model; print('OK')"
./start.sh                                         # Existing app still works unchanged
```

---

## Phase 2: LangChain Tool Wrappers

**Goal:** Create LangChain `StructuredTool` wrappers around existing `AgentTools` methods, without modifying the existing tools or agent.

### Files to Create

#### `backend/agent/langchain_tools.py`

This file creates Pydantic input models for each tool and a factory function that wraps `AgentTools` methods as LangChain `StructuredTool` instances.

**Pydantic input models** (one per tool, matching current JSON schemas in `TOOL_DEFINITIONS`):

```python
class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    num_results: int = Field(default=5, description="Number of results (max 10)")

class JobSearchInput(BaseModel):
    query: str = Field(description="Job search query")
    location: Optional[str] = Field(default=None, description="Location filter")
    remote_only: Optional[bool] = Field(default=None, description="Remote only filter")
    salary_min: Optional[int] = Field(default=None, description="Minimum salary")
    salary_max: Optional[int] = Field(default=None, description="Maximum salary")
    num_results: int = Field(default=10, description="Number of results (max 20)")
    provider: Optional[str] = Field(default=None, description="Search provider: 'adzuna' or 'jsearch'")

class ScrapeUrlInput(BaseModel):
    url: str = Field(description="URL to scrape")

class CreateJobInput(BaseModel):
    company: str = Field(description="Company name")
    title: str = Field(description="Job title")
    url: Optional[str] = Field(default=None, description="Job posting URL")
    status: Optional[str] = Field(default=None, description="Job status: saved, applied, interviewing, offer, rejected")
    notes: Optional[str] = Field(default=None, description="Notes about the job")
    salary_min: Optional[int] = Field(default=None, description="Minimum salary")
    salary_max: Optional[int] = Field(default=None, description="Maximum salary")
    location: Optional[str] = Field(default=None, description="Job location")
    remote_type: Optional[str] = Field(default=None, description="Remote type: onsite, hybrid, remote")
    tags: Optional[str] = Field(default=None, description="Comma-separated tags")
    contact_name: Optional[str] = Field(default=None, description="Contact person name")
    contact_email: Optional[str] = Field(default=None, description="Contact person email")
    source: Optional[str] = Field(default=None, description="Where the job was found")
    requirements: Optional[str] = Field(default=None, description="Job requirements, newline-separated")
    nice_to_haves: Optional[str] = Field(default=None, description="Nice-to-have qualifications, newline-separated")
    job_fit: Optional[int] = Field(default=None, description="Job fit rating, 0-5 stars")

class ListJobsInput(BaseModel):
    status: Optional[str] = Field(default=None, description="Filter by status")
    company: Optional[str] = Field(default=None, description="Filter by company")
    title: Optional[str] = Field(default=None, description="Filter by title")
    url: Optional[str] = Field(default=None, description="Filter by URL")
    limit: int = Field(default=20, description="Max results to return")

class UpdateUserProfileInput(BaseModel):
    content: str = Field(description="Full updated user profile markdown content")

# read_user_profile and read_resume take no arguments — they use empty input models or no args_schema
```

**Factory function:**

```python
def create_langchain_tools(agent_tools: AgentTools) -> list[StructuredTool]:
    """
    Wrap each AgentTools method as a LangChain StructuredTool.

    The AgentTools instance is captured via closure so all business logic
    (API keys, DB access, app context) works unchanged.

    Returns a list of StructuredTool instances ready to pass to model.bind_tools().
    """
```

**Key implementation details:**

- Use `StructuredTool.from_function()` with `args_schema=<PydanticModel>` for tools with parameters.
- For parameterless tools (`read_user_profile`, `read_resume`), use a wrapper function that takes no arguments and calls the underlying `AgentTools` method with an empty dict.
- Each wrapper function calls `agent_tools.execute(tool_name, kwargs)` to reuse the existing dispatch + error handling.
- Tool `name` and `description` must match the current `TOOL_DEFINITIONS` values exactly (LLMs are sensitive to tool descriptions).
- Return values are dicts (JSON-serializable). LangChain will handle `str()` conversion in `ToolMessage`, but we'll serialize to JSON in the agent loop for consistency with the current behavior.

### Verification

```python
# Manual test in a Python shell with Flask app context
from backend.agent.tools import AgentTools
from backend.agent.langchain_tools import create_langchain_tools

tools = create_langchain_tools(AgentTools())
for t in tools:
    print(f"{t.name}: {t.description[:60]}...")

# Test parameterless tools
profile_tool = next(t for t in tools if t.name == "read_user_profile")
result = profile_tool.invoke({})
print(result)

# Test list_jobs
list_tool = next(t for t in tools if t.name == "list_jobs")
result = list_tool.invoke({"limit": 5})
print(result)
```

---

## Phase 3: LangChain Agent with SSE Bridge (Core Change)

**Goal:** Build new agent classes that use LangChain `BaseChatModel` streaming but yield the exact same SSE event dicts as the current agents. This is the critical phase — the new agents must be drop-in replacements.

### Files to Create

#### `backend/agent/langchain_agent.py`

Three classes:

### `LangChainAgent`

**Constructor:**

```python
class LangChainAgent:
    MAX_ITERATIONS = 25

    def __init__(self, model: BaseChatModel, search_api_key="", adzuna_app_id="",
                 adzuna_app_key="", adzuna_country="us", jsearch_api_key=""):
        self.agent_tools = AgentTools(search_api_key, adzuna_app_id, adzuna_app_key,
                                      adzuna_country, jsearch_api_key)
        self.lc_tools = create_langchain_tools(self.agent_tools)
        self.model_with_tools = model.bind_tools(self.lc_tools)
```

**`run(self, messages)` — generator yielding SSE event dicts:**

The method signature and yield format is identical to the current `Agent.run()`:

```python
def run(self, messages: list[dict]) -> Generator[dict, None, None]:
    """
    Yields dicts with structure: {"event": <event_type>, "data": <event_data>}

    Event types (identical to current implementation):
      - text_delta:          {"content": "..."}
      - tool_start:          {"id": "...", "name": "...", "arguments": {...}}
      - tool_result:         {"id": "...", "name": "...", "result": {...}}
      - tool_error:          {"id": "...", "name": "...", "error": "..."}
      - done:                {"content": "full accumulated text"}
      - error:               {"message": "..."}
    """
```

**Algorithm:**

1. **Convert input messages to LangChain types:**
   - `{"role": "user", "content": "..."}` → `HumanMessage(content="...")`
   - `{"role": "assistant", "content": "..."}` → `AIMessage(content="...")`
   - System prompt is prepended as `SystemMessage`
   - Only the initial DB messages need conversion. Tool call history within the agent loop uses LangChain native types directly.

2. **Build system prompt:**
   - Read user profile via `read_user_profile()` from `backend/agent/user_profile.py`
   - Read resume status via `get_resume_text()` / `get_parsed_resume()` from `backend/resume_parser`
   - Format into `SYSTEM_PROMPT` template (reuse existing prompt from `agent.py`)
   - Prepend as `SystemMessage(content=system_prompt)`

3. **Iteration loop** (max 25 iterations):

   ```python
   for iteration in range(MAX_ITERATIONS):
       # Stream LLM response
       accumulated_text = ""
       accumulated_tool_calls = []

       for chunk in self.model_with_tools.stream(lc_messages):
           # chunk is AIMessageChunk

           # Handle text content
           if chunk.content:
               # chunk.content can be str or list (varies by provider)
               text = chunk.content if isinstance(chunk.content, str) else ""
               if isinstance(chunk.content, list):
                   text = "".join(
                       block.get("text", "") if isinstance(block, dict) else str(block)
                       for block in chunk.content
                   )
               if text:
                   accumulated_text += text
                   yield {"event": "text_delta", "data": {"content": text}}

           # Handle tool call chunks
           if chunk.tool_call_chunks:
               # Accumulate partial tool call chunks into complete tool calls
               # (LangChain streams tool calls as incremental chunks with index, id, name, args)
               for tc_chunk in chunk.tool_call_chunks:
                   _accumulate_tool_call_chunk(accumulated_tool_calls, tc_chunk)

       # After stream completes, finalize tool calls (parse accumulated JSON args)
       final_tool_calls = _finalize_tool_calls(accumulated_tool_calls)

       if not final_tool_calls:
           # No tool calls — we're done
           yield {"event": "done", "data": {"content": accumulated_text}}
           return

       # Build the AIMessage with tool_calls for history
       ai_message = AIMessage(
           content=accumulated_text,
           tool_calls=[
               {"id": tc.id, "name": tc.name, "args": tc.args}
               for tc in final_tool_calls
           ]
       )
       lc_messages.append(ai_message)

       # Execute each tool call
       for tc in final_tool_calls:
           yield {"event": "tool_start", "data": {
               "id": tc.id, "name": tc.name, "arguments": tc.args
           }}

           result = self.agent_tools.execute(tc.name, tc.args)

           if isinstance(result, dict) and "error" in result:
               yield {"event": "tool_error", "data": {
                   "id": tc.id, "name": tc.name, "error": result["error"]
               }}
               tool_content = json.dumps(result)
           else:
               yield {"event": "tool_result", "data": {
                   "id": tc.id, "name": tc.name, "result": result
               }}
               tool_content = json.dumps(result)

           # Append ToolMessage to history
           lc_messages.append(ToolMessage(
               content=tool_content,
               tool_call_id=tc.id
           ))

       # Loop continues — LLM sees the tool results and responds

   # If we reach here, max iterations exceeded
   yield {"event": "error", "data": {"message": "Max iterations reached"}}
   ```

4. **Tool call chunk accumulation helpers:**

   ```python
   def _accumulate_tool_call_chunk(accumulated: list, chunk):
       """
       Merge incremental tool_call_chunks into accumulated tool call state.

       LangChain streams tool calls as partial chunks with:
         - index: which tool call this chunk belongs to
         - id: tool call ID (may be None after first chunk)
         - name: tool name (may be None after first chunk)
         - args: partial JSON string for arguments

       We accumulate by index, building up the full args string.
       """

   def _finalize_tool_calls(accumulated: list) -> list:
       """
       Parse accumulated JSON arg strings into dicts.
       Generate UUID fallback if tool_call id is None.
       Return list of finalized tool call objects.
       """
   ```

### `LangChainOnboardingAgent`

**Differences from `LangChainAgent`:**

| Aspect | `LangChainAgent` | `LangChainOnboardingAgent` |
|--------|-------------------|----------------------------|
| Max iterations | 25 | 6 |
| Tools | All 8 | Only `read_user_profile` and `update_user_profile` |
| System prompt | `SYSTEM_PROMPT` with `{user_profile}` + `{resume_status}` | `ONBOARDING_SYSTEM_PROMPT` with `{user_profile}` |
| Profile re-read | Once at start | After every iteration (tools may update it) |
| Completion marker | None | Detects `[ONBOARDING_COMPLETE]` in accumulated text |
| Extra SSE event | None | `onboarding_complete` (emitted before `done`) |

**`[ONBOARDING_COMPLETE]` handling:**
When the accumulated text contains `[ONBOARDING_COMPLETE]`:
1. Call `set_onboarded(True)` to update the profile frontmatter
2. Strip the marker from the text
3. Yield `{"event": "onboarding_complete", "data": {}}`
4. Yield `{"event": "done", "data": {"content": cleaned_text}}`
5. Return

### `LangChainResumeParser`

**Differences from agent classes:**

- **Non-streaming** — calls `model.invoke()` instead of `model.stream()`
- **No tools** — model is not bound to any tools
- **Returns a dict** — not a generator

```python
class LangChainResumeParser:
    def __init__(self, model: BaseChatModel):
        self.model = model

    def parse(self, raw_text: str) -> dict:
        """
        Send resume text to LLM, extract structured JSON from response.
        Calls save_parsed_resume() and returns the parsed dict.
        Raises RuntimeError on failure.
        """
        messages = [
            SystemMessage(content=RESUME_PARSING_SYSTEM_PROMPT),
            HumanMessage(content=raw_text)
        ]
        response = self.model.invoke(messages)
        text = response.content  # full response text

        parsed = _extract_json(text)  # reuse existing JSON extraction logic
        if not parsed:
            raise RuntimeError("Failed to extract JSON from resume parsing response")

        save_parsed_resume(parsed)
        return parsed
```

### Verification

Test each agent class independently against each provider:

```bash
# Text-only response (no tool calls)
# Verify: text_delta events stream, done event with full text

# Tool call response (ask agent to list jobs)
# Verify: text_delta, tool_start, tool_result, done events all fire

# Multi-tool response (ask agent to search and add a job)
# Verify: multiple tool_start/tool_result pairs, then done

# Error handling (invalid tool args, tool execution failure)
# Verify: tool_error event fires, agent loop continues

# Max iterations (unlikely but testable with a tight limit)
# Verify: error event fires after limit reached

# Onboarding flow
# Verify: onboarding_complete event fires when marker detected

# Resume parsing
# Verify: returns valid dict with expected schema
```

---

## Phase 4: Wire Up Routes & Config

**Goal:** Replace old agent/provider usage in Flask routes with LangChain-based code. The SSE generator and API contracts remain unchanged.

### Files to Modify

#### `backend/routes/chat.py`

**Changes:**
- Replace `from backend.llm.factory import create_provider` with `from backend.llm.langchain_factory import create_langchain_model`
- Replace `from backend.agent.agent import Agent, OnboardingAgent` with `from backend.agent.langchain_agent import LangChainAgent, LangChainOnboardingAgent`
- In `send_message()`: replace `provider = create_provider(...)` + `agent = Agent(provider, ...)` with `model = create_langchain_model(...)` + `agent = LangChainAgent(model, ...)`
- In `_get_onboarding_provider()`: rename to `_get_onboarding_model()`, return a `BaseChatModel` instead of `LLMProvider`. Update callers.
- In `send_onboarding_message()` and `kick_onboarding()`: replace `OnboardingAgent(provider)` with `LangChainOnboardingAgent(model)`
- **The `generate()` SSE function is unchanged** — it just iterates `agent.run(messages)` which yields identical event dicts.

#### `backend/routes/config.py`

**Changes:**
- `/api/config/test` endpoint: replace `create_provider()` + `stream_with_tools()` with `create_langchain_model()` + `model.invoke([HumanMessage("Hello")])`. Since this is a connection test, streaming isn't needed — `invoke()` is simpler.

  ```python
  # Before:
  llm_provider = create_provider(provider, api_key, model)
  for chunk in llm_provider.stream_with_tools(system_prompt="...", messages=[...], tools=[]):
      ...

  # After:
  from langchain_core.messages import HumanMessage, SystemMessage
  model = create_langchain_model(provider, api_key, model)
  response = model.invoke([
      SystemMessage(content="You are a helpful assistant. Respond with just 'OK'."),
      HumanMessage(content="Hello")
  ])
  test_response = response.content
  ```

- `/api/config/models` endpoint: **Unchanged.** Keep using the old provider `list_models()` static methods directly. These are extracted in Phase 5.
- `/api/config/providers` endpoint: **Unchanged.**

#### `backend/routes/resume.py`

**Changes:**
- Replace `from backend.agent.agent import ResumeParsingAgent` with `from backend.agent.langchain_agent import LangChainResumeParser`
- Replace `provider = create_provider(...)` + `ResumeParsingAgent(provider)` with `model = create_langchain_model(...)` + `LangChainResumeParser(model)`
- The rest of the route handler remains the same (`agent.parse(raw_text)` returns a dict).

### Frontend Contracts (Unchanged)

All of these remain identical — **zero frontend changes required:**

| Contract | Status |
|----------|--------|
| SSE events: `text_delta`, `tool_start`, `tool_result`, `tool_error`, `done`, `onboarding_complete`, `error` | Identical |
| `POST /api/chat/conversations/:id/messages` response format | Identical |
| `POST /api/config/test` request/response | Identical |
| `POST /api/config/models` request/response | Identical |
| `GET /api/config/providers` response | Identical |
| `GET /api/health` response | Identical |
| `POST /api/resume/parse` response | Identical |

### Verification

End-to-end browser testing:

1. Start app with `./start.sh`
2. Test chat: send a message, verify streaming text appears
3. Test tool use: ask the agent to search for jobs, scrape a URL, add a job
4. Test onboarding: fresh user flow + returning user (resume mid-onboarding)
5. Test resume upload + parsing
6. Test Settings: connection test for each provider, model listing for each provider
7. Verify frontend compiles: `cd frontend && npm run build`

---

## Phase 5: Clean Up Old Code

**Goal:** Remove replaced code, extract `list_models()` into a standalone module, update documentation.

### Files to Delete

| File | Contents Being Removed |
|------|----------------------|
| `backend/llm/anthropic_provider.py` | `AnthropicProvider` class |
| `backend/llm/openai_provider.py` | `OpenAIProvider` class |
| `backend/llm/gemini_provider.py` | `GeminiProvider` class |
| `backend/llm/ollama_provider.py` | `OllamaProvider` class |
| `backend/llm/base.py` | `LLMProvider` ABC, `StreamChunk`, `ToolCall` dataclasses |
| `backend/agent/agent.py` | `Agent`, `OnboardingAgent`, `ResumeParsingAgent`, system prompts (moved to `langchain_agent.py`) |

### Files to Create

#### `backend/llm/model_listing.py`

Extract `list_models()` functions from the deleted provider files. These use the raw SDKs directly and do not depend on any LangChain code:

```python
def list_anthropic_models(api_key: str) -> list[dict]:
    """List available Anthropic models. Returns [{"id": ..., "name": ...}]."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    models = []
    for model in client.models.list():
        models.append({"id": model.id, "name": getattr(model, "display_name", model.id)})
    models.sort(key=lambda m: m["id"])
    return models

def list_openai_models(api_key: str) -> list[dict]:
    """List available OpenAI models. Returns [{"id": ..., "name": ...}]."""
    ...

def list_gemini_models(api_key: str) -> list[dict]:
    """List available Gemini models. Returns [{"id": ..., "name": ...}]."""
    ...

def list_ollama_models(**kwargs) -> list[dict]:
    """List locally available Ollama models. Returns [{"id": ..., "name": ...}]."""
    ...

MODEL_LISTERS = {
    "anthropic": list_anthropic_models,
    "openai": list_openai_models,
    "gemini": list_gemini_models,
    "ollama": list_ollama_models,
}

def list_models(provider_name: str, api_key: str = "", **kwargs) -> list[dict]:
    """List available models for a provider."""
    lister = MODEL_LISTERS.get(provider_name)
    if not lister:
        raise ValueError(f"Unknown provider: {provider_name}")
    return lister(api_key=api_key, **kwargs) if provider_name != "ollama" else lister(**kwargs)
```

### Files to Modify

#### `backend/llm/factory.py`

- Remove the `PROVIDERS` registry and `create_provider()` function (no longer needed)
- Re-export `create_langchain_model` from `langchain_factory.py` for convenience, or remove this file entirely if all callers import from `langchain_factory.py` directly
- Alternatively, keep `factory.py` as a slim re-export module:

  ```python
  from backend.llm.langchain_factory import create_langchain_model
  from backend.llm.model_listing import list_models, MODEL_LISTERS
  ```

#### `backend/llm/__init__.py`

Update exports if applicable.

#### `backend/routes/config.py`

- Update `/api/config/models` import path: replace `PROVIDERS[name].list_models(api_key)` with `list_models(name, api_key)` from `model_listing.py`

#### `backend/agent/langchain_agent.py`

- Ensure system prompts (`SYSTEM_PROMPT`, `ONBOARDING_SYSTEM_PROMPT`, `RESUME_PARSING_SYSTEM_PROMPT`) are defined here (copied from deleted `agent.py` in Phase 3), or moved to a separate `prompts.py` module.
- Ensure `_extract_json()` helper is defined here or moved to a `utils.py` module.

#### `CLAUDE.md`

Update to reflect:
- Tech stack: add LangChain to the list
- Backend file structure: new files (`langchain_factory.py`, `langchain_tools.py`, `langchain_agent.py`, `model_listing.py`), removed files
- Remove references to `LLMProvider`, `StreamChunk`, `ToolCall`, old provider classes
- Update agent/tools description
- Update any architecture notes mentioning provider abstractions

#### `docs/CHANGELOG.md`

Add entry under `[Unreleased]`:

```markdown
### Changed
- Migrated LLM provider layer from custom implementations to LangChain (`langchain-anthropic`, `langchain-openai`, `langchain-google-genai`, `langchain-ollama`)
- Replaced custom `LLMProvider` ABC and 4 provider implementations with unified `BaseChatModel` interface
- Replaced JSON schema tool definitions with LangChain `StructuredTool` + Pydantic input models
- Agent loop now uses LangChain native message types (`HumanMessage`, `AIMessage`, `ToolMessage`) instead of Anthropic-format content blocks

### Removed
- `backend/llm/base.py` (LLMProvider ABC, StreamChunk, ToolCall)
- `backend/llm/anthropic_provider.py`, `openai_provider.py`, `gemini_provider.py`, `ollama_provider.py`
- `backend/agent/agent.py` (old Agent, OnboardingAgent, ResumeParsingAgent)
```

#### `docs/TODO.md`

Mark any relevant items as done.

### Verification

```bash
# Confirm no old imports remain
grep -r "from backend.llm.anthropic_provider\|from backend.llm.openai_provider\|from backend.llm.gemini_provider\|from backend.llm.ollama_provider\|from backend.llm.base\|from backend.agent.agent" backend/

# Confirm no references to deleted classes
grep -r "LLMProvider\|StreamChunk\|ToolCall\|AnthropicProvider\|OpenAIProvider\|GeminiProvider\|OllamaProvider" backend/ --include="*.py"

# Full regression test
./start.sh
# Run through all verification steps from Phase 4

# Frontend build check
cd frontend && npm run build

# Sidecar build check (ensure PyInstaller still works with LangChain deps)
./build_sidecar.sh
```

### Files to Potentially Remove from `pyproject.toml`

After migration, evaluate whether these raw SDK packages are still needed as direct dependencies:

| Package | Still Needed? | Reason |
|---------|--------------|--------|
| `anthropic` | Yes | Used by `list_anthropic_models()` in `model_listing.py`, also a transitive dep of `langchain-anthropic` |
| `openai` | Yes | Used by `list_openai_models()` in `model_listing.py`, also a transitive dep of `langchain-openai` |
| `google-genai` | Maybe | Check if `langchain-google-genai` uses this or `google-generativeai`. May need to swap for the correct package in `model_listing.py` |
| `requests` | Yes | Used by Ollama model listing, web scraping, and other non-LLM code |

---

## Risk Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `AIMessageChunk.content` format varies across providers (str vs list of dicts) | Agent loop breaks for some providers — text deltas missing or malformed | Medium | Test all 4 providers in Phase 3. Normalize `chunk.content`: if `str`, use directly; if `list`, extract `"text"` fields from text-type blocks. |
| Ollama `bind_tools()` doesn't work with some local models | Tool calling fails for Ollama users — models that don't support function calling will error | Medium | Test with common tool-capable models (`llama3.1`, `mistral`). Document model requirements. Consider a graceful error message when `bind_tools()` fails. |
| Tool call IDs missing from some providers (especially Ollama) | `ToolMessage(tool_call_id=...)` has `None` ID, breaking the tool result → LLM response matching | Medium | Generate `uuid4()` fallback if `tool_call_chunk.id` is `None`. This matches the current behavior where we generate IDs for providers that don't supply them. |
| Sync `.stream()` has edge cases (hangs, silent errors, incomplete chunks) | Streaming hangs or agent loop never terminates | Low | Test sync streaming for each provider. Add a timeout wrapper if needed. Fall back to `.invoke()` + fake streaming as a last resort. |
| Binary size increase from LangChain deps | Tauri desktop app download size grows significantly | Low | Monitor PyInstaller output size before and after. LangChain packages are mostly pure Python (no heavy native deps like NumPy/PyTorch). Expect modest increase (~5-15MB). |
| LangChain version incompatibilities between provider packages | Import errors or runtime failures after `uv sync` | Low | Pin compatible version ranges in `pyproject.toml`. Use `langchain-core>=0.3,<1.0` as the anchor; provider packages follow semver. |
| `ToolMessage` content format expectations vary | Some providers expect `ToolMessage.content` to be a string, others accept dicts | Low | Always serialize tool results to JSON strings in `ToolMessage.content`. This is the universal safe format. |

---

## Verification Plan

After all phases are complete, perform the following end-to-end verification:

### Functional Tests

1. **Start app:** `./start.sh` — verify both servers start cleanly, no import errors
2. **Chat with each provider:** Switch between Anthropic, OpenAI, Gemini, and Ollama in Settings. Send a simple message. Verify streaming text appears in the chat panel.
3. **Tool calling:** Ask the agent to:
   - Search for jobs (`web_search` / `job_search`)
   - Scrape a URL (`scrape_url`)
   - Add a job to the tracker (`create_job`)
   - List tracked jobs (`list_jobs`)
   - Verify all SSE events stream correctly: `tool_start` → `tool_result` or `tool_error` → `done`
4. **Onboarding — fresh user:** Delete `user_profile.md`, reload app. Verify setup wizard → onboarding interview flow works. Verify `onboarding_complete` event fires and profile is saved.
5. **Onboarding — returning user:** Kill the app mid-onboarding. Restart. Verify onboarding resumes with context.
6. **Resume upload + parsing:** Upload a PDF/DOCX resume. Click "Parse with AI". Verify structured data appears.
7. **Settings — connection test:** Test connection for each provider. Verify success/failure messages.
8. **Settings — model listing:** List models for each provider. Verify dropdown populates.

### Build Verification

```bash
# Frontend compiles
cd frontend && npm run build

# No old imports remain
grep -r "from backend.llm.anthropic_provider\|from backend.llm.openai_provider\|from backend.llm.gemini_provider\|from backend.llm.ollama_provider\|from backend.llm.base\|from backend.agent.agent" backend/
# Expected: no output

# No references to deleted classes
grep -r "class AnthropicProvider\|class OpenAIProvider\|class GeminiProvider\|class OllamaProvider\|class LLMProvider" backend/ --include="*.py"
# Expected: no output

# Sidecar builds (for Tauri desktop app)
./build_sidecar.sh
# Verify binary size is within expected range
```

### Performance Sanity Check

- Verify streaming latency is comparable to pre-migration (no perceptible delay increase)
- Verify first-token time is unchanged (LangChain adds minimal overhead over raw SDK calls)
- Monitor memory usage during a multi-tool conversation (ensure no leaks from LangChain internals)
