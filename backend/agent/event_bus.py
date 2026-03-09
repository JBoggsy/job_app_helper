"""Thread-safe event bus for SSE streaming.

Producers call emit() from any thread (agent workers, tool execution).
The consumer drains events via drain_blocking() from the Flask response
generator.
"""

from __future__ import annotations

import queue

_SENTINEL = object()


class EventBus:
    """Thread-safe event bus for SSE streaming.

    Producers call .emit() from any thread. The consumer drains via
    .drain_blocking(). One bus per agent.run() invocation.
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()

    def emit(self, event_type: str, data: dict) -> None:
        """Push an event onto the bus (thread-safe)."""
        self._queue.put({"event": event_type, "data": data})

    def drain_blocking(self):
        """Yield events until close() is called.

        Blocks on each queue.get() with a 0.5s timeout. When an item
        is available, it returns immediately — the timeout only applies
        when the queue is empty (waiting for slow LLM responses).
        """
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is _SENTINEL:
                break
            yield item

    def close(self):
        """Signal that no more events will be produced."""
        self._queue.put(_SENTINEL)
