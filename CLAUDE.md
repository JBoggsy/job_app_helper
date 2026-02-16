# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Job application helper — a web app to track and manage job applications.

## Tech Stack

- **Backend:** Python 3.12+, Flask, Flask-SQLAlchemy, SQLite
- **Frontend:** React 19, Vite
- **Package management:** uv (Python), npm (JS)

## Key Commands

### Backend
- `uv sync` — install Python dependencies
- `uv run python main.py` — start Flask dev server (port 5000)

### Frontend
- `cd frontend && npm install` — install JS dependencies
- `cd frontend && npm run dev` — start Vite dev server (port 3000)
- `cd frontend && npm run build` — production build

## Project Structure

- `backend/app.py` — Flask app factory (`create_app`)
- `backend/config.py` — app configuration
- `backend/database.py` — SQLAlchemy `db` instance
- `backend/models/` — SQLAlchemy models (e.g., `Job`)
- `backend/routes/` — API blueprints (e.g., `jobs_bp` at `/api/jobs`)
- `frontend/src/` — React source code
- `main.py` — entry point, runs Flask server

## Conventions

- Backend API routes are prefixed with `/api/`
- Frontend Vite dev server proxies `/api` to Flask at `localhost:5000`
- SQLite database file is `app.db` in the project root (gitignored)
