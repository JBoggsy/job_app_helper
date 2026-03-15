# SSE Streaming Architecture

This document describes how SSE (Server-Sent Events) streaming works in the Shortlist codebase. All real-time agent communication — text streaming, tool progress indicators, and search results — flows through a unified **EventBus** architecture.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Event Types](#2-event-types)
3. [EventBus](#3-eventbus)
4. [AgentTools — Automatic Event Emission](#4-agenttools--automatic-event-emission)
5. [Agent Pattern: Worker Thread + Drain](#5-agent-pattern-worker-thread--drain)
6. [Backend Route Consumption](#6-backend-route-consumption)
7. [Frontend Event Handling](#7-frontend-event-handling)
8. [Per-Agent Design Details](#8-per-agent-design-details)
9. [Adding a New Event Type](#9-adding-a-new-event-type)
10. [Adding a New Tool](#10-adding-a-new-tool)
11. [Key Design Decisions](#11-key-design-decisions)

---

## 1. Overview

Every event in the system — `text_delta`, `tool_start`, `tool_result`, `done`, etc. — flows through a single **`EventBus`** queue per request. The pattern is:

1. Agent `run()` spawns a **worker thread** that does all LLM calls and tool execution.
2. The worker emits events to the `EventBus` via `bus.emit()`.
3. `AgentTools.execute()` **automatically** emits `tool_start`/`tool_result`/`tool_error` — agents and workflows never manually emit tool events.
4. `run()` in the main thread yields events from `bus.drain_blocking()`, which Flask serializes as SSE lines.

This means:
- **All tool calls are visible to the user** — no workflows silently execute tools.
- **Agents and workflows focus on logic**, not event plumbing.
- **New event types** only require an `emit()` call + a frontend handler.

---

## 2. Event Types

| Event | Data Shape | Purpose |
|---|---|---|
| `text_delta` | `{"content": str}` | Incremental LLM text token |
| `tool_start` | `{"id": str, "name": str, "arguments": dict}` | Tool execution beginning (auto-emitted) |
| `tool_result` | `{"id": str, "name": str, "result": dict}` | Tool completed successfully (auto-emitted) |
| `tool_error` | `{"id": str, "name": str, "error": str}` | Tool execution failed (auto-emitted) |
| `done` | `{"content": str}` | Full accumulated text; agent finished |
| `error` | `{"message": str}` | Fatal error; stream terminates |
| `search_result_added` | Full `SearchResult` dict | Emitted by `add_search_result` tool; opens results panel |
| `document_saved` | `{"document": {...}, "job_id": int, "doc_type": str}` | Emitted by `save_job_document` tool; refreshes document editor |
| `onboarding_complete` | `{}` | Onboarding interview finished (onboarding flow only) |

> **Telemetry integration:** All tool calls and agent runs are also recorded by the [telemetry system](TELEMETRY_DESIGN.md) when enabled. The telemetry hooks are separate from the SSE event flow — `AgentTools.execute()` emits events to the `EventBus` *and* records to `TelemetryCollector` independently. See [TELEMETRY_DESIGN.md](TELEMETRY_DESIGN.md) for details.

---

## 3. EventBus

**File:** `backend/agent/event_bus.py`

A thread-safe queue that decouples event producers (worker threads) from the consumer (Flask response generator). One bus is created per `agent.run()` invocation.

```python
class EventBus:
    def emit(self, event_type: str, data: dict) -> None:
        """Push an event (thread-safe). Called from worker threads."""

    def drain_blocking(self):
        """Yield events until close(). Blocks with 0.5s timeout when queue is empty."""

    def close(self):
        """Signal no more events. Causes drain_blocking() to terminate."""
```

**Key properties:**
- `emit()` is thread-safe — can be called from any thread.
- `drain_blocking()` returns items immediately when available; the 0.5s timeout only applies when the queue is empty (no perceptible latency for streaming).
- `close()` must be called in the worker's `finally` block to avoid hanging the response.

---

## 4. AgentTools — Automatic Event Emission

**File:** `backend/agent/tools/__init__.py`

`AgentTools.execute()` automatically emits tool events when an `event_bus` is configured:

1. **Before execution:** emits `tool_start` with tool name, arguments, and a unique call ID.
2. **After execution:** emits `tool_result` (success) or `tool_error` (if result contains `"error"` key).

This means **no agent or workflow code needs to manually emit tool events**. Any call to `tools.execute()` produces the complete `tool_start` → `tool_result`/`tool_error` lifecycle automatically.

The `add_search_result` tool additionally emits `search_result_added` directly to the bus for real-time search results panel updates.

### `_CachedTools` (micro_agents_v1)

The `_CachedTools` proxy in the workflow executor skips event emission on cache hits — the user doesn't see repeated "list_jobs ✓" indicators when results are served from cache. Cache misses delegate to the inner `AgentTools.execute()`, which emits normally.

---

## 5. Agent Pattern: Worker Thread + Drain

All agent `run()` methods follow the same structure:

```python
def run(self, messages):
    from flask import current_app
    app = current_app._get_current_object()

    thread = threading.Thread(target=self._worker, args=(app, messages), daemon=True)
    thread.start()
    yield from self.event_bus.drain_blocking()
    thread.join()

def _worker(self, app, messages):
    with app.app_context():
        try:
            # ... do LLM calls, tool execution, etc. ...
            # emit text_delta, done, etc. to self.event_bus
            self.event_bus.emit("done", {"content": full_text})
        except Exception as exc:
            self.event_bus.emit("error", {"message": str(exc)})
        finally:
            self.event_bus.close()
```

**Why a worker thread?** The worker thread runs LLM calls and tool execution while the main thread drains the bus as a generator for Flask's streaming response. This eliminates complex generator/yield-from chains — all internal code is plain synchronous methods.

**Flask app context:** The worker thread needs `app.app_context()` for DB operations. The `app` reference is captured in the main thread (inside the request context) and passed to the worker.

---

## 6. Backend Route Consumption

**File:** `backend/routes/chat.py`

The route iterates `agent.run(messages)` in a `generate()` function:

```python
def generate():
    for event in agent.run(llm_messages):
        event_type = event["event"]
        event_data = json.dumps(event["data"])
        yield f"event: {event_type}\ndata: {event_data}\n\n"

        if event_type == "text_delta":
            full_text += event["data"]["content"]
        elif event_type in ("tool_start", "tool_result", "tool_error"):
            tool_calls_log.append(event["data"])
        elif event_type == "done":
            # Save assistant message to DB with full_text and tool_calls_log
```

The route is **event-type agnostic** — it forwards all events to the client unchanged. The only special handling is accumulating text and tool data for DB persistence on `done`.

---

## 7. Frontend Event Handling

### SSE parsing (`frontend/src/api.js`)

`_readSSE()` reads the fetch `ReadableStream` line-by-line, parses `event:` / `data:` pairs, and calls the `onEvent` callback.

### ChatPanel (`frontend/src/components/ChatPanel.jsx`)

Messages are stored as an array of **segments** — interleaved text and tool entries:

- **`text_delta`**: Appends to the current text segment (or creates a new one). This is what makes text stream character-by-character.
- **`tool_start`**: Creates a new tool segment `{type: "tool", id, name, status: "running"}` and resets the text accumulator so subsequent text appears _after_ the tool indicator.
- **`tool_result`**: Finds the matching tool segment by `id` and sets `status: "completed"`. If the tool name is in `JOB_MUTATING_TOOLS`, triggers a job list refresh.
- **`tool_error`**: Finds the matching tool segment and sets `status: "error"` with the error message.
- **`search_result_added`**: Accumulates search results and opens the `SearchResultsPanel`.
- **`done`**: Final state push.
- **`error`**: Displays a toast notification.

### Tool rendering

Tool segments render as compact inline status lines:
- **Running**: blue spinning circle + tool name in monospace
- **Completed**: green checkmark (✓) + tool name
- **Error**: amber warning (⚠) + tool name + collapsible "Details" button

### `JOB_MUTATING_TOOLS`

When a `tool_result` fires for a tool in this set (`create_job`, `edit_job`, `remove_job`, `add_job_todo`, `edit_job_todo`, `remove_job_todo`), the job list auto-refreshes. **If you add a new tool that modifies jobs, add its name to this set in ChatPanel.jsx.**

---

## 8. Per-Agent Design Details

### DefaultAgent (`backend/agent/default/agent.py`)

Monolithic **ReAct loop** using `litellm.completion(stream=True)` with OpenAI-format tool calling:

1. Streams every LLM token as `text_delta` in real-time.
2. After each LLM turn, executes any requested tool calls via `tools.execute()` (which auto-emits tool events).
3. Appends tool results to the LLM message history and loops (up to `MAX_ITERATIONS`).
4. When no more tool calls are requested, emits `done`.

**Result:** The user sees a rich, interleaved timeline — streaming text, spinning tool indicators, more streaming text, cyclically.

### MicroAgentsV1Agent (`backend/agent/micro_agents_v1/agent.py`)

**4-stage pipeline**: outcome planning → workflow mapping → workflow execution → result collation.

1. **OutcomePlanner**: Emits "Thinking..." `text_delta`.
2. **WorkflowMapper**: Silent (no events).
3. **WorkflowExecutor**: Runs workflows as plain method calls. Emits step labels (e.g. "**Step 1/3: Find matching jobs**"). Each workflow calls `tools.execute()` which auto-emits tool events.
4. **ResultCollator**: Streams the final synthesized response token-by-token as `text_delta`.

All workflows are **plain methods** returning `WorkflowResult` — they call `self.event_bus.emit()` for text progress and `self.tools.execute()` for tool calls (which auto-emits tool events to the shared bus).

---

## 9. Adding a New Event Type

Since all events flow through the `EventBus`, adding a new event type is straightforward:

**Backend:** Call `event_bus.emit("my_new_event", {"key": "value"})` from any code that has access to the bus. No generator plumbing or yield chains needed.

**Route:** No changes — the route forwards all events to the client unchanged.

**Frontend:** Add a handler in `ChatPanel.jsx`'s event processing logic:

```javascript
} else if (event.event === "my_new_event") {
  // Handle the new event type
}
```

---

## 10. Adding a New Tool

1. Create the tool in `backend/agent/tools/` with `@agent_tool` decorator.
2. Add the mixin to `AgentTools` in `backend/agent/tools/__init__.py`.
3. Tool events (`tool_start`/`tool_result`/`tool_error`) are emitted automatically — no additional SSE work needed.
4. If the tool modifies jobs, add its name to `JOB_MUTATING_TOOLS` in `frontend/src/components/ChatPanel.jsx`.
5. If the tool needs a custom SSE event (like `search_result_added`), emit it directly: `self.event_bus.emit("custom_event", data)`.

---

## 11. Key Design Decisions

- **All events through the bus.** Including `text_delta` and `done` — not just tool events. This eliminates generator/yield-from chains and lets all internal code be plain synchronous methods.
- **One worker thread per request.** The worker runs all LLM calls and tool execution. The main thread is a thin drain loop. Both agent designs use this identical structure.
- **Automatic tool events.** `AgentTools.execute()` handles `tool_start`/`tool_result`/`tool_error` — agents never emit these manually. This guarantees all tool calls are visible to the user.
- **Cache hits are silent.** `_CachedTools` returns cached results without calling the inner `execute()`, so no redundant tool indicators appear.
- **Workflows are plain methods.** In the micro_agents_v1 design, workflow `run()` returns `WorkflowResult` directly (not a generator). Progress events are emitted via `self.event_bus.emit()`.
