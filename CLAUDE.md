# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Job application helper — a web app to track and manage job applications. Users can add, edit, and delete job applications and track their status through the hiring pipeline.

## Tech Stack

- **Backend:** Python 3.12+, Flask, Flask-SQLAlchemy, SQLite
- **Frontend:** React 19, Vite, Tailwind CSS 4
- **Package management:** uv (Python), npm (JS)

## Key Commands

### Backend
- `uv sync` — install Python dependencies
- `uv run python main.py` — start Flask dev server (port 5000)

### Frontend
- `cd frontend && npm install` — install JS dependencies
- `cd frontend && npm run dev` — start Vite dev server (port 3000)
- `cd frontend && npm run build` — production build (use to verify changes compile)

## Project Structure

### Backend
- `main.py` — entry point, runs Flask server
- `backend/app.py` — Flask app factory (`create_app`)
- `backend/config.py` — app configuration
- `backend/database.py` — SQLAlchemy `db` instance
- `backend/models/job.py` — `Job` model (fields: `id`, `company`, `title`, `url`, `status`, `notes`, `salary_min`, `salary_max`, `location`, `remote_type`, `tags`, `contact_name`, `contact_email`, `applied_date`, `source`, `created_at`, `updated_at`)
- `backend/routes/jobs.py` — CRUD blueprint (`jobs_bp` at `/api/jobs`)

### Frontend
- `frontend/vite.config.js` — Vite config (React plugin, Tailwind CSS plugin, API proxy)
- `frontend/src/main.jsx` — React entry point
- `frontend/src/index.css` — Tailwind CSS base import
- `frontend/src/App.jsx` — App shell with header and layout
- `frontend/src/api.js` — API helper (`fetchJobs`, `createJob`, `updateJob`, `deleteJob`)
- `frontend/src/pages/JobList.jsx` — Main dashboard: job table with status badges, add/edit/delete
- `frontend/src/components/JobForm.jsx` — Reusable form for creating and editing jobs

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/jobs` | List all jobs (newest first) |
| POST | `/api/jobs` | Create job (`company`, `title` required) |
| GET | `/api/jobs/:id` | Get single job |
| PATCH | `/api/jobs/:id` | Update job (partial) |
| DELETE | `/api/jobs/:id` | Delete job |

Job statuses: `saved`, `applied`, `interviewing`, `offer`, `rejected`
Remote types: `onsite`, `hybrid`, `remote` (or `null`)

Optional job fields: `salary_min` (int), `salary_max` (int), `location` (string), `remote_type` (string), `tags` (comma-separated string), `contact_name` (string), `contact_email` (string), `applied_date` (ISO date string), `source` (string)

## Conventions

- Backend API routes are prefixed with `/api/`
- Frontend Vite dev server proxies `/api` to Flask at `localhost:5000`
- SQLite database file is `app.db` in the project root (gitignored)
- Frontend pages live in `frontend/src/pages/`, reusable components in `frontend/src/components/`
- API helper functions in `frontend/src/api.js` — all backend calls go through this module

## Best Practices

### General
- Keep changes focused — one feature or fix per commit
- Run `cd frontend && npm run build` to verify frontend changes compile before committing
- Prefer editing existing files over creating new ones to avoid file bloat

### Backend (Python)
- Follow PEP 8 style conventions
- Use Flask blueprints for new route groups; register them in `backend/app.py`
- Add new models in `backend/models/` and import them in `backend/models/__init__.py`
- Use SQLAlchemy model methods (e.g., `to_dict()`) to serialize responses — keep route handlers thin
- Validate required fields in route handlers before creating/updating records

### Frontend (React/JS)
- Use functional components with hooks (`useState`, `useEffect`)
- Place page-level components in `frontend/src/pages/`, shared UI in `frontend/src/components/`
- All API calls go through `frontend/src/api.js` — never call `fetch` directly in components
- Use Tailwind CSS utility classes for styling — no separate CSS files per component
- Keep components focused: if a component grows beyond ~150 lines, consider extracting subcomponents

## Documentation

After making changes, update this file (`CLAUDE.md`) to reflect:
- New or modified files in the project structure section
- New API endpoints or changes to existing ones
- New commands, dependencies, or conventions
- Any architectural decisions that future contributors should know about

Keeping this file accurate ensures Claude Code (and human developers) can work with the codebase effectively.
