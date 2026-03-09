"""Application Todos workflow — manage application step checklists.

Pipeline:
1. A ``JobResolver`` identifies which tracked job to manage todos for.
2. A DSPy module classifies the user's intent — one of: ``generate``
   (create a recommended checklist), ``toggle`` (mark todos complete/
   incomplete), ``add`` (add specific items), ``remove`` (delete items),
   or ``list`` (just show the current todos).
3. For ``generate``: a DSPy module analyses the job listing and user
   profile to produce categorised application steps.
4. For ``toggle``/``add``/``remove``: a DSPy module extracts the
   specifics and the appropriate tool calls are made.
5. The current state of the todo list is returned.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import dspy
from pydantic import BaseModel, Field

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from ._dspy_utils import build_lm
from .registry import BaseWorkflow, WorkflowResult, register_workflow
from .resolvers import JobResolver

logger = logging.getLogger(__name__)

VALID_TODO_CATEGORIES = {"document", "question", "assessment", "reference", "other"}


# ---------------------------------------------------------------------------
# DSPy signatures
# ---------------------------------------------------------------------------


class ClassifyTodoIntentSig(dspy.Signature):
    """Classify the user's intent regarding application todos.

    Given the user's message and the current todo list for a job,
    determine what action they want to take.

    Guidelines:
    - ``generate``: user wants you to create/suggest a checklist of
      application steps (e.g. "what do I need to do to apply?", "create
      a checklist", "help me plan my application").
    - ``toggle``: user wants to mark one or more todos as completed or
      incomplete (e.g. "I finished the cover letter", "mark the resume
      as done").
    - ``add``: user wants to add specific todo item(s) (e.g. "add a
      todo to research the company").
    - ``remove``: user wants to delete todo item(s) (e.g. "remove the
      reference check item").
    - ``list``: user just wants to see the current todos (e.g. "what's
      on my list?", "show my todos").
    """

    user_message: str = dspy.InputField(desc="The user's message about application todos")
    job_summary: str = dspy.InputField(desc="Brief summary of the job (title, company)")
    current_todos: str = dspy.InputField(desc="JSON list of current todos for this job (may be empty)")
    intent: str = dspy.OutputField(
        desc="One of: generate, toggle, add, remove, list"
    )


class GeneratedTodo(BaseModel):
    """A single generated todo item."""

    title: str = Field(description="Concise action-oriented title")
    category: str = Field(
        description="One of: document, question, assessment, reference, other"
    )
    description: str = Field(description="Detailed description of what to do")
    sort_order: int = Field(description="Suggested order (1-based)")


class GenerateTodosSig(dspy.Signature):
    """Generate a recommended application checklist for a job.

    Given the job details and the user's profile, produce a practical,
    ordered list of steps the user should take to apply for this job.

    Guidelines:
    - Include 4–8 actionable items, covering typical application steps.
    - Tailor items to the specific job (e.g. if requirements mention a
      portfolio, include "Prepare portfolio").
    - Use the correct category for each item: ``document`` for things to
      prepare (resume, cover letter, portfolio), ``question`` for
      research tasks, ``assessment`` for tests/challenges, ``reference``
      for reference-related tasks, ``other`` for anything else.
    - Order items in a logical sequence (research first, then documents,
      then application submission).
    - Do NOT include items that duplicate existing todos.
    """

    job_details: str = dspy.InputField(desc="Job information (title, company, requirements, etc.)")
    user_profile: str = dspy.InputField(desc="The user's job search profile (may be empty)")
    existing_todos: str = dspy.InputField(desc="JSON list of existing todos to avoid duplicates")
    todos: list[GeneratedTodo] = dspy.OutputField(desc="Recommended application checklist items")


class TodoAction(BaseModel):
    """A specific action to perform on a todo item."""

    action: str = Field(description="One of: toggle_complete, toggle_incomplete, add, remove")
    todo_id: Optional[int] = Field(
        default=None,
        description="ID of the existing todo to act on (for toggle/remove)"
    )
    title: Optional[str] = Field(
        default=None,
        description="Title for a new todo (for add action)"
    )
    category: Optional[str] = Field(
        default=None,
        description="Category for a new todo (for add action)"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description for a new todo (for add action)"
    )


class ExtractTodoActionsSig(dspy.Signature):
    """Extract specific todo actions from the user's message.

    Given the user's message and the current todo list, determine the
    exact operations to perform.

    Guidelines:
    - For toggle actions, match the user's description to existing todos
      by title or content and set the appropriate completion state.
    - For remove actions, match similarly and return the todo IDs.
    - For add actions, extract the title and optionally a category and
      description.
    - A single user message may result in multiple actions.
    """

    user_message: str = dspy.InputField(desc="The user's message describing todo changes")
    current_todos: str = dspy.InputField(
        desc="JSON list of current todos (id, title, category, completed, ...)"
    )
    actions: list[TodoAction] = dspy.OutputField(desc="List of todo actions to perform")


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@register_workflow("application_todos")
class ApplicationTodosWorkflow(BaseWorkflow):
    """Manage application task lists for a specific job."""

    OUTPUTS = {
        "job": "dict — the target job record",
        "intent": "str — classified action (generate/list/toggle/add/remove)",
        "added_todos": "list[dict] — newly created todos (if any)",
        "final_todos": "list[dict] — full current todo list after changes",
    }

    def _resolve_job(self, user_message: str, conversation_context: str) -> dict | None:
        """Resolve the target job, emitting progress events. Returns job dict or None."""
        # Check if job_id was provided directly in params
        job_id = self.params.get("job_id")
        if job_id:
            result = self.tools.execute("list_jobs", {})
            if "error" not in result:
                for j in result.get("jobs", []):
                    if j["id"] == int(job_id):
                        return j
            # Fall through to resolver if direct lookup failed

        self.event_bus.emit("text_delta", {"content": "Identifying which job to manage todos for...\n"})

        jobs_response = self.tools.execute("list_jobs", {"limit": 50})
        if "error" in jobs_response:
            self.event_bus.emit("text_delta", {"content": f"Error fetching jobs: {jobs_response['error']}\n"})
            return None

        jobs = jobs_response.get("jobs", [])
        if not jobs:
            self.event_bus.emit("text_delta", {"content": "No jobs in the tracker yet.\n"})
            return None

        resolver = JobResolver(self.llm_config)
        resolved = resolver.resolve(
            user_message=user_message,
            jobs=jobs,
            conversation_context=conversation_context,
        )

        if not resolved:
            self.event_bus.emit("text_delta", {"content": "Couldn't determine which job you're referring to. Please be more specific.\n"})
            return None

        job_id = resolved[0].job_id
        for j in jobs:
            if j["id"] == job_id:
                return j

        return None

    def _classify_intent(self, user_message: str, job: dict, todos: list[dict]) -> str:
        """Classify the user's intent regarding todos."""
        lm = build_lm(self.llm_config)
        classifier = dspy.ChainOfThought(ClassifyTodoIntentSig)

        with dspy.context(lm=lm):
            result = classifier(
                user_message=user_message,
                job_summary=f"{job['title']} at {job['company']}",
                current_todos=json.dumps(todos, default=str),
            )

        intent = result.intent.strip().lower()
        valid_intents = {"generate", "toggle", "add", "remove", "list"}
        if intent not in valid_intents:
            logger.warning("Unknown intent %r, defaulting to 'generate'", intent)
            intent = "generate"
        return intent

    def _generate_todos(
        self, job: dict, todos: list[dict],
    ) -> list[dict]:
        """Generate recommended todos and add them via the tool."""
        self.event_bus.emit("text_delta", {"content": "Generating recommended application steps...\n"})

        # Load user profile for context
        profile_resp = self.tools.execute("read_user_profile", {})
        user_profile = profile_resp.get("content", "")

        # Build job details string
        job_details = json.dumps(
            {k: v for k, v in job.items() if v is not None},
            default=str,
        )

        lm = build_lm(self.llm_config)
        generator = dspy.ChainOfThought(GenerateTodosSig)

        with dspy.context(lm=lm):
            result = generator(
                job_details=job_details,
                user_profile=user_profile,
                existing_todos=json.dumps(todos, default=str),
            )

        added = []
        for i, todo in enumerate(result.todos):
            category = todo.category if todo.category in VALID_TODO_CATEGORIES else "other"
            add_result = self.tools.execute("add_job_todo", {
                "job_id": job["id"],
                "title": todo.title,
                "category": category,
                "description": todo.description,
            })

            if "error" in add_result:
                logger.error("Failed to add todo: %s", add_result["error"])
                self.event_bus.emit("text_delta", {"content": f"  Failed to add: {todo.title}\n"})
            else:
                added.append(add_result["todo"])
                self.event_bus.emit("text_delta", {
                    "content": f"  Added: **{todo.title}** ({category})\n",
                })

        return added

    def _execute_actions(
        self, job: dict, user_message: str, todos: list[dict],
    ) -> list[dict]:
        """Extract and execute specific todo actions from the user message."""
        lm = build_lm(self.llm_config)
        extractor = dspy.ChainOfThought(ExtractTodoActionsSig)

        with dspy.context(lm=lm):
            result = extractor(
                user_message=user_message,
                current_todos=json.dumps(todos, default=str),
            )

        results = []
        for action in result.actions:
            if action.action in ("toggle_complete", "toggle_incomplete"):
                if action.todo_id is None:
                    continue
                completed = action.action == "toggle_complete"
                resp = self.tools.execute("edit_job_todo", {
                    "job_id": job["id"],
                    "todo_id": action.todo_id,
                    "completed": completed,
                })
                if "error" not in resp:
                    status = "completed" if completed else "incomplete"
                    self.event_bus.emit("text_delta", {"content": f"  Marked **{resp['todo']['title']}** as {status}\n"})
                    results.append(resp["todo"])
                else:
                    self.event_bus.emit("text_delta", {"content": f"  Error: {resp['error']}\n"})

            elif action.action == "add":
                if not action.title:
                    continue
                category = action.category if action.category in VALID_TODO_CATEGORIES else "other"
                resp = self.tools.execute("add_job_todo", {
                    "job_id": job["id"],
                    "title": action.title,
                    "category": category,
                    "description": action.description or "",
                })
                if "error" not in resp:
                    self.event_bus.emit("text_delta", {"content": f"  Added: **{action.title}** ({category})\n"})
                    results.append(resp["todo"])
                else:
                    self.event_bus.emit("text_delta", {"content": f"  Error: {resp['error']}\n"})

            elif action.action == "remove":
                if action.todo_id is None:
                    continue
                resp = self.tools.execute("remove_job_todo", {
                    "job_id": job["id"],
                    "todo_id": action.todo_id,
                })
                if "error" not in resp:
                    self.event_bus.emit("text_delta", {"content": f"  Removed: **{resp['deleted']['title']}**\n"})
                    results.append(resp["deleted"])
                else:
                    self.event_bus.emit("text_delta", {"content": f"  Error: {resp['error']}\n"})

        return results

    def run(self) -> WorkflowResult:
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")

        # 1. Resolve the target job
        job = self._resolve_job(user_message, conversation_context)
        if job is None:
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "Could not resolve target job"},
                summary="Could not determine which job to manage todos for.",
            )

        job_label = f"{job['title']} at {job['company']}"
        self.event_bus.emit("text_delta", {"content": f"Managing todos for **{job_label}**...\n"})

        # 2. Fetch current todos
        todos_response = self.tools.execute("list_job_todos", {"job_id": job["id"]})
        current_todos = todos_response.get("todos", []) if "error" not in todos_response else []

        # 3. Classify intent
        intent = self._classify_intent(user_message, job, current_todos)

        logger.info(
            "ApplicationTodosWorkflow: job=%d intent=%s current_todos=%d",
            job["id"], intent, len(current_todos),
        )

        # 4. Execute based on intent
        if intent == "generate":
            added = self._generate_todos(job, current_todos)
            summary = f"Generated {len(added)} application step(s) for {job_label}."
            data = {"job": job, "added_todos": added, "intent": intent}

        elif intent == "list":
            if current_todos:
                self.event_bus.emit("text_delta", {"content": f"\nCurrent todos for **{job_label}**:\n"})
                for t in current_todos:
                    check = "x" if t["completed"] else " "
                    self.event_bus.emit("text_delta", {"content": f"  [{check}] {t['title']} ({t['category']})\n"})
            else:
                self.event_bus.emit("text_delta", {"content": f"No todos yet for **{job_label}**.\n"})
            summary = f"Listed {len(current_todos)} todo(s) for {job_label}."
            data = {"job": job, "todos": current_todos, "intent": intent}

        else:
            # toggle, add, remove
            results = self._execute_actions(job, user_message, current_todos)
            summary = f"Performed {len(results)} todo action(s) for {job_label}."
            data = {"job": job, "action_results": results, "intent": intent}

        # 5. Fetch final state and include in data
        final_todos = self.tools.execute("list_job_todos", {"job_id": job["id"]})
        if "error" not in final_todos:
            data["final_todos"] = final_todos.get("todos", [])

        self.event_bus.emit("text_delta", {"content": f"\n{summary}\n"})

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=True,
            data=data,
            summary=summary,
        )
