"""DSPy Module implementations for structured-output micro-agents.

Each module wraps a dspy.ChainOfThought call and exposes a run() method
matching the interface that pipelines already use:
    run(system_prompt: str, user_message: str) -> Pydantic model
"""

import logging

import dspy

from . import schemas
from .module_store import load_module_state
from .dspy_signatures import (
    EvaluateFit,
    EvaluateJobs,
    ExtractJobDetails,
    GenerateResearchQueries,
    GenerateSearchQueries,
    GenerateTodos,
    RouteRequest,
    UpdateProfile,
)

logger = logging.getLogger(__name__)


class RoutingModule(dspy.Module):
    """Classify user intent and extract structured parameters."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(RouteRequest)

    def forward(self, conversation_context: str) -> schemas.RoutingResult:
        result = self.predict(conversation_context=conversation_context)
        return result.routing_result


class QueryGeneratorModule(dspy.Module):
    """Generate optimized job search queries."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(GenerateSearchQueries)
        load_module_state("query_generator", self)

    def forward(self, search_criteria: str, user_profile: str) -> schemas.QueryGeneratorResult:
        result = self.predict(search_criteria=search_criteria, user_profile=user_profile)
        return result.query_result

    def run(self, system_prompt: str, user_message: str) -> schemas.QueryGeneratorResult:
        """Backward-compatible interface matching BaseMicroAgent.run()."""
        agent_name = type(self).__name__
        logger.info("[%s] run start — user_msg=%s", agent_name, user_message[:150])
        result = self(search_criteria=system_prompt, user_profile=user_message)
        logger.info("[%s] run done — %d queries", agent_name, len(result.queries) if hasattr(result, "queries") else 0)
        return result


class EvaluatorModule(dspy.Module):
    """Evaluate job results against user profile."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(EvaluateJobs)
        load_module_state("evaluator", self)

    def forward(self, job_context: str, job_results: str) -> schemas.JobEvaluationResult:
        result = self.predict(job_context=job_context, job_results=job_results)
        return result.evaluation_result

    def run(self, system_prompt: str, user_message: str) -> schemas.JobEvaluationResult:
        agent_name = type(self).__name__
        logger.info("[%s] run start — user_msg=%s", agent_name, user_message[:150])
        result = self(job_context=system_prompt, job_results=user_message)
        logger.info("[%s] run done — %d evaluations", agent_name, len(result.evaluations) if hasattr(result, "evaluations") else 0)
        return result


class ProfileUpdateModule(dspy.Module):
    """Interpret natural-language profile updates."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(UpdateProfile)

    def forward(self, current_profile: str, update_request: str) -> schemas.ProfileUpdateResult:
        result = self.predict(current_profile=current_profile, update_request=update_request)
        return result.profile_update

    def run(self, system_prompt: str, user_message: str) -> schemas.ProfileUpdateResult:
        agent_name = type(self).__name__
        logger.info("[%s] run start — user_msg=%s", agent_name, user_message[:150])
        result = self(current_profile=system_prompt, update_request=user_message)
        logger.info("[%s] run done — %d updates", agent_name, len(result.updates) if hasattr(result, "updates") else 0)
        return result


class TodoGeneratorModule(dspy.Module):
    """Generate application preparation todos."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(GenerateTodos)

    def forward(self, job_details: str, user_profile: str) -> schemas.TodoGeneratorResult:
        result = self.predict(job_details=job_details, user_profile=user_profile)
        return result.todo_result

    def run(self, system_prompt: str, user_message: str) -> schemas.TodoGeneratorResult:
        agent_name = type(self).__name__
        logger.info("[%s] run start — user_msg=%s", agent_name, user_message[:150])
        result = self(job_details=system_prompt, user_profile=user_message)
        logger.info("[%s] run done — %d todos", agent_name, len(result.todos) if hasattr(result, "todos") else 0)
        return result


class DetailExtractionModule(dspy.Module):
    """Extract structured job details from raw data."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(ExtractJobDetails)

    def forward(self, raw_data: str, url: str) -> schemas.JobDetails:
        result = self.predict(raw_data=raw_data, url=url)
        return result.job_details

    def run(self, system_prompt: str, user_message: str) -> schemas.JobDetails:
        agent_name = type(self).__name__
        logger.info("[%s] run start — user_msg=%s", agent_name, user_message[:150])
        result = self(raw_data=system_prompt, url=user_message)
        logger.info("[%s] run done — company=%s, title=%s", agent_name,
                    getattr(result, "company", "?"), getattr(result, "title", "?"))
        return result


class FitEvaluatorModule(dspy.Module):
    """Deep fit analysis with strengths and gaps."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(EvaluateFit)

    def forward(self, job_details: str, user_profile: str, resume_summary: str) -> schemas.FitEvaluation:
        result = self.predict(job_details=job_details, user_profile=user_profile, resume_summary=resume_summary)
        return result.fit_evaluation

    def run(self, system_prompt: str, user_message: str) -> schemas.FitEvaluation:
        agent_name = type(self).__name__
        logger.info("[%s] run start — user_msg=%s", agent_name, user_message[:150])
        result = self(job_details=system_prompt, user_profile=user_message, resume_summary="")
        logger.info("[%s] run done — fit=%s", agent_name, getattr(result, "job_fit", "?"))
        return result


class ResearchQueryModule(dspy.Module):
    """Generate research search queries."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(GenerateResearchQueries)

    def forward(self, topic: str, research_type: str, company_context: str) -> schemas.SearchQueryList:
        result = self.predict(topic=topic, research_type=research_type, company_context=company_context)
        return result.search_queries

    def run(self, system_prompt: str, user_message: str) -> schemas.SearchQueryList:
        agent_name = type(self).__name__
        logger.info("[%s] run start — user_msg=%s", agent_name, user_message[:150])
        result = self(topic=system_prompt, research_type="general", company_context=user_message)
        logger.info("[%s] run done — %d queries", agent_name, len(result.queries) if hasattr(result, "queries") else 0)
        return result
