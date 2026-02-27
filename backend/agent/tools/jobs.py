"""Job tracker tools — create_job, list_jobs, edit_job, remove_job."""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from ._registry import agent_tool

logger = logging.getLogger(__name__)

VALID_STATUSES = {"saved", "applied", "interviewing", "offer", "rejected"}
VALID_REMOTE_TYPES = {"onsite", "hybrid", "remote"}

# Fields that can be set/updated on a Job record
_EDITABLE_FIELDS = (
    "company", "title", "url", "status", "notes",
    "salary_min", "salary_max", "location", "remote_type",
    "tags", "contact_name", "contact_email", "source",
    "job_fit", "requirements", "nice_to_haves",
)


class CreateJobInput(BaseModel):
    company: str = Field(description="Company name")
    title: str = Field(description="Job title")
    url: Optional[str] = Field(default=None, description="Job posting URL")
    status: Optional[str] = Field(default=None, description="Application status (saved, applied, interviewing, offer, rejected)")
    notes: Optional[str] = Field(default=None, description="Notes")
    salary_min: Optional[int] = Field(default=None, description="Minimum salary")
    salary_max: Optional[int] = Field(default=None, description="Maximum salary")
    location: Optional[str] = Field(default=None, description="Job location")
    remote_type: Optional[str] = Field(default=None, description="Remote type (onsite, hybrid, remote)")
    tags: Optional[str] = Field(default=None, description="Comma-separated tags")
    contact_name: Optional[str] = Field(default=None, description="Contact name")
    contact_email: Optional[str] = Field(default=None, description="Contact email")
    source: Optional[str] = Field(default=None, description="Job source")
    requirements: Optional[str] = Field(default=None, description="Requirements (newline-separated)")
    nice_to_haves: Optional[str] = Field(default=None, description="Nice-to-haves (newline-separated)")
    job_fit: Optional[int] = Field(default=None, description="Job fit rating 0-5")


class ListJobsInput(BaseModel):
    status: Optional[str] = Field(default=None, description="Filter by status (saved, applied, interviewing, offer, rejected)")
    company: Optional[str] = Field(default=None, description="Filter by company (case-insensitive substring match)")
    title: Optional[str] = Field(default=None, description="Filter by title (case-insensitive substring match)")
    url: Optional[str] = Field(default=None, description="Filter by URL (case-insensitive substring match)")
    limit: int = Field(default=20, description="Max results")


class EditJobInput(BaseModel):
    job_id: int = Field(description="ID of the job to edit")
    company: Optional[str] = Field(default=None, description="Updated company name")
    title: Optional[str] = Field(default=None, description="Updated job title")
    url: Optional[str] = Field(default=None, description="Updated job posting URL")
    status: Optional[str] = Field(default=None, description="Updated status (saved, applied, interviewing, offer, rejected)")
    notes: Optional[str] = Field(default=None, description="Updated notes")
    salary_min: Optional[int] = Field(default=None, description="Updated minimum salary")
    salary_max: Optional[int] = Field(default=None, description="Updated maximum salary")
    location: Optional[str] = Field(default=None, description="Updated job location")
    remote_type: Optional[str] = Field(default=None, description="Updated remote type (onsite, hybrid, remote)")
    tags: Optional[str] = Field(default=None, description="Updated comma-separated tags")
    contact_name: Optional[str] = Field(default=None, description="Updated contact name")
    contact_email: Optional[str] = Field(default=None, description="Updated contact email")
    source: Optional[str] = Field(default=None, description="Updated job source")
    requirements: Optional[str] = Field(default=None, description="Updated requirements (newline-separated)")
    nice_to_haves: Optional[str] = Field(default=None, description="Updated nice-to-haves (newline-separated)")
    job_fit: Optional[int] = Field(default=None, description="Updated job fit rating 0-5")


class RemoveJobInput(BaseModel):
    job_id: int = Field(description="ID of the job to remove")


VALID_TODO_CATEGORIES = {"document", "question", "assessment", "reference", "other"}


class AddJobTodoInput(BaseModel):
    job_id: int = Field(description="ID of the job to add a todo to")
    title: str = Field(description="Title of the todo item")
    category: Optional[str] = Field(default=None, description="Category (document, question, assessment, reference, other)")
    description: Optional[str] = Field(default=None, description="Detailed description of the todo item")
    completed: Optional[bool] = Field(default=None, description="Whether the todo is already completed")


class EditJobTodoInput(BaseModel):
    job_id: int = Field(description="ID of the job the todo belongs to")
    todo_id: int = Field(description="ID of the todo to edit")
    title: Optional[str] = Field(default=None, description="Updated title")
    category: Optional[str] = Field(default=None, description="Updated category (document, question, assessment, reference, other)")
    description: Optional[str] = Field(default=None, description="Updated description")
    completed: Optional[bool] = Field(default=None, description="Updated completion status")
    sort_order: Optional[int] = Field(default=None, description="Updated sort order")


class RemoveJobTodoInput(BaseModel):
    job_id: int = Field(description="ID of the job the todo belongs to")
    todo_id: int = Field(description="ID of the todo to remove")


class ListJobTodosInput(BaseModel):
    job_id: int = Field(description="ID of the job to list todos for")


class JobsMixin:
    @agent_tool(
        description="Add a new job application to the tracker.",
        args_schema=CreateJobInput,
    )
    def create_job(self, company, title, url=None, status=None, notes=None,
                   salary_min=None, salary_max=None, location=None,
                   remote_type=None, tags=None, contact_name=None,
                   contact_email=None, source=None, requirements=None,
                   nice_to_haves=None, job_fit=None):
        from backend.database import db
        from backend.models.job import Job

        if status and status not in VALID_STATUSES:
            return {"error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}
        if remote_type and remote_type not in VALID_REMOTE_TYPES:
            return {"error": f"Invalid remote_type '{remote_type}'. Must be one of: {', '.join(sorted(VALID_REMOTE_TYPES))}"}
        if job_fit is not None and not (0 <= job_fit <= 5):
            return {"error": "job_fit must be between 0 and 5"}

        job = Job(
            company=company,
            title=title,
            url=url,
            status=status or "saved",
            notes=notes,
            salary_min=salary_min,
            salary_max=salary_max,
            location=location,
            remote_type=remote_type,
            tags=tags,
            contact_name=contact_name,
            contact_email=contact_email,
            source=source,
            requirements=requirements,
            nice_to_haves=nice_to_haves,
            job_fit=job_fit,
        )
        db.session.add(job)
        db.session.commit()
        logger.info("create_job: id=%d company=%s title=%s", job.id, company, title)
        return {"job": job.to_dict()}

    @agent_tool(
        description="List and search jobs in the tracker database. Returns jobs sorted by newest first.",
        args_schema=ListJobsInput,
    )
    def list_jobs(self, limit=20, status=None, company=None, title=None, url=None):
        from backend.models.job import Job

        query = Job.query
        if status:
            if status not in VALID_STATUSES:
                return {"error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}
            query = query.filter(Job.status == status)
        if company:
            query = query.filter(Job.company.ilike(f"%{company}%"))
        if title:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        if url:
            query = query.filter(Job.url.ilike(f"%{url}%"))
        jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
        return {"jobs": [j.to_dict() for j in jobs], "count": len(jobs)}

    @agent_tool(
        description=(
            "Edit an existing job application in the tracker. Only the fields you "
            "provide will be updated; omitted fields remain unchanged."
        ),
        args_schema=EditJobInput,
    )
    def edit_job(self, job_id, company=None, title=None, url=None, status=None,
                 notes=None, salary_min=None, salary_max=None, location=None,
                 remote_type=None, tags=None, contact_name=None,
                 contact_email=None, source=None, requirements=None,
                 nice_to_haves=None, job_fit=None):
        from backend.database import db
        from backend.models.job import Job

        job = db.session.get(Job, job_id)
        if not job:
            return {"error": f"Job with id {job_id} not found"}
        if status and status not in VALID_STATUSES:
            return {"error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}
        if remote_type and remote_type not in VALID_REMOTE_TYPES:
            return {"error": f"Invalid remote_type '{remote_type}'. Must be one of: {', '.join(sorted(VALID_REMOTE_TYPES))}"}
        if job_fit is not None and not (0 <= job_fit <= 5):
            return {"error": "job_fit must be between 0 and 5"}

        # Collect provided fields (only update what was explicitly passed)
        updates = {}
        local_args = locals()
        for field in _EDITABLE_FIELDS:
            val = local_args.get(field)
            if val is not None:
                updates[field] = val

        if not updates:
            return {"error": "No fields to update — provide at least one field to change"}

        for field, val in updates.items():
            setattr(job, field, val)
        db.session.commit()

        logger.info("edit_job: id=%d updated_fields=%s", job_id, list(updates.keys()))
        return {"job": job.to_dict(), "updated_fields": list(updates.keys())}

    @agent_tool(
        description="Remove a job application from the tracker. This permanently deletes the job and its associated application todos.",
        args_schema=RemoveJobInput,
    )
    def remove_job(self, job_id):
        from backend.database import db
        from backend.models.job import Job
        from backend.models.application_todo import ApplicationTodo

        job = db.session.get(Job, job_id)
        if not job:
            return {"error": f"Job with id {job_id} not found"}

        job_summary = {"id": job.id, "company": job.company, "title": job.title}

        # Delete associated application todos first
        ApplicationTodo.query.filter_by(job_id=job_id).delete()
        db.session.delete(job)
        db.session.commit()

        logger.info("remove_job: id=%d company=%s title=%s", job_id, job_summary["company"], job_summary["title"])
        return {"deleted": job_summary}

    # ------------------------------------------------------------------
    # Application Todo tools
    # ------------------------------------------------------------------

    @agent_tool(
        description="List application todo items for a job, ordered by sort_order.",
        args_schema=ListJobTodosInput,
    )
    def list_job_todos(self, job_id):
        from backend.database import db
        from backend.models.job import Job
        from backend.models.application_todo import ApplicationTodo

        job = db.session.get(Job, job_id)
        if not job:
            return {"error": f"Job with id {job_id} not found"}

        todos = (ApplicationTodo.query
                 .filter_by(job_id=job_id)
                 .order_by(ApplicationTodo.sort_order, ApplicationTodo.id)
                 .all())
        return {
            "job_id": job_id,
            "todos": [t.to_dict() for t in todos],
            "count": len(todos),
        }

    @agent_tool(
        description="Add an application todo item to a job (e.g. documents to prepare, questions to research, assessments to complete).",
        args_schema=AddJobTodoInput,
    )
    def add_job_todo(self, job_id, title, category=None, description=None, completed=None):
        from backend.database import db
        from backend.models.job import Job
        from backend.models.application_todo import ApplicationTodo

        job = db.session.get(Job, job_id)
        if not job:
            return {"error": f"Job with id {job_id} not found"}

        if category and category not in VALID_TODO_CATEGORIES:
            return {"error": f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_TODO_CATEGORIES))}"}

        # Determine next sort_order
        max_order = (db.session.query(db.func.max(ApplicationTodo.sort_order))
                     .filter_by(job_id=job_id).scalar())
        next_order = (max_order or 0) + 1

        todo = ApplicationTodo(
            job_id=job_id,
            category=category or "other",
            title=title,
            description=description or "",
            completed=bool(completed) if completed is not None else False,
            sort_order=next_order,
        )
        db.session.add(todo)
        db.session.commit()

        logger.info("add_job_todo: job_id=%d todo_id=%d title=%s", job_id, todo.id, title)
        return {"todo": todo.to_dict()}

    @agent_tool(
        description="Edit an existing application todo item. Only provided fields are updated.",
        args_schema=EditJobTodoInput,
    )
    def edit_job_todo(self, job_id, todo_id, title=None, category=None,
                      description=None, completed=None, sort_order=None):
        from backend.database import db
        from backend.models.job import Job
        from backend.models.application_todo import ApplicationTodo

        job = db.session.get(Job, job_id)
        if not job:
            return {"error": f"Job with id {job_id} not found"}

        todo = db.session.get(ApplicationTodo, todo_id)
        if not todo or todo.job_id != job_id:
            return {"error": f"Todo with id {todo_id} not found for job {job_id}"}

        if category and category not in VALID_TODO_CATEGORIES:
            return {"error": f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_TODO_CATEGORIES))}"}

        updates = {}
        if title is not None:
            todo.title = title
            updates["title"] = title
        if category is not None:
            todo.category = category
            updates["category"] = category
        if description is not None:
            todo.description = description
            updates["description"] = description
        if completed is not None:
            todo.completed = bool(completed)
            updates["completed"] = bool(completed)
        if sort_order is not None:
            todo.sort_order = sort_order
            updates["sort_order"] = sort_order

        if not updates:
            return {"error": "No fields to update — provide at least one field to change"}

        db.session.commit()

        logger.info("edit_job_todo: job_id=%d todo_id=%d updated=%s", job_id, todo_id, list(updates.keys()))
        return {"todo": todo.to_dict(), "updated_fields": list(updates.keys())}

    @agent_tool(
        description="Remove an application todo item from a job.",
        args_schema=RemoveJobTodoInput,
    )
    def remove_job_todo(self, job_id, todo_id):
        from backend.database import db
        from backend.models.job import Job
        from backend.models.application_todo import ApplicationTodo

        job = db.session.get(Job, job_id)
        if not job:
            return {"error": f"Job with id {job_id} not found"}

        todo = db.session.get(ApplicationTodo, todo_id)
        if not todo or todo.job_id != job_id:
            return {"error": f"Todo with id {todo_id} not found for job {job_id}"}

        todo_summary = {"id": todo.id, "job_id": job_id, "title": todo.title}
        db.session.delete(todo)
        db.session.commit()

        logger.info("remove_job_todo: job_id=%d todo_id=%d title=%s", job_id, todo_id, todo_summary["title"])
        return {"deleted": todo_summary}
