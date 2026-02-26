"""LangChain-based agent classes that replace the custom Agent,
OnboardingAgent, and ResumeParsingAgent.

These classes use LangChain BaseChatModel.stream() / .invoke() to
interact with LLMs while yielding the exact same SSE event dicts
that the Flask routes expect. The agent loop, tool execution, and
message history management remain custom (not AgentExecutor) to
give full control over SSE events.
"""

import json
import logging
import queue
import re
import threading
import uuid

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from backend.agent.tools import AgentTools
from backend.agent.user_profile import read_profile, set_onboarded
from backend.resume_parser import get_saved_resume, save_parsed_resume

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts (carried over from agent.py)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful job search assistant. You help users find, research, and track job applications.

You have access to tools that let you:
- Search dedicated job board APIs (Adzuna, JSearch) for real job listings
- Search the web for general information, company research, etc.
- Scrape job posting URLs to extract details
- Add jobs to the user's tracker
- List and search jobs already being tracked (filter by status, company, title, or URL)
- Read and update a persistent user profile document

## User Profile

You maintain a user profile document that stores information about the user relevant to their job search. This profile persists across conversations.

**Reading the profile:** The current profile is provided below. You can also use the `read_user_profile` tool to get the latest version at any time (e.g., after you've updated it).

**Updating the profile:** When the user shares information about themselves — education, work experience, skills, fields of interest, salary preferences, location preferences, remote work preferences, career goals, or any other job-search-relevant details — you MUST update the profile using the `update_user_profile` tool. Always read the current profile first, merge in the new information, and write back the complete updated document. Never discard existing information unless the user explicitly corrects it.

**Referencing the profile:** When evaluating whether a job is a good fit for the user, always consider the user's profile. Compare the job's requirements, location, salary, remote policy, and other attributes against the user's preferences and qualifications. Proactively mention how well a job matches (or doesn't match) the user's profile.

**Proactive extraction:** Pay close attention to what the user says in conversation. Even if the user isn't explicitly updating their profile, extract relevant information. For example:
- "I have 5 years of Python experience" → update Skills & Expertise
- "I'm looking for remote roles in the $120k-$150k range" → update Salary Preferences and Remote Work Preferences
- "I just graduated with a CS degree from MIT" → update Education
- "I used to work at Google as a senior engineer" → update Work Experience

### Current User Profile
{user_profile}

### Resume

The user may have uploaded a resume (PDF or DOCX). Use the `read_resume` tool to access the full parsed text when you need detailed information about the user's qualifications, work history, or skills — especially when evaluating job fit or helping with application preparation.

Resume status: {resume_status}

## Job Search Behavior

**When the user asks you to find or search for jobs**, use the `run_job_search` tool. This launches a specialized search sub-agent that will:
- Search multiple job boards with varied queries
- Evaluate each job against the user's profile
- Add qualifying results (rated ≥3/5 stars) to a visual results panel

After `run_job_search` completes, use `list_search_results` to review all found jobs, then highlight up to 5 of the best matches to the user with brief commentary on why each is a good fit.

**When the user shares a specific job URL** (not a general search), scrape it directly with `scrape_url`, evaluate the details, and offer to add it to the tracker with `create_job`.

Before adding a job directly to the tracker, check if it's already tracked by searching for the company name or URL to avoid duplicates.

When adding a job, always set the `job_fit` field (0-5) based on how well the job matches the user's profile. 5 = excellent fit, 0 = poor fit. Consider requirements match, salary alignment, location/remote preferences, and career goals.

Be concise and helpful. After adding jobs, confirm what was added and note how well the job matches the user's profile."""


ONBOARDING_SYSTEM_PROMPT = """You are a friendly onboarding assistant for a job search application. Your goal is to learn about the user so the app can help them find the best jobs.

You have access to tools to read and update the user's profile document. The current profile is shown below.

### Current User Profile
{user_profile}

## First Message (when conversation history is empty)

If there are no prior messages in the conversation, check whether the user's profile above already contains real (non-placeholder) information.

### Brand-new user (profile is all placeholder / default content)
Start with an introductory message that:
1. Welcomes the user to the app.
2. Briefly explains the onboarding process: "I'll ask you a series of questions about your background, skills, and job preferences. This usually takes just a few minutes. Your answers will help me find jobs that are the best fit for you."
3. Encourages the user to give detailed, full-sentence answers. Frame it positively — something like: "Think of this like talking to a career consultant. The more detail you share, the better I can match you with relevant jobs. For example, instead of just 'Python', you might say 'I have 5 years of professional Python experience building web APIs and data pipelines.'"
4. Ends with your first question — ask about their current role or professional background (e.g. "To start, could you tell me about your current or most recent job title and what you do?").

### Returning user (profile already has some real content)
The user started onboarding before but didn't finish. In this case:
1. Welcome them back briefly (e.g. "Welcome back! I see we got started on your profile last time.").
2. Briefly summarize what you already know about them based on the profile content.
3. Skip any sections that already have real content — do NOT re-ask those questions.
4. Ask about the NEXT missing section that still has placeholder content (e.g. "_Not yet provided_").
5. Do NOT repeat the full onboarding explanation or encourage detailed answers again — get straight to the next question.

## Ongoing Conversation

After the first message, follow this process:

1. **Ask about ONE topic at a time.** Pick the most important missing piece of information and ask about it. Topics include:
   - Current job title / role and years of experience
   - Work experience (companies, roles, durations, highlights)
   - Education (degrees, institutions, fields of study)
   - Technical and professional skills & expertise
   - Fields / industries of interest
   - Salary range preferences
   - Location preferences (city, state, willing to relocate?)
   - Remote work preferences (remote, hybrid, onsite)
   - Job search goals (what kind of role are you looking for? what matters most?)
   - Anything else relevant (visa status, availability, etc.)
2. **After each answer**, use the `update_user_profile` tool to save the information. Condense and summarize verbose answers into concise bullet points. Always read the current profile first (it's in the system prompt, or use `read_user_profile`), merge the new info, and write back the full document.
3. **Ask relevant follow-up questions** if the answer is vague or there's a natural follow-up. For example, if they say "I'm a software engineer", ask about specific technologies, seniority level, etc.
4. **When all sections are filled**, ask: "Is there anything else you'd like me to know about your job search?" Process their answer if they have one.
5. **When done**, thank the user and let them know their profile is saved. End your final message with the exact marker `[ONBOARDING_COMPLETE]` (this signals the system to mark onboarding as done — the user will not see this marker).

## Guidelines
- Be conversational and encouraging, not robotic.
- Ask only 1-2 questions per message to avoid overwhelming the user.
- Keep your messages concise.
- Always update the profile after receiving information — don't wait until the end.
- Write a brief Summary section once you have enough context.
- Do NOT ask about topics that already have real (non-placeholder) content in the profile."""


RESUME_PARSING_SYSTEM_PROMPT = """You are a resume parsing specialist. Your job is to take raw text extracted from a PDF or DOCX resume and produce clean, structured JSON.

The raw text often has formatting artifacts from PDF extraction: weird spacing, broken lines, garbled characters, merged words, misplaced headers, duplicated content, etc. You must intelligently clean and restructure this content.

## Output Format

Return ONLY valid JSON (no markdown fences, no explanation) with this structure:

{
  "contact_info": {
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1-555-123-4567",
    "location": "City, State",
    "linkedin": "linkedin.com/in/...",
    "github": "github.com/...",
    "website": "..."
  },
  "summary": "A brief professional summary or objective if present in the resume.",
  "work_experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "location": "City, State",
      "start_date": "Jan 2020",
      "end_date": "Present",
      "highlights": [
        "Key accomplishment or responsibility",
        "Another highlight"
      ]
    }
  ],
  "education": [
    {
      "institution": "University Name",
      "degree": "Bachelor of Science in Computer Science",
      "location": "City, State",
      "start_date": "2016",
      "end_date": "2020",
      "details": ["GPA: 3.8", "Honors: Magna Cum Laude"]
    }
  ],
  "skills": {
    "languages": ["Python", "JavaScript"],
    "frameworks": ["React", "Flask"],
    "tools": ["Docker", "Git"],
    "other": ["Project Management", "Agile"]
  },
  "certifications": [
    {
      "name": "AWS Solutions Architect",
      "issuer": "Amazon Web Services",
      "date": "2023"
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "description": "Brief description",
      "technologies": ["Tech1", "Tech2"],
      "url": "..."
    }
  ],
  "publications": [
    {
      "title": "Paper Title",
      "venue": "Conference/Journal",
      "date": "2023",
      "url": "..."
    }
  ],
  "awards": [
    {
      "name": "Award Name",
      "issuer": "Organization",
      "date": "2023"
    }
  ],
  "languages": [
    {
      "language": "English",
      "proficiency": "Native"
    }
  ],
  "volunteer": [
    {
      "organization": "Org Name",
      "role": "Volunteer Role",
      "start_date": "2020",
      "end_date": "2021",
      "description": "..."
    }
  ]
}

## Rules

1. Only include sections that have data in the resume. Omit empty sections entirely (don't include empty arrays).
2. For skills, group them logically. If the resume doesn't categorize them, do your best to sort them into languages, frameworks, tools, and other.
3. Fix obvious OCR/extraction errors: merged words ("PythonDeveloper" → "Python Developer"), garbled characters, broken lines that should be joined.
4. Normalize dates to a consistent format (e.g., "Jan 2020", "2020", "Jan 2020 - Present").
5. Preserve all meaningful content — don't drop information, just restructure it.
6. If something is ambiguous, make your best judgment rather than omitting it.
7. Return ONLY the JSON object. No preamble, no explanation, no markdown code fences."""


# ---------------------------------------------------------------------------
# Tool-call chunk accumulation helpers
# ---------------------------------------------------------------------------

class _ToolCallAccumulator:
    """Accumulates partial tool_call_chunks from LangChain streaming into
    complete tool calls with parsed arguments."""

    __slots__ = ("id", "name", "args_parts")

    def __init__(self):
        self.id: str | None = None
        self.name: str = ""
        self.args_parts: list[str] = []


def _accumulate_tool_call_chunk(accumulated: list[_ToolCallAccumulator], chunk) -> None:
    """Merge an incremental ``tool_call_chunk`` into *accumulated*.

    LangChain streams tool calls as partial chunks with:
      - index: which tool call this chunk belongs to
      - id:    tool-call ID (may be ``None`` after the first chunk)
      - name:  tool name   (may be ``None`` after the first chunk)
      - args:  partial JSON string for arguments
    """
    idx = chunk.get("index") if isinstance(chunk, dict) else getattr(chunk, "index", None)
    # If index is None, assume a single tool call (index 0)
    if idx is None:
        idx = 0

    # Extend the list if needed
    while len(accumulated) <= idx:
        accumulated.append(_ToolCallAccumulator())

    acc = accumulated[idx]

    tc_id = chunk.get("id") if isinstance(chunk, dict) else getattr(chunk, "id", None)
    tc_name = chunk.get("name") if isinstance(chunk, dict) else getattr(chunk, "name", None)
    tc_args = chunk.get("args") if isinstance(chunk, dict) else getattr(chunk, "args", None)

    if tc_id:
        acc.id = tc_id
    if tc_name:
        acc.name += tc_name
    if tc_args:
        acc.args_parts.append(tc_args)


class _FinalToolCall:
    """A fully-accumulated tool call with parsed arguments."""
    __slots__ = ("id", "name", "args")

    def __init__(self, id: str, name: str, args: dict):
        self.id = id
        self.name = name
        self.args = args


def _finalize_tool_calls(accumulated: list[_ToolCallAccumulator]) -> list[_FinalToolCall]:
    """Parse accumulated JSON arg strings into dicts and generate
    fallback UUIDs for tool-call IDs when missing."""
    results = []
    for acc in accumulated:
        if not acc.name:
            continue
        tc_id = acc.id or str(uuid.uuid4())
        args_str = "".join(acc.args_parts)
        try:
            args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError:
            logger.warning("Failed to parse tool-call args for %s: %s", acc.name, args_str)
            args = {}
        results.append(_FinalToolCall(id=tc_id, name=acc.name, args=args))
    return results


# ---------------------------------------------------------------------------
# Streaming text extraction helper
# ---------------------------------------------------------------------------

def _extract_text_from_chunk(chunk) -> str:
    """Extract text from an AIMessageChunk's ``.content``.

    ``chunk.content`` may be a plain ``str`` (OpenAI, Ollama) or a
    ``list`` of content blocks (Anthropic).  This normalises both
    cases into a single string.
    """
    content = chunk.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # Anthropic text block: {"type": "text", "text": "..."}
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


# ---------------------------------------------------------------------------
# Message conversion helper
# ---------------------------------------------------------------------------

def _convert_messages(messages: list[dict]) -> list:
    """Convert DB-style message dicts to LangChain message objects.

    Only handles "user" and "assistant" roles (system is prepended
    separately). Messages with complex content blocks (from previous
    tool-call turns persisted by old code) are simplified to plain text.
    """
    lc_messages = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        # For content that is a list (Anthropic-style blocks persisted by old agent),
        # extract only the textual content.
        if isinstance(content, list):
            text_pieces = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_pieces.append(block.get("text", ""))
                    # Skip tool_use / tool_result blocks in persisted messages
                elif isinstance(block, str):
                    text_pieces.append(block)
            content = "\n".join(text_pieces)
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
    return lc_messages


# ---------------------------------------------------------------------------
# LangChainAgent — main chat agent
# ---------------------------------------------------------------------------

MAX_ITERATIONS = 25


class LangChainAgent:
    """Main agent that uses LangChain models with tool calling.

    Drop-in replacement for the old ``Agent`` class — yields identical
    SSE event dicts from ``run()``.
    """

    def __init__(
        self,
        model: BaseChatModel,
        search_api_key: str = "",
        adzuna_app_id: str = "",
        adzuna_app_key: str = "",
        adzuna_country: str = "us",
        jsearch_api_key: str = "",
        conversation_id: int | None = None,
        search_model: BaseChatModel | None = None,
    ):
        # Thread-safe queue for real-time SSE events from sub-agents
        self._event_queue: queue.Queue[dict] = queue.Queue()

        def _event_callback(event):
            self._event_queue.put(event)

        self.agent_tools = AgentTools(
            search_api_key=search_api_key,
            adzuna_app_id=adzuna_app_id,
            adzuna_app_key=adzuna_app_key,
            adzuna_country=adzuna_country,
            jsearch_api_key=jsearch_api_key,
            conversation_id=conversation_id,
            event_callback=_event_callback,
            search_model=search_model,
        )
        self.lc_tools = self.agent_tools.to_langchain_tools()
        self.model_with_tools = model.bind_tools(self.lc_tools)

    def run(self, messages):
        """Run the agent loop, yielding SSE event dicts.

        Yields dicts with 'event' and 'data' keys:
            - text_delta: {"content": "..."}
            - tool_start: {"id": "...", "name": "...", "arguments": {...}}
            - tool_result: {"id": "...", "name": "...", "result": {...}}
            - tool_error: {"id": "...", "name": "...", "error": "..."}
            - done: {"content": "full accumulated text"}
            - error: {"message": "..."}
        """
        # Build system prompt with current user profile + resume status
        user_profile = read_profile()
        resume_info = get_saved_resume()
        resume_status = (
            f"Uploaded — {resume_info['filename']}" if resume_info else "No resume uploaded"
        )
        system_prompt = SYSTEM_PROMPT.format(
            user_profile=user_profile, resume_status=resume_status
        )

        # Convert DB messages to LangChain types
        lc_messages = [SystemMessage(content=system_prompt)]
        lc_messages.extend(_convert_messages(messages))

        full_text = ""

        logger.info(
            "LangChainAgent run started — %d messages in history", len(messages)
        )

        for iteration in range(MAX_ITERATIONS):
            logger.info(
                "Agent iteration %d/%d (messages: %d)",
                iteration + 1,
                MAX_ITERATIONS,
                len(lc_messages),
            )
            text_accum = ""
            accumulated_tool_calls: list[_ToolCallAccumulator] = []
            iteration_started = False

            try:
                for chunk in self.model_with_tools.stream(lc_messages):
                    # --- text ---
                    text = _extract_text_from_chunk(chunk)
                    if text:
                        # Separator between iterations (matches old behaviour)
                        if not iteration_started and full_text:
                            separator = "\n\n"
                            text_accum += separator
                            full_text += separator
                            yield {"event": "text_delta", "data": {"content": separator}}
                        iteration_started = True
                        text_accum += text
                        full_text += text
                        yield {"event": "text_delta", "data": {"content": text}}

                    # --- tool-call chunks ---
                    tc_chunks = getattr(chunk, "tool_call_chunks", None) or []
                    for tc_chunk in tc_chunks:
                        _accumulate_tool_call_chunk(accumulated_tool_calls, tc_chunk)

            except Exception as e:
                logger.error("LLM stream error: %s", e)
                yield {"event": "error", "data": {"message": str(e)}}
                return

            # Finalize tool calls
            final_tool_calls = _finalize_tool_calls(accumulated_tool_calls)

            if not final_tool_calls:
                logger.info(
                    "Agent done — %d iterations, %d chars of text",
                    iteration + 1,
                    len(full_text),
                )
                yield {"event": "done", "data": {"content": full_text}}
                return

            # Build AIMessage with tool_calls for history
            ai_message = AIMessage(
                content=text_accum,
                tool_calls=[
                    {"id": tc.id, "name": tc.name, "args": tc.args}
                    for tc in final_tool_calls
                ],
            )
            lc_messages.append(ai_message)

            # Execute tools
            for tc in final_tool_calls:
                logger.info(
                    "Tool call: %s — args: %s",
                    tc.name,
                    json.dumps(tc.args, default=str),
                )
                yield {
                    "event": "tool_start",
                    "data": {"id": tc.id, "name": tc.name, "arguments": tc.args},
                }

                # Drain any stale events
                while not self._event_queue.empty():
                    try:
                        self._event_queue.get_nowait()
                    except queue.Empty:
                        break

                # Run tool in a thread so sub-agent events stream in real-time
                result_holder: list = []
                error_holder: list = []

                # Capture Flask app context for the thread
                from flask import current_app
                app = current_app._get_current_object()

                def _run_tool():
                    with app.app_context():
                        try:
                            result_holder.append(self.agent_tools.execute(tc.name, tc.args))
                        except Exception as exc:
                            error_holder.append(exc)
                        finally:
                            # Sentinel to signal completion
                            self._event_queue.put(None)

                thread = threading.Thread(target=_run_tool, daemon=True)
                thread.start()

                # Yield sub-agent events in real-time while tool runs
                while True:
                    try:
                        pending = self._event_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if pending is None:
                        break
                    yield pending

                thread.join()

                if error_holder:
                    raise error_holder[0]
                result = result_holder[0]

                if isinstance(result, dict) and "error" in result:
                    logger.warning("Tool error: %s — %s", tc.name, result["error"])
                    yield {
                        "event": "tool_error",
                        "data": {
                            "id": tc.id,
                            "name": tc.name,
                            "error": result["error"],
                        },
                    }
                else:
                    result_json = json.dumps(result, default=str)
                    logger.info("Tool result: %s — %d chars", tc.name, len(result_json))
                    logger.debug("Tool result full: %s — %s", tc.name, result_json)
                    yield {
                        "event": "tool_result",
                        "data": {"id": tc.id, "name": tc.name, "result": result},
                    }

                # Append ToolMessage to history
                lc_messages.append(
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=tc.id,
                    )
                )

        logger.warning("Agent hit max iterations (%d)", MAX_ITERATIONS)
        yield {"event": "error", "data": {"message": "Max iterations reached"}}


# ---------------------------------------------------------------------------
# LangChainOnboardingAgent — onboarding interview
# ---------------------------------------------------------------------------

# Only profile-related tools for onboarding
ONBOARDING_TOOL_NAMES = {"read_user_profile", "update_user_profile"}

ONBOARDING_MAX_ITERATIONS = 6


class LangChainOnboardingAgent:
    """Agent that runs the onboarding interview to populate the user profile.

    Drop-in replacement for the old ``OnboardingAgent`` class.
    """

    def __init__(self, model: BaseChatModel):
        self.agent_tools = AgentTools(search_api_key="")
        lc_tools = self.agent_tools.to_langchain_tools()
        # Filter to onboarding-only tools
        self.lc_tools = [t for t in lc_tools if t.name in ONBOARDING_TOOL_NAMES]
        self.model_with_tools = model.bind_tools(self.lc_tools)

    def run(self, messages):
        """Same streaming interface as LangChainAgent.run()."""
        user_profile = read_profile()
        system_prompt = ONBOARDING_SYSTEM_PROMPT.format(user_profile=user_profile)

        lc_messages = [SystemMessage(content=system_prompt)]
        lc_messages.extend(_convert_messages(messages))

        full_text = ""

        logger.info(
            "LangChainOnboardingAgent run started — %d messages in history",
            len(messages),
        )

        for iteration in range(ONBOARDING_MAX_ITERATIONS):
            logger.info(
                "Onboarding iteration %d/%d",
                iteration + 1,
                ONBOARDING_MAX_ITERATIONS,
            )
            text_accum = ""
            accumulated_tool_calls: list[_ToolCallAccumulator] = []
            iteration_started = False

            try:
                for chunk in self.model_with_tools.stream(lc_messages):
                    text = _extract_text_from_chunk(chunk)
                    if text:
                        if not iteration_started and full_text:
                            separator = "\n\n"
                            text_accum += separator
                            full_text += separator
                            yield {"event": "text_delta", "data": {"content": separator}}
                        iteration_started = True
                        text_accum += text
                        full_text += text
                        yield {"event": "text_delta", "data": {"content": text}}

                    tc_chunks = getattr(chunk, "tool_call_chunks", None) or []
                    for tc_chunk in tc_chunks:
                        _accumulate_tool_call_chunk(accumulated_tool_calls, tc_chunk)

            except Exception as e:
                logger.error("Onboarding LLM stream error: %s", e)
                yield {"event": "error", "data": {"message": str(e)}}
                return

            final_tool_calls = _finalize_tool_calls(accumulated_tool_calls)

            if not final_tool_calls:
                # Check if onboarding is complete
                if "[ONBOARDING_COMPLETE]" in full_text:
                    logger.info("Onboarding complete — marking user as onboarded")
                    set_onboarded(True)
                    clean_text = full_text.replace("[ONBOARDING_COMPLETE]", "").rstrip()
                    yield {"event": "onboarding_complete", "data": {}}
                    yield {"event": "done", "data": {"content": clean_text}}
                else:
                    yield {"event": "done", "data": {"content": full_text}}
                return

            # Build AIMessage with tool_calls for history
            ai_message = AIMessage(
                content=text_accum,
                tool_calls=[
                    {"id": tc.id, "name": tc.name, "args": tc.args}
                    for tc in final_tool_calls
                ],
            )
            lc_messages.append(ai_message)

            # Execute tools
            for tc in final_tool_calls:
                logger.info(
                    "Onboarding tool call: %s — args: %s",
                    tc.name,
                    json.dumps(tc.args, default=str),
                )
                yield {
                    "event": "tool_start",
                    "data": {"id": tc.id, "name": tc.name, "arguments": tc.args},
                }

                result = self.agent_tools.execute(tc.name, tc.args)

                if isinstance(result, dict) and "error" in result:
                    yield {
                        "event": "tool_error",
                        "data": {
                            "id": tc.id,
                            "name": tc.name,
                            "error": result["error"],
                        },
                    }
                else:
                    yield {
                        "event": "tool_result",
                        "data": {"id": tc.id, "name": tc.name, "result": result},
                    }

                lc_messages.append(
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=tc.id,
                    )
                )

            # Re-read profile for next iteration (it may have been updated)
            user_profile = read_profile()
            system_prompt = ONBOARDING_SYSTEM_PROMPT.format(user_profile=user_profile)
            # Update the system message in-place
            lc_messages[0] = SystemMessage(content=system_prompt)

        yield {"event": "done", "data": {"content": full_text}}


# ---------------------------------------------------------------------------
# LangChainResumeParser — non-streaming resume parsing
# ---------------------------------------------------------------------------


class LangChainResumeParser:
    """Uses an LLM to clean up and structure raw resume text into JSON.

    Drop-in replacement for the old ``ResumeParsingAgent`` class.
    """

    def __init__(self, model: BaseChatModel):
        self.model = model

    def parse(self, raw_text: str) -> dict:
        """Parse raw resume text into structured JSON.

        Args:
            raw_text: The raw text extracted from a PDF/DOCX resume.

        Returns:
            Structured resume data as a dictionary.

        Raises:
            RuntimeError: If the LLM fails to produce valid JSON.
        """
        lc_messages = [
            SystemMessage(content=RESUME_PARSING_SYSTEM_PROMPT),
            HumanMessage(
                content=f"Parse the following raw resume text into structured JSON:\n\n{raw_text}"
            ),
        ]

        logger.info(
            "LangChainResumeParser: starting parse (%d chars of raw text)",
            len(raw_text),
        )

        try:
            response = self.model.invoke(lc_messages)
        except Exception as e:
            logger.error("LLM error during resume parsing: %s", e)
            raise RuntimeError(f"LLM error: {e}") from e

        full_text = response.content if isinstance(response.content, str) else str(response.content)
        logger.info(
            "LangChainResumeParser: received %d chars of response", len(full_text)
        )

        parsed = _extract_json(full_text)
        if parsed is None:
            logger.error(
                "LangChainResumeParser: failed to parse JSON from LLM response"
            )
            raise RuntimeError("LLM did not return valid JSON. Please try again.")

        save_parsed_resume(parsed)
        logger.info(
            "LangChainResumeParser: successfully parsed and saved structured resume"
        )
        return parsed


# ---------------------------------------------------------------------------
# JSON extraction helper (shared with ResumeParser)
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from LLM output, handling markdown fences."""
    text = text.strip()

    # Try to find JSON in markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find the first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    return None
