"""Interview Prep workflow — generate tailored interview preparation.

Pipeline:
1. A ``JobResolver`` identifies which tracked job to prepare for.
2. The user's resume, profile, and the job's details are loaded.
3. A planning step analyses the job posting, the user's profile, and
   their resume to identify the key themes, likely focus areas, and
   notable gaps that the downstream sub-modules should address.
4. Five specialist sub-modules run **in parallel**, each generating one
   category of interview preparation material:

   a. **Company & Role Research Brief** — key facts about the company
      (mission, culture, recent news/developments, competitive
      landscape) and how the role fits into the organisation.  Gives
      the candidate concrete talking points that demonstrate research.
   b. **Behavioural Questions & STAR Answers** — likely behavioural /
      competency-based questions derived from the job's stated values,
      responsibilities, and team context, paired with STAR-format
      answer frameworks drawn from the candidate's *actual* experience
      in their resume and profile.
   c. **Technical & Domain Questions** — technical or domain-specific
      questions inferred from the job requirements, tech stack, and
      role level.  Each question includes preparation notes: key
      concepts to review, relevant projects from the candidate's
      background, and suggested talking points.
   d. **Weakness & Gap Mitigation** — honest assessment of areas where
      the candidate's profile does not fully match the stated
      requirements, with concrete strategies for addressing each gap
      confidently (transferable skills, learning trajectory, adjacent
      experience, etc.).
   e. **Questions for the Interviewer** — thoughtful, role-aware
      questions the candidate should consider asking, organised by
      audience (hiring manager, peer, skip-level).  Each question
      includes a brief note on *why* it's valuable to ask and what
      signal to look for in the answer.

5. An assembly step merges the five outputs into a single, well-
   organised prep guide, resolves any cross-section redundancy, and
   adds a concise "day-of" checklist at the top.
"""

from __future__ import annotations

import concurrent.futures
import logging

import dspy
from pydantic import BaseModel, Field

from backend.llm.llm_factory import LLMConfig

from ._dspy_utils import build_dspy_tools, build_lm, load_job_context, load_user_context
from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DSPy signatures
# ---------------------------------------------------------------------------


class InterviewPlanFocusArea(BaseModel):
    """A focus area identified during the planning step."""

    area: str = Field(description="Short label for this focus area")
    reasoning: str = Field(
        description="Why this area is important for this interview"
    )


class AnalyseInterviewSig(dspy.Signature):
    """Analyse a job posting, user profile, and resume to plan interview prep.

    Identify the key themes the interview is likely to cover, areas where
    the candidate is strong, and gaps where additional preparation will be
    most valuable.  This analysis feeds the downstream specialist modules.
    """

    user_message: str = dspy.InputField(
        desc="The user's original request/context"
    )
    job_context: str = dspy.InputField(desc="Target job details")
    user_context: str = dspy.InputField(desc="User profile and resume context")

    key_themes: list[str] = dspy.OutputField(
        desc="3-6 key themes this interview is likely to focus on"
    )
    candidate_strengths: list[str] = dspy.OutputField(
        desc="Top strengths from the candidate's background that align with this role"
    )
    focus_areas: list[InterviewPlanFocusArea] = dspy.OutputField(
        desc="Areas that need preparation, ordered by importance"
    )
    gap_notes: list[str] = dspy.OutputField(
        desc="Notable gaps between the candidate's profile and the job requirements"
    )


class CompanyBriefSig(dspy.Signature):
    """Research a company and produce an interview-prep brief.

    You have access to web_search and scrape_url tools.  Use them to find
    current, accurate information about the company — do NOT rely solely on
    your training data.

    Steps:
    1. Search for the company name + recent news, mission, culture, and
       competitive landscape.
    2. If a company website or relevant article is found, scrape it for
       details.
    3. Synthesise your findings into a concise brief with concrete talking
       points the candidate can use in their interview.

    Focus on information that would be impressive and relevant in an
    interview setting.  Cite specific facts rather than generic praise.
    """

    job_context: str = dspy.InputField(desc="Target job details")
    key_themes: str = dspy.InputField(
        desc="Key interview themes from the planning step"
    )

    company_overview: str = dspy.OutputField(
        desc="2-3 paragraph overview: mission, culture, recent developments, competitive landscape"
    )
    role_context: str = dspy.OutputField(
        desc="How this role fits into the organisation and team"
    )
    talking_points: list[str] = dspy.OutputField(
        desc="5-8 concrete talking points that demonstrate research"
    )


class BehaviouralQuestion(BaseModel):
    """One behavioural interview question with a STAR answer framework."""

    question: str = Field(description="The likely behavioural question")
    why_asked: str = Field(
        description="Why the interviewer would ask this for this role"
    )
    star_situation: str = Field(
        description="Suggested Situation from the candidate's experience"
    )
    star_task: str = Field(description="The Task the candidate faced")
    star_action: str = Field(description="The Action the candidate took")
    star_result: str = Field(description="The Result and impact achieved")


class BehaviouralQuestionsSig(dspy.Signature):
    """Generate behavioural interview questions with STAR answer frameworks.

    Questions should be derived from the job's stated values,
    responsibilities, and team context.  STAR answers must be drawn from
    the candidate's *actual* experience in their resume and profile — do
    NOT invent accomplishments.
    """

    job_context: str = dspy.InputField(desc="Target job details")
    user_context: str = dspy.InputField(desc="User profile and resume context")
    key_themes: str = dspy.InputField(
        desc="Key interview themes from the planning step"
    )
    candidate_strengths: str = dspy.InputField(
        desc="Candidate strengths identified in the planning step"
    )

    questions: list[BehaviouralQuestion] = dspy.OutputField(
        desc="5-7 likely behavioural questions with STAR answer frameworks"
    )


class TechnicalQuestion(BaseModel):
    """One technical or domain-specific question with preparation notes."""

    question: str = Field(description="The technical/domain question")
    difficulty: str = Field(description="One of 'foundational', 'intermediate', 'advanced'")
    key_concepts: list[str] = Field(
        description="Key concepts to review before answering"
    )
    relevant_experience: str = Field(
        description="Relevant project or experience from the candidate's background"
    )
    talking_points: list[str] = Field(
        description="Suggested talking points for a strong answer"
    )


class TechnicalQuestionsSig(dspy.Signature):
    """Generate technical and domain-specific interview questions.

    Infer questions from the job requirements, tech stack, and role level.
    For each question, provide preparation notes and connect to the
    candidate's background where possible.
    """

    job_context: str = dspy.InputField(desc="Target job details and requirements")
    user_context: str = dspy.InputField(desc="User profile and resume context")
    key_themes: str = dspy.InputField(
        desc="Key interview themes from the planning step"
    )

    questions: list[TechnicalQuestion] = dspy.OutputField(
        desc="5-8 technical/domain questions spanning foundational to advanced"
    )


class GapStrategy(BaseModel):
    """Strategy for addressing one gap between the candidate and the role."""

    gap: str = Field(description="The gap or weakness being addressed")
    severity: str = Field(description="One of 'minor', 'moderate', 'significant'")
    strategy: str = Field(
        description="How to address this gap confidently in an interview"
    )
    transferable_skills: list[str] = Field(
        description="Transferable skills or adjacent experience that bridge this gap"
    )
    example_framing: str = Field(
        description="Example sentence showing how to frame this positively"
    )


class WeaknessGapSig(dspy.Signature):
    """Assess gaps between the candidate's profile and job requirements.

    Provide honest, actionable strategies for addressing each gap
    confidently in an interview.  Focus on transferable skills, learning
    trajectory, and adjacent experience — not on hiding weaknesses.
    """

    job_context: str = dspy.InputField(desc="Target job details and requirements")
    user_context: str = dspy.InputField(desc="User profile and resume context")
    gap_notes: str = dspy.InputField(
        desc="Gap notes from the planning step"
    )

    strategies: list[GapStrategy] = dspy.OutputField(
        desc="Strategies for each identified gap, ordered by severity"
    )
    overall_narrative: str = dspy.OutputField(
        desc="1-2 sentence overarching narrative for positioning any gaps positively"
    )


class InterviewerQuestion(BaseModel):
    """A question the candidate should consider asking the interviewer."""

    question: str = Field(description="The question to ask")
    audience: str = Field(
        description="Best audience: 'hiring_manager', 'peer', or 'skip_level'"
    )
    why_valuable: str = Field(
        description="Why this question is valuable to ask"
    )
    signal_to_watch: str = Field(
        description="What signal to look for in the interviewer's answer"
    )


class QuestionsForInterviewerSig(dspy.Signature):
    """Generate thoughtful questions the candidate should ask the interviewer.

    Questions should be role-aware, organised by audience, and demonstrate
    genuine interest and strategic thinking about the role and company.
    """

    job_context: str = dspy.InputField(desc="Target job details")
    user_context: str = dspy.InputField(desc="User profile and resume context")
    key_themes: str = dspy.InputField(
        desc="Key interview themes from the planning step"
    )

    questions: list[InterviewerQuestion] = dspy.OutputField(
        desc="6-10 questions organised by audience type"
    )


class AssemblePrepGuideSig(dspy.Signature):
    """Assemble interview prep sections into a unified, well-organised guide.

    Merge the five specialist outputs into a single document.  Resolve
    cross-section redundancy, ensure consistent tone, and add a concise
    "day-of checklist" at the top that distils the most important
    actionable items.
    """

    job_label: str = dspy.InputField(desc="Job title at company")
    company_brief: str = dspy.InputField(
        desc="Company and role research brief section"
    )
    behavioural_section: str = dspy.InputField(
        desc="Behavioural questions and STAR answers section"
    )
    technical_section: str = dspy.InputField(
        desc="Technical and domain questions section"
    )
    gaps_section: str = dspy.InputField(
        desc="Weakness and gap mitigation section"
    )
    interviewer_questions_section: str = dspy.InputField(
        desc="Questions for the interviewer section"
    )

    day_of_checklist: list[str] = dspy.OutputField(
        desc="5-8 concise, actionable checklist items for interview day"
    )
    assembled_guide: str = dspy.OutputField(
        desc="The full assembled interview prep guide in well-formatted markdown"
    )


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@register_workflow("prep_interview")
class PrepInterviewWorkflow(BaseWorkflow):
    """Generate interview preparation materials for a specific job."""

    OUTPUTS = {
        "job": "dict — the target job record",
        "key_themes": "list[str] — main interview themes identified",
        "candidate_strengths": "list[str] — relevant strengths from the user's profile",
        "gap_notes": "list[str] — weakness mitigation strategies",
        "checklist": "list[str] — day-of checklist items",
    }

    # -- Helpers ------------------------------------------------------------
    # Job/user context loading delegated to shared helpers in _dspy_utils.py.

    # -- Parallel sub-module runners ----------------------------------------

    # Tools exposed to the company brief ReAct module for live research.
    _COMPANY_BRIEF_TOOL_NAMES = frozenset({"web_search", "scrape_url"})

    def _run_company_brief(
        self,
        lm: dspy.LM,
        job_context: str,
        key_themes: str,
    ) -> str:
        """Research the company via web search and generate a brief."""
        research_tools = [
            t for t in build_dspy_tools(self.tools)
            if t.name in self._COMPANY_BRIEF_TOOL_NAMES
        ]
        module = dspy.ReAct(
            CompanyBriefSig,
            tools=research_tools,
            max_iters=6,
        )
        with dspy.context(lm=lm):
            result = module(
                job_context=job_context,
                key_themes=key_themes,
            )

        talking_points = (
            "\n".join(f"- {tp}" for tp in result.talking_points)
            if result.talking_points else ""
        )
        return (
            f"### Company & Role Research Brief\n\n"
            f"{result.company_overview}\n\n"
            f"**Role Context:** {result.role_context}\n\n"
            f"**Talking Points:**\n{talking_points}"
        )

    def _run_behavioural_questions(
        self,
        lm: dspy.LM,
        job_context: str,
        user_context: str,
        key_themes: str,
        candidate_strengths: str,
    ) -> str:
        """Generate behavioural questions with STAR answer frameworks."""
        module = dspy.ChainOfThought(BehaviouralQuestionsSig)
        with dspy.context(lm=lm):
            result = module(
                job_context=job_context,
                user_context=user_context,
                key_themes=key_themes,
                candidate_strengths=candidate_strengths,
            )

        questions = list(result.questions) if result.questions else []
        parts: list[str] = ["### Behavioural Questions & STAR Answers\n"]
        for i, q in enumerate(questions, start=1):
            parts.append(f"**{i}. {q.question}**")
            parts.append(f"_Why asked:_ {q.why_asked}\n")
            parts.append(f"- **Situation:** {q.star_situation}")
            parts.append(f"- **Task:** {q.star_task}")
            parts.append(f"- **Action:** {q.star_action}")
            parts.append(f"- **Result:** {q.star_result}")
            parts.append("")
        return "\n".join(parts)

    def _run_technical_questions(
        self,
        lm: dspy.LM,
        job_context: str,
        user_context: str,
        key_themes: str,
    ) -> str:
        """Generate technical and domain-specific questions."""
        module = dspy.ChainOfThought(TechnicalQuestionsSig)
        with dspy.context(lm=lm):
            result = module(
                job_context=job_context,
                user_context=user_context,
                key_themes=key_themes,
            )

        questions = list(result.questions) if result.questions else []
        parts: list[str] = ["### Technical & Domain Questions\n"]
        for i, q in enumerate(questions, start=1):
            concepts = ", ".join(q.key_concepts) if q.key_concepts else "N/A"
            talking = "\n".join(f"  - {tp}" for tp in q.talking_points) if q.talking_points else "  - N/A"
            parts.append(f"**{i}. {q.question}** _{q.difficulty}_")
            parts.append(f"- Key concepts: {concepts}")
            parts.append(f"- Relevant experience: {q.relevant_experience}")
            parts.append(f"- Talking points:\n{talking}")
            parts.append("")
        return "\n".join(parts)

    def _run_weakness_gap(
        self,
        lm: dspy.LM,
        job_context: str,
        user_context: str,
        gap_notes: str,
    ) -> str:
        """Generate weakness & gap mitigation strategies."""
        module = dspy.ChainOfThought(WeaknessGapSig)
        with dspy.context(lm=lm):
            result = module(
                job_context=job_context,
                user_context=user_context,
                gap_notes=gap_notes,
            )

        strategies = list(result.strategies) if result.strategies else []
        parts: list[str] = ["### Weakness & Gap Mitigation\n"]
        if result.overall_narrative:
            parts.append(f"_{result.overall_narrative}_\n")
        for s in strategies:
            transferable = ", ".join(s.transferable_skills) if s.transferable_skills else "N/A"
            parts.append(f"**{s.gap}** ({s.severity})")
            parts.append(f"- Strategy: {s.strategy}")
            parts.append(f"- Transferable skills: {transferable}")
            parts.append(f"- Example framing: *\"{s.example_framing}\"*")
            parts.append("")
        return "\n".join(parts)

    def _run_questions_for_interviewer(
        self,
        lm: dspy.LM,
        job_context: str,
        user_context: str,
        key_themes: str,
    ) -> str:
        """Generate questions the candidate should ask the interviewer."""
        module = dspy.ChainOfThought(QuestionsForInterviewerSig)
        with dspy.context(lm=lm):
            result = module(
                job_context=job_context,
                user_context=user_context,
                key_themes=key_themes,
            )

        questions = list(result.questions) if result.questions else []
        # Group by audience
        grouped: dict[str, list[InterviewerQuestion]] = {}
        for q in questions:
            grouped.setdefault(q.audience, []).append(q)

        audience_labels = {
            "hiring_manager": "Hiring Manager",
            "peer": "Peer / Team Member",
            "skip_level": "Skip-Level / Leadership",
        }

        parts: list[str] = ["### Questions for the Interviewer\n"]
        for audience_key, label in audience_labels.items():
            qs = grouped.get(audience_key, [])
            if not qs:
                continue
            parts.append(f"**{label}:**\n")
            for q in qs:
                parts.append(f"- **{q.question}**")
                parts.append(f"  _Why:_ {q.why_valuable}")
                parts.append(f"  _Watch for:_ {q.signal_to_watch}")
            parts.append("")

        # Catch any questions with unlisted audiences
        covered = set(audience_labels.keys())
        for audience_key, qs in grouped.items():
            if audience_key not in covered:
                parts.append(f"**{audience_key.replace('_', ' ').title()}:**\n")
                for q in qs:
                    parts.append(f"- **{q.question}**")
                    parts.append(f"  _Why:_ {q.why_valuable}")
                    parts.append(f"  _Watch for:_ {q.signal_to_watch}")
                parts.append("")

        return "\n".join(parts)

    # -- Main run -----------------------------------------------------------

    def run(self) -> WorkflowResult:
        user_message = self.outcome_description or self.params.get("user_message", "")
        conversation_context = self.params.get("conversation_context", "")

        # 1. Resolve the target job (required)
        job, job_context = load_job_context(
            self.tools, self.params, self.llm_config,
            user_message, conversation_context,
        )
        if not job:
            msg = "I need to know which job to prepare for. Please specify the job.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No job resolved"},
                summary=msg.strip(),
            )

        job_label = f"{job['title']} at {job['company']}"
        self.event_bus.emit("text_delta", {"content": f"Preparing interview guide for: **{job_label}**\n\n"})

        # 2. Load user context
        self.event_bus.emit("text_delta", {"content": "Loading your profile and resume...\n"})
        user_context = load_user_context(self.tools)

        lm = build_lm(self.llm_config)

        # 3. Planning — analyse job, profile, and resume
        self.event_bus.emit("text_delta", {"content": "Analysing the role and your background...\n"})

        planner = dspy.ChainOfThought(AnalyseInterviewSig)
        with dspy.context(lm=lm):
            analysis = planner(
                user_message=user_message,
                job_context=job_context,
                user_context=user_context,
            )

        key_themes = list(analysis.key_themes) if analysis.key_themes else []
        candidate_strengths = list(analysis.candidate_strengths) if analysis.candidate_strengths else []
        focus_areas = list(analysis.focus_areas) if analysis.focus_areas else []
        gap_notes = list(analysis.gap_notes) if analysis.gap_notes else []

        # Stream the plan summary
        plan_lines = ["## Interview Prep Plan\n"]
        if key_themes:
            plan_lines.append("**Key themes:** " + ", ".join(key_themes))
        if candidate_strengths:
            plan_lines.append("**Your strengths:** " + ", ".join(candidate_strengths))
        if focus_areas:
            plan_lines.append("**Focus areas:**")
            for fa in focus_areas:
                plan_lines.append(f"- {fa.area}: {fa.reasoning}")
        plan_lines.append("")
        self.event_bus.emit("text_delta", {"content": "\n".join(plan_lines) + "\n"})

        # Serialise plan outputs for downstream modules
        key_themes_str = "\n".join(key_themes)
        candidate_strengths_str = "\n".join(candidate_strengths)
        gap_notes_str = "\n".join(gap_notes)

        # 4. Run five specialist sub-modules in parallel
        self.event_bus.emit("text_delta", {"content": "Generating interview preparation materials...\n"})

        section_results: dict[str, str] = {}
        section_labels = {
            "company_brief": "Company & Role Research Brief",
            "behavioural": "Behavioural Questions & STAR Answers",
            "technical": "Technical & Domain Questions",
            "gaps": "Weakness & Gap Mitigation",
            "interviewer_qs": "Questions for the Interviewer",
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures: dict[concurrent.futures.Future, str] = {
                pool.submit(
                    self._run_company_brief,
                    lm, job_context, key_themes_str,
                ): "company_brief",
                pool.submit(
                    self._run_behavioural_questions,
                    lm, job_context, user_context, key_themes_str,
                    candidate_strengths_str,
                ): "behavioural",
                pool.submit(
                    self._run_technical_questions,
                    lm, job_context, user_context, key_themes_str,
                ): "technical",
                pool.submit(
                    self._run_weakness_gap,
                    lm, job_context, user_context, gap_notes_str,
                ): "gaps",
                pool.submit(
                    self._run_questions_for_interviewer,
                    lm, job_context, user_context, key_themes_str,
                ): "interviewer_qs",
            }

            # Wait for all futures to complete.  Tool events are
            # auto-emitted by AgentTools.execute() via the event bus.
            for future in concurrent.futures.as_completed(futures):
                key = futures[future]
                label = section_labels[key]
                exc = future.exception()
                if exc:
                    logger.warning(
                        "Interview prep sub-module '%s' failed: %s", key, exc,
                    )
                    section_results[key] = f"### {label}\n\n_Generation failed — please retry._"
                else:
                    section_results[key] = future.result()

                self.event_bus.emit("text_delta", {"content": f"  completed: {label}\n"})

        # 5. Assemble into a unified prep guide
        self.event_bus.emit("text_delta", {"content": "\nAssembling your interview prep guide...\n\n"})

        assembler = dspy.ChainOfThought(AssemblePrepGuideSig)
        with dspy.context(lm=lm):
            assembled = assembler(
                job_label=job_label,
                company_brief=section_results.get("company_brief", ""),
                behavioural_section=section_results.get("behavioural", ""),
                technical_section=section_results.get("technical", ""),
                gaps_section=section_results.get("gaps", ""),
                interviewer_questions_section=section_results.get("interviewer_qs", ""),
            )

        checklist = list(assembled.day_of_checklist) if assembled.day_of_checklist else []
        guide = assembled.assembled_guide.strip() if assembled.assembled_guide else ""

        # Fall back to concatenated sections if assembly fails
        if not guide:
            guide = "\n\n".join(
                section_results.get(k, "")
                for k in ("company_brief", "behavioural", "technical", "gaps", "interviewer_qs")
            )

        checklist_text = ""
        if checklist:
            checklist_text = (
                "## Day-of Checklist\n\n"
                + "\n".join(f"- [ ] {item}" for item in checklist)
                + "\n\n"
            )

        self.event_bus.emit("text_delta", {
            "content": (
                f"---\n\n"
                f"# Interview Prep Guide — {job_label}\n\n"
                f"{checklist_text}"
                f"{guide}\n\n"
                f"---\n"
            ),
        })

        summary = f"Generated interview prep guide for {job_label}."

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=True,
            data={
                "job": job,
                "key_themes": key_themes,
                "candidate_strengths": candidate_strengths,
                "gap_notes": gap_notes,
                "checklist": checklist,
            },
            summary=summary,
        )
