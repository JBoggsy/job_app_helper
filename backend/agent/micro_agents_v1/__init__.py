"""Micro agents v1 — workflow-orchestrated agent design.

User requests are decomposed into discrete outcomes by a DSPy Outcome
Planner, mapped to hand-crafted workflows by a DSPy Workflow Mapper,
executed in dependency order by a deterministic Workflow Executor, and
finally synthesised into a unified response by a DSPy Result Collator.

Complex reasoning steps within workflows (entity resolution, field
extraction, fit evaluation, etc.) are handled by small, focused DSPy
modules ("micro-agents") that can be independently optimised via DSPy's
prompt-tuning and few-shot bootstrapping.

See ``backend/agent/micro_agents_v1/README.md`` for full architecture
documentation.
"""

from .agent import MicroAgentsV1Agent
from .onboarding_agent import MicroAgentsV1OnboardingAgent
from .resume_parser import MicroAgentsV1ResumeParser

__all__ = ["MicroAgentsV1Agent", "MicroAgentsV1OnboardingAgent", "MicroAgentsV1ResumeParser"]
