# Job App Helper

A web app to help track and manage job applications.

## Tech Stack

- **Backend:** Flask, Flask-SQLAlchemy, SQLite
- **Frontend:** React, Vite
- **Future:** LLM agent capabilities for application assistance

## Project Structure

```
job_app_helper/
├── backend/            # Flask API
│   ├── app.py          # App factory
│   ├── config.py       # Configuration
│   ├── database.py     # SQLAlchemy setup
│   ├── models/         # Database models
│   └── routes/         # API endpoints
├── frontend/           # React + Vite app
│   └── src/
├── main.py             # Backend entry point
└── pyproject.toml      # Python dependencies
```

## Setup

### Backend

```bash
# Install Python dependencies (requires uv)
uv sync

# Run the Flask server
uv run python main.py
```

The API will be available at `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server will be available at `http://localhost:3000` and proxies `/api` requests to the Flask backend.

## API Endpoints

| Method | Endpoint           | Description        |
| ------ | ------------------ | ------------------ |
| GET    | /api/jobs          | List all jobs      |
| POST   | /api/jobs          | Create a job       |
| GET    | /api/jobs/:id      | Get a job          |
| PATCH  | /api/jobs/:id      | Update a job       |
| DELETE | /api/jobs/:id      | Delete a job       |
