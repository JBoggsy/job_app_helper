"""Workflow Executor — run workflow assignments in dependency order.

Given a list of :class:`WorkflowAssignment` objects from the Workflow
Mapper, the executor:

1. Topologically sorts assignments by their outcome dependencies.
2. For each assignment, resolves any **deferred parameters** using a
   ``DeferredParamExtractor`` DSPy module that inspects the results of
   upstream outcomes.
3. Dispatches the assignment to the corresponding registered workflow.
4. Collects :class:`WorkflowResult` objects for downstream stages.

The executor is a deterministic orchestrator — only the deferred-param
resolution step uses an LLM (via DSPy).
"""

from __future__ import annotations

import json
import logging
from graphlib import TopologicalSorter

import dspy

from backend.agent.event_bus import EventBus
from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from .workflow_mapper import WorkflowAssignment
from ..workflows._dspy_utils import build_lm
from ..workflows.registry import WorkflowResult, get_workflow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deferred parameter extraction (DSPy module)
# ---------------------------------------------------------------------------


class ExtractDeferredParamSig(dspy.Signature):
    """Extract a deferred workflow parameter from upstream results.

    A workflow parameter could not be determined at planning time because
    it depends on the output of earlier outcomes.  Given the parameter
    name, its description context, and the results of the dependency
    outcomes, extract the concrete value for this parameter.

    Guidelines:
    - Return ONLY the extracted value — no explanation or extra text.
    - If the dependency results do not contain enough information to
      determine the value, return an empty string.
    - For structured values (lists, objects), return valid JSON.
    """

    param_name: str = dspy.InputField(
        desc="Name of the deferred parameter to resolve"
    )
    param_context: str = dspy.InputField(
        desc=(
            "Context about what this parameter represents — typically the "
            "outcome description and workflow name"
        )
    )
    dependency_results: str = dspy.InputField(
        desc=(
            "JSON-serialised results from the dependency outcomes that this "
            "parameter depends on"
        )
    )
    extracted_value: str = dspy.OutputField(
        desc="The resolved parameter value (plain string or JSON-encoded)"
    )


class DeferredParamExtractor(dspy.Module):
    """DSPy module that resolves deferred workflow parameters.

    Uses chain-of-thought reasoning to inspect upstream workflow results
    and extract the concrete parameter value that was deferred at
    planning time.
    """

    def __init__(self, llm_config: LLMConfig):
        super().__init__()
        self.llm_config = llm_config
        self.extractor = dspy.ChainOfThought(ExtractDeferredParamSig)

    # ------------------------------------------------------------------
    # DSPy forward
    # ------------------------------------------------------------------

    def forward(
        self,
        param_name: str,
        param_context: str,
        dependency_results: str,
    ) -> dspy.Prediction:
        with dspy.context(lm=build_lm(self.llm_config)):
            return self.extractor(
                param_name=param_name,
                param_context=param_context,
                dependency_results=dependency_results,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        param_name: str,
        param_context: str,
        dependency_results: list[WorkflowResult],
    ) -> str:
        """Resolve a single deferred parameter.

        Args:
            param_name: The parameter key to resolve.
            param_context: Human-readable context (outcome description,
                workflow name) so the LLM knows what value is expected.
            dependency_results: Completed :class:`WorkflowResult` objects
                from the outcomes this parameter depends on.

        Returns:
            The extracted value as a string.
        """
        serialised = json.dumps(
            [
                {
                    "outcome_id": r.outcome_id,
                    "success": r.success,
                    "data": r.data,
                    "summary": r.summary,
                }
                for r in dependency_results
            ],
            indent=2,
        )

        prediction = self(
            param_name=param_name,
            param_context=param_context,
            dependency_results=serialised,
        )

        value = prediction.extracted_value
        logger.debug(
            "DeferredParamExtractor resolved %s = %r",
            param_name,
            value,
        )
        return value


# ---------------------------------------------------------------------------
# Per-run tool cache
# ---------------------------------------------------------------------------

# Read-only tools whose results don't change within a single pipeline run.
# Caching these avoids redundant DB queries when multiple workflows (e.g.
# write_cover_letter + specialize_resume) each call list_jobs.
_CACHEABLE_TOOLS = frozenset({
    "list_jobs",
    "read_user_profile",
    "read_resume",
})


class _CachedTools:
    """Thin proxy around ``AgentTools`` that caches read-only tool results.

    Only tools listed in ``_CACHEABLE_TOOLS`` are cached.  The cache key
    is ``(tool_name, sorted_args_tuple)``; mutating tools (``create_job``,
    ``edit_job``, ``update_user_profile``, etc.) pass through and
    invalidate the cache for any tool whose results they may have changed.

    Cache hits return directly without emitting events — this is the
    desired behaviour (read-only tools don't need to show in the UI
    every time they're called from a cache).
    """

    # Tools that mutate job data → invalidate list_jobs cache
    _JOB_MUTATING = frozenset({
        "create_job", "edit_job", "remove_job",
    })
    # Tools that mutate profile → invalidate read_user_profile cache
    _PROFILE_MUTATING = frozenset({
        "update_user_profile",
    })

    def __init__(self, inner: AgentTools):
        self._inner = inner
        self._cache: dict[tuple, object] = {}

    def execute(self, tool_name: str, arguments: dict | None = None):
        arguments = arguments or {}

        # Invalidate affected caches on mutation
        if tool_name in self._JOB_MUTATING:
            self._evict("list_jobs")
        elif tool_name in self._PROFILE_MUTATING:
            self._evict("read_user_profile")

        if tool_name in _CACHEABLE_TOOLS:
            key = (tool_name, tuple(sorted(arguments.items())))
            if key in self._cache:
                return self._cache[key]
            result = self._inner.execute(tool_name, arguments)
            # Only cache successful responses
            if "error" not in result:
                self._cache[key] = result
            return result

        return self._inner.execute(tool_name, arguments)

    def _evict(self, tool_name: str):
        self._cache = {
            k: v for k, v in self._cache.items() if k[0] != tool_name
        }

    # Proxy everything else to the inner AgentTools instance
    def __getattr__(self, name: str):
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# Workflow Executor
# ---------------------------------------------------------------------------


class WorkflowExecutor:
    """Execute workflow assignments in topological order, streaming progress.

    This is a deterministic orchestrator.  It resolves deferred parameters
    via :class:`DeferredParamExtractor`, instantiates each workflow from
    the registry, and collects results.
    """

    def __init__(self, tools: AgentTools, llm_config: LLMConfig,
                 event_bus: EventBus | None = None):
        self.tools = tools
        self.llm_config = llm_config
        self.event_bus = event_bus
        self.param_extractor = DeferredParamExtractor(llm_config)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _topological_order(
        assignments: list[WorkflowAssignment],
    ) -> list[WorkflowAssignment]:
        """Sort assignments so dependencies are executed first.

        Uses ``graphlib.TopologicalSorter`` on the outcome dependency
        graph.  Assignments whose outcomes have no dependencies come
        first.
        """
        by_outcome: dict[int, WorkflowAssignment] = {
            a.outcome.id: a for a in assignments
        }

        sorter: TopologicalSorter[int] = TopologicalSorter()
        for a in assignments:
            sorter.add(a.outcome.id, *a.outcome.depends_on)

        ordered: list[WorkflowAssignment] = []
        for outcome_id in sorter.static_order():
            if outcome_id in by_outcome:
                ordered.append(by_outcome[outcome_id])

        return ordered

    def _resolve_deferred_params(
        self,
        assignment: WorkflowAssignment,
        completed: dict[int, WorkflowResult],
    ) -> dict:
        """Resolve deferred params using the DeferredParamExtractor.

        Returns a new params dict with deferred entries replaced by their
        resolved values.
        """
        params = dict(assignment.params)

        for param_name, dep_ids in assignment.deferred_params.items():
            dep_results = [
                completed[oid]
                for oid in dep_ids
                if oid in completed
            ]

            if not dep_results:
                logger.warning(
                    "No completed results for deferred param %s "
                    "(deps: %s) — leaving empty",
                    param_name,
                    dep_ids,
                )
                params[param_name] = ""
                continue

            context = (
                f"Workflow: {assignment.workflow_name}\n"
                f"Outcome: {assignment.outcome.description}\n"
                f"Parameter: {param_name}"
            )

            # Enrich context with the output schema of upstream workflows
            # so the extractor knows what fields to look for.
            dep_schema_parts = []
            for oid in dep_ids:
                if oid in self._assignment_map:
                    dep_a = self._assignment_map[oid]
                    dep_wf_cls = get_workflow(dep_a.workflow_name)
                    dep_outputs = getattr(dep_wf_cls, "OUTPUTS", {})
                    if dep_outputs:
                        fields = ", ".join(
                            f"{k} ({v})" for k, v in dep_outputs.items()
                        )
                        dep_schema_parts.append(
                            f"Outcome {oid} ({dep_a.workflow_name}) outputs: {fields}"
                        )
            if dep_schema_parts:
                context += "\n\nUpstream output schemas:\n" + "\n".join(dep_schema_parts)

            params[param_name] = self.param_extractor.extract(
                param_name=param_name,
                param_context=context,
                dependency_results=dep_results,
            )

        return params

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute(
        self,
        assignments: list[WorkflowAssignment],
    ) -> list[WorkflowResult]:
        """Execute all workflow assignments in dependency order.

        Returns the list of WorkflowResult objects directly.
        Emits progress events to the event bus.
        """
        ordered = self._topological_order(assignments)
        completed: dict[int, WorkflowResult] = {}
        results: list[WorkflowResult] = []

        # Wrap tools in a per-run cache to avoid redundant DB queries
        # (e.g. multiple workflows calling list_jobs).
        cached_tools = _CachedTools(self.tools)

        # Build a lookup of assignments by outcome ID so deferred-param
        # resolution can reference upstream workflow metadata.
        self._assignment_map: dict[int, WorkflowAssignment] = {
            a.outcome.id: a for a in ordered
        }

        logger.info(
            "WorkflowExecutor: %d assignment(s), topo order: %s",
            len(ordered),
            [f"{a.outcome.id}:{a.workflow_name}" for a in ordered],
        )

        for assignment in ordered:
            outcome_id = assignment.outcome.id
            wf_name = assignment.workflow_name

            # Show a concise description of what's happening — no internal
            # details (workflow names, outcome IDs, params, deferred_params).
            step_label = assignment.outcome.description
            if len(ordered) > 1:
                step_idx = ordered.index(assignment) + 1
                step_label = f"Step {step_idx}/{len(ordered)}: {step_label}"
            if self.event_bus:
                self.event_bus.emit("text_delta",
                    {"content": f"**{step_label}**\n\n"})

            # Resolve deferred parameters using upstream results
            if assignment.deferred_params:
                logger.info(
                    "  Outcome %d has deferred params: %s",
                    outcome_id,
                    assignment.deferred_params,
                )
                params = self._resolve_deferred_params(assignment, completed)
            else:
                params = dict(assignment.params)

            logger.info(
                "  Dispatching outcome %d → workflow=%s params=%s",
                outcome_id,
                wf_name,
                params,
            )

            # Look up and instantiate the workflow
            try:
                workflow_cls = get_workflow(wf_name)
            except KeyError:
                logger.error("Unknown workflow %r — skipping outcome %d", wf_name, outcome_id)
                result = WorkflowResult(
                    outcome_id=outcome_id,
                    success=False,
                    summary=f"Unknown workflow: {wf_name}",
                )
                results.append(result)
                completed[outcome_id] = result
                continue

            workflow = workflow_cls(
                outcome_id=outcome_id,
                params=params,
                tools=cached_tools,
                llm_config=self.llm_config,
                outcome_description=assignment.outcome.description,
                event_bus=self.event_bus,
            )

            # Execute — plain method call
            try:
                result = workflow.run()
            except NotImplementedError:
                logger.warning(
                    "Workflow %r for outcome %d is not yet implemented",
                    wf_name, outcome_id,
                )
                msg = f"The `{wf_name}` workflow is not yet implemented.\n"
                if self.event_bus:
                    self.event_bus.emit("text_delta", {"content": msg})
                result = WorkflowResult(
                    outcome_id=outcome_id,
                    success=False,
                    summary=f"Workflow '{wf_name}' is not yet implemented.",
                )

            logger.info(
                "Workflow %r for outcome %d finished — success=%s",
                wf_name,
                outcome_id,
                result.success,
            )

            results.append(result)
            completed[outcome_id] = result

        logger.info(
            "WorkflowExecutor finished: %d result(s), successes=%d",
            len(results),
            sum(1 for r in results if r.success),
        )

        return results
