"""Find jobs pipeline — search for jobs matching criteria via job board APIs."""

import json
import logging

from ..feedback import record_evaluator_example, record_query_generator_example
from ..micro_agents import (
    EvaluatorAgent,
    QueryGeneratorAgent,
    ResultsSummaryAgent,
)
from ..pipeline_base import Pipeline, ToolResult
from ..prompts import (
    EVALUATOR_PROMPT,
    QUERY_GENERATOR_PROMPT,
    RESULTS_SUMMARY_PROMPT,
)
from ..schemas import FindJobsParams

logger = logging.getLogger(__name__)


class FindJobsPipeline(Pipeline):
    params_schema = FindJobsParams

    def execute(self):
        p = self.params
        logger.info("[FindJobsPipeline] query=%s, location=%s, remote=%s, num_results=%d",
                    p.query, p.location, p.remote_type, p.num_results)

        # Step 1: Load profile and resume
        profile = self.ctx.ensure_profile()
        logger.info("[FindJobsPipeline] profile loaded, len=%d", len(profile))
        resume_summary = self.ctx.get_resume_summary()
        logger.info("[FindJobsPipeline] resume summary loaded, len=%d", len(resume_summary))

        # Step 2: Generate optimized search queries
        yield self.text("\n\nSearching job boards...")

        queries = self._generate_queries(profile)
        logger.info("[FindJobsPipeline] generated %d search queries: %s",
                    len(queries), queries)
        if not queries:
            queries = [{"query": p.query, "location": p.location, "remote_only": p.remote_type == "remote"}]
            logger.info("[FindJobsPipeline] using fallback query: %s", queries)

        # Step 3: Execute job searches
        all_results = []
        for q in queries:
            search_args = {
                "query": q.get("query", p.query),
                "num_results": min(p.num_results, 20),
            }
            if q.get("location") or p.location:
                search_args["location"] = q.get("location") or p.location
            if q.get("remote_only") or p.remote_type == "remote":
                search_args["remote_only"] = True
            if p.salary_min:
                search_args["salary_min"] = p.salary_min
            if p.employment_type:
                search_args["employment_type"] = p.employment_type
            if p.date_posted:
                search_args["date_posted"] = p.date_posted

            tr = ToolResult()
            yield from self.exec_tool("job_search", search_args, tr)

            results = tr.data.get("results", [])
            all_results.extend(results)

        logger.info("[FindJobsPipeline] job_search returned %d total results", len(all_results))

        if not all_results:
            yield self.text("\n\nI couldn't find any jobs matching your criteria. Try broadening your search terms or adjusting filters.")
            return

        # Step 4: Deduplicate by URL or company+title
        deduped = _deduplicate(all_results)
        logger.info("[FindJobsPipeline] %d unique results after dedup", len(deduped))
        yield self.text(f"\n\nFound {len(deduped)} unique results. Evaluating fit...")

        # Step 5: Evaluate jobs against profile
        logger.info("[FindJobsPipeline] evaluating %d jobs against profile", len(deduped))
        evaluations = _evaluate_jobs(self.model, deduped, profile, resume_summary,
                                      user_intent=p.user_intent,
                                      soft_constraints=p.soft_constraints,
                                      conversation_id=self.ctx.tools.conversation_id)
        logger.info("[FindJobsPipeline] evaluations done — %d results", len(evaluations))

        # Step 6: Filter and add search results
        added_count = 0
        added_results = []
        for i, job in enumerate(deduped):
            eval_data = evaluations.get(i, {"job_fit": 3, "fit_reason": ""})
            job_fit = eval_data.get("job_fit", 3)

            if job_fit < 3:
                continue

            sr_data = {
                "company": job.get("company", "Unknown"),
                "title": job.get("title", "Unknown"),
                "job_fit": job_fit,
                "fit_reason": eval_data.get("fit_reason", ""),
            }
            if job.get("url"):
                sr_data["url"] = job["url"]
            if job.get("salary_min"):
                sr_data["salary_min"] = job["salary_min"]
            if job.get("salary_max"):
                sr_data["salary_max"] = job["salary_max"]
            if job.get("location"):
                sr_data["location"] = job["location"]
            if job.get("remote"):
                sr_data["remote_type"] = "remote"
            if job.get("description"):
                sr_data["description"] = job["description"][:500]
            if job.get("source"):
                sr_data["source"] = job["source"]

            tr = ToolResult()
            yield from self.exec_tool("add_search_result", sr_data, tr)

            if not tr.is_error:
                added_count += 1
                added_results.append({**sr_data, "result": tr.data.get("search_result", {})})

            if added_count >= p.num_results:
                break

        # Step 7: Summarize results
        yield self.text("\n\n")
        yield from self._summarize_results(added_results, len(deduped))

    def _generate_queries(self, profile: str) -> list[dict]:
        p = self.params
        try:
            criteria = json.dumps({
                "query": p.query, "location": p.location, "remote_type": p.remote_type,
                "salary_min": p.salary_min, "salary_max": p.salary_max,
                "employment_type": p.employment_type,
                "user_intent": p.user_intent,
                "soft_constraints": p.soft_constraints,
            })
            system_prompt = QUERY_GENERATOR_PROMPT.format(criteria=criteria, profile=profile)
            agent = QueryGeneratorAgent(self.model)
            result = agent.run(system_prompt, f"Generate search queries for: {p.query}")
            if hasattr(result, "queries"):
                # Record feedback example
                try:
                    record_query_generator_example(
                        self.ctx.tools.conversation_id, criteria, profile, result,
                    )
                except Exception as e:
                    logger.debug("Failed to record query_generator example: %s", e)
                return [{"query": q.query, "location": q.location, "remote_only": q.remote_only}
                        for q in result.queries]
        except Exception as e:
            logger.warning("Query generation failed: %s", e)
        return []

    def _summarize_results(self, added_results: list[dict], total_found: int):
        p = self.params
        results_text = ""
        for r in added_results[:10]:
            results_text += f"- {r.get('title', '?')} at {r.get('company', '?')}"
            results_text += f" ({r.get('job_fit', '?')}/5"
            if r.get("fit_reason"):
                results_text += f": {r['fit_reason']}"
            results_text += ")\n"

        system_prompt = RESULTS_SUMMARY_PROMPT.format(
            params=json.dumps({"query": p.query, "location": p.location, "remote_type": p.remote_type}),
            results=results_text or "(no results passed the filter)",
            total_found=total_found,
        )

        agent = ResultsSummaryAgent(self.model)
        for chunk in agent.run(system_prompt, "Summarize these job search results."):
            yield self.text(chunk)


def _evaluate_jobs(model, jobs: list[dict], profile: str, resume_summary: str,
                   *, user_intent: str = "", soft_constraints: list[str] | None = None,
                   conversation_id: int | None = None) -> dict:
    """Evaluate jobs against profile using micro-agent. Returns {index: {job_fit, fit_reason}}."""
    if not jobs:
        return {}

    try:
        jobs_text = ""
        for i, job in enumerate(jobs[:15]):
            jobs_text += f"\n[Job {i}] {job.get('title', '?')} at {job.get('company', '?')}"
            if job.get("location"):
                jobs_text += f" | Location: {job['location']}"
            if job.get("salary_min") or job.get("salary_max"):
                jobs_text += f" | Salary: {job.get('salary_min', '?')}-{job.get('salary_max', '?')}"
            if job.get("description"):
                jobs_text += f"\n  {job['description'][:200]}"

        constraints_text = "\n".join(f"- {c}" for c in (soft_constraints or [])) or "(none)"
        system_prompt = EVALUATOR_PROMPT.format(
            profile=profile, resume_summary=resume_summary, jobs=jobs_text,
            user_intent=user_intent or "(not specified)",
            soft_constraints=constraints_text,
        )
        agent = EvaluatorAgent(model)
        result = agent.run(system_prompt, "Evaluate these jobs against the user's profile.")
        if hasattr(result, "evaluations"):
            # Record feedback example
            try:
                if conversation_id:
                    record_evaluator_example(conversation_id, system_prompt, jobs_text, result)
            except Exception as fe:
                logger.debug("Failed to record evaluator example: %s", fe)
            return {e.index: {"job_fit": e.job_fit, "fit_reason": e.fit_reason}
                    for e in result.evaluations}
    except Exception as e:
        logger.warning("Job evaluation failed: %s", e)

    return {i: {"job_fit": 3, "fit_reason": "Could not evaluate fit"} for i in range(len(jobs))}


def _deduplicate(results: list[dict]) -> list[dict]:
    """Deduplicate job results by URL or company+title."""
    seen = set()
    deduped = []
    for job in results:
        url = job.get("url", "")
        company = job.get("company", "").lower().strip()
        title = job.get("title", "").lower().strip()

        key = url if url else f"{company}|{title}"
        if key and key not in seen:
            seen.add(key)
            deduped.append(job)
    return deduped


def run(model, params, ctx):
    yield from FindJobsPipeline(model, params, ctx).execute()
