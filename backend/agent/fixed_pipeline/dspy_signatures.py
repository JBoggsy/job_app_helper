"""DSPy Signature definitions for structured-output micro-agents.

Each signature maps to one micro-agent that previously used
BaseMicroAgent.invoke() with a Pydantic output schema. The docstring
serves as the DSPy instruction (replaces the system prompt for DSPy calls).
"""

import dspy

from .schemas import (
    FitEvaluation,
    JobDetails,
    JobEvaluationResult,
    ProfileUpdateResult,
    QueryGeneratorResult,
    RoutingResult,
    SearchQueryList,
    TodoGeneratorResult,
)


class RouteRequest(dspy.Signature):
    """You are a request classifier for a job-search assistant app called Shortlist.

    Given the user's message and recent conversation history, classify the request
    into exactly one type and extract structured parameters.

    Request Types:
    - find_jobs: Search for new job listings. Params: query, location, remote_type, salary_min, salary_max, employment_type, date_posted, num_results, user_intent, soft_constraints
    - research_url: Analyze a specific URL. Params: url, intent
    - track_crud: Create/edit/delete a tracked job. Params: action, job_ref, job_id, fields
    - query_jobs: Read/filter/summarize tracked jobs. Params: filters, question, format
    - todo_mgmt: Manage application todos. Params: action, job_ref, job_id, todo_id, todo_data
    - profile_mgmt: Read/update user profile. Params: action, section, content, natural_update
    - prepare: Interview prep, cover letters, resume tailoring. Params: prep_type, job_ref, job_id, specifics
    - compare: Compare or rank jobs. Params: job_refs, job_ids, dimensions, mode
    - research: Research companies, salaries, industries. Params: topic, research_type, company, role
    - general: Career advice, open-ended questions. Params: question, needs_job_context, needs_profile, job_ref
    - multi_step: Compound request requiring 2+ steps. Params: steps

    Instructions:
    1. Classify into exactly ONE type. Pick the most specific.
    2. Extract all relevant parameters.
    3. Include entity_refs: job names, company names, IDs, or URLs mentioned.
    4. Write a brief acknowledgment confirming what you'll do.
    5. URLs → research_url (unless user explicitly asks to just track it).
    6. Multiple distinct steps → multi_step.
    7. When in doubt → general.
    """

    conversation_context: str = dspy.InputField(desc="Recent conversation messages for context")
    routing_result: RoutingResult = dspy.OutputField(desc="Classification with request_type, params, entity_refs, acknowledgment")


class GenerateSearchQueries(dspy.Signature):
    """You are a job search query optimizer. Generate optimized search queries
    based on the user's search criteria and their profile.

    IMPORTANT RULES:
    - Keep queries SHORT — 2-4 words max (e.g., "machine learning engineer")
    - Use COMMON job titles that employers actually post
    - DO NOT combine multiple specializations into one query
    - Each query should be a different common job title matching the user's skills
    - Cast a wide net — better to get too many results than too few

    GEOGRAPHIC EXPANSION:
    - If the user specified a vague region (e.g., "the South"), generate separate
      queries targeting specific major cities in that region.
    """

    search_criteria: str = dspy.InputField(desc="User's search criteria including query, location, filters")
    user_profile: str = dspy.InputField(desc="User's profile with skills, preferences, and goals")
    query_result: QueryGeneratorResult = dspy.OutputField(desc="List of optimized search queries")


class EvaluateJobs(dspy.Signature):
    """You are a job fit evaluator. Rate each job result against the user's
    profile and preferences.

    For each job (identified by index), provide:
    - job_fit: 0-5 star rating (0=terrible fit, 3=decent, 5=perfect)
    - fit_reason: 1-2 sentence explanation

    Consider: skills match, salary alignment, location/remote preferences,
    career goals, experience level, AND any soft constraints provided.
    Penalize results that violate soft constraints.
    """

    job_context: str = dspy.InputField(desc="User profile, resume summary, search context, and soft constraints")
    job_results: str = dspy.InputField(desc="Job results to evaluate, with index numbers")
    evaluation_result: JobEvaluationResult = dspy.OutputField(desc="Evaluations with job_fit and fit_reason per job")


class UpdateProfile(dspy.Signature):
    """You are a profile editor for a job-search app.

    Determine which profile sections need to be updated and what the new content
    should be based on the user's request.

    Available sections: Summary, Education, Work Experience, Skills & Expertise,
    Fields of Interest, Salary Preferences, Location Preferences,
    Remote Work Preferences, Job Search Goals, Other Notes

    For each section that needs updating, provide the complete new content
    (merge with existing content if appropriate).
    """

    current_profile: str = dspy.InputField(desc="Current user profile content")
    update_request: str = dspy.InputField(desc="User's natural-language update request")
    profile_update: ProfileUpdateResult = dspy.OutputField(desc="List of section updates")


class GenerateTodos(dspy.Signature):
    """You are a job application prep assistant. Generate a practical checklist
    of 5-10 application tasks for the given job.

    Use these categories:
    - document: resume, cover letter, portfolio items
    - question: questions to prepare for or ask
    - assessment: technical tests, assignments
    - reference: references, recommendations
    - other: anything else

    Each task should have a clear, actionable title and brief description.
    """

    job_details: str = dspy.InputField(desc="Job details as JSON")
    user_profile: str = dspy.InputField(desc="User profile and resume summary")
    todo_result: TodoGeneratorResult = dspy.OutputField(desc="List of actionable todo items")


class ExtractJobDetails(dspy.Signature):
    """You are a job posting parser. Extract structured details from raw job data.

    Extract all available fields: company, title, url, salary_min (int),
    salary_max (int), location, remote_type (remote/hybrid/onsite),
    description (brief summary), requirements (newline-separated list),
    nice_to_haves (newline-separated list), source.

    Use null for any fields not present in the data. For salary, extract
    numeric values only.
    """

    raw_data: str = dspy.InputField(desc="Raw job posting content to parse")
    url: str = dspy.InputField(desc="URL of the job posting")
    job_details: JobDetails = dspy.OutputField(desc="Structured job details")


class EvaluateFit(dspy.Signature):
    """You are a job fit analyst. Provide a detailed fit analysis for this job
    against the user's profile and resume.

    Analyze:
    1. Overall fit rating (0-5 stars)
    2. Key strengths (what makes this a good match)
    3. Gaps (what the user might be missing)
    4. Brief explanation of the rating
    """

    job_details: str = dspy.InputField(desc="Job details as JSON")
    user_profile: str = dspy.InputField(desc="User profile content")
    resume_summary: str = dspy.InputField(desc="User's resume summary")
    fit_evaluation: FitEvaluation = dspy.OutputField(desc="Fit rating, strengths, gaps, and reason")


class GenerateResearchQueries(dspy.Signature):
    """Generate 2-4 web search queries to research the given topic.

    Generate queries that will find authoritative, recent information.
    Be specific and use terms that will return high-quality results.
    """

    topic: str = dspy.InputField(desc="Research topic")
    research_type: str = dspy.InputField(desc="Type of research: company, salary, interview_process, industry, general")
    company_context: str = dspy.InputField(desc="Additional company/role context if available")
    search_queries: SearchQueryList = dspy.OutputField(desc="List of search query strings")
