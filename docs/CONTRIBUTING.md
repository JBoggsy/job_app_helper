# Contributing to Job Application Helper

Thank you for your interest in contributing to Job Application Helper! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Code Style Guidelines](#code-style-guidelines)
- [Commit Message Conventions](#commit-message-conventions)

## Code of Conduct

This project follows a simple code of conduct: be respectful, constructive, and professional in all interactions. We're here to build something useful together.

## How Can I Contribute?

There are several ways to contribute:

- **Report bugs**: Found a bug? Let us know!
- **Suggest features**: Have an idea? We'd love to hear it!
- **Improve documentation**: Help make our docs clearer
- **Write code**: Fix bugs or implement new features
- **Review pull requests**: Provide feedback on proposed changes

## Reporting Bugs

Before submitting a bug report:

1. **Check existing issues**: Search [GitHub Issues](../../issues) to see if it's already reported
2. **Use the latest version**: Make sure you're running the latest code
3. **Reproduce the bug**: Verify the bug is consistent and reproducible

When submitting a bug report, use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:

- **Clear description**: What happened vs. what you expected
- **Steps to reproduce**: Detailed steps to recreate the issue
- **Environment**: OS, Python version, Node version, LLM provider
- **Screenshots/logs**: Visual evidence or error logs when relevant

**Example:**

```
**Bug**: Chat panel doesn't scroll to new messages

**Steps to reproduce**:
1. Open chat panel
2. Send a long message that requires scrolling
3. Notice the panel doesn't auto-scroll to the new message

**Environment**: macOS 14.1, Python 3.12, Node 18.17, Anthropic provider

**Expected**: Chat panel should auto-scroll to show the latest message
**Actual**: User must manually scroll down
```

## Suggesting Features

Before suggesting a feature:

1. **Check existing issues**: See if it's already been suggested
2. **Consider scope**: Does it fit the project's goals?
3. **Think about users**: Would others benefit from this?

When suggesting a feature, use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md) and include:

- **Problem**: What problem does this solve?
- **Proposed solution**: How would you implement it?
- **Alternatives**: What other approaches did you consider?
- **Additional context**: Use cases, examples, mockups

**Example:**

```
**Feature**: Export jobs to CSV

**Problem**: Users want to analyze their job search data in spreadsheet tools

**Solution**: Add an "Export CSV" button that downloads all jobs as a CSV file

**Alternatives**:
- JSON export (more developer-focused)
- Direct integration with Google Sheets (more complex)

**Use case**: A user wants to create custom charts of their application success rate
```

## Development Setup

For detailed development setup instructions, see [DEVELOPMENT.md](DEVELOPMENT.md). Here's a quick overview:

### Prerequisites

- Python 3.12+
- Node.js 18+
- uv (Python package manager)
- npm (JavaScript package manager)
- Rust toolchain (only if working on the Tauri desktop wrapper)

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/job_app_helper.git
cd job_app_helper

# Backend setup
uv sync
export LLM_PROVIDER=anthropic
export LLM_API_KEY=your-api-key
uv run python main.py

# Frontend setup (in a new terminal)
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend tests (when available)
uv run pytest

# Frontend tests (when available)
cd frontend
npm run test
```

## Pull Request Process

1. **Fork the repository** and create a branch from `main`:

```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes**:
   - Follow the [Code Style Guidelines](#code-style-guidelines)
   - Write clear, focused commits
   - Add/update tests if applicable
   - Update documentation if needed

3. **Verify your changes work**:

```bash
# Backend: Run the server and test manually
uv run python main.py

# Frontend: Verify it builds without errors
cd frontend
npm run build

# Desktop (if you changed Tauri/sidecar code): Verify Tauri dev mode works
npm run tauri:dev
```

4. **Commit your changes**:

```bash
git add .
git commit -m "feat: add CSV export for jobs"
```

5. **Push to your fork**:

```bash
git push origin feature/your-feature-name
```

6. **Open a pull request**:
   - Use the [Pull Request template](.github/PULL_REQUEST_TEMPLATE.md)
   - Provide a clear description of what changed and why
   - Link related issues (e.g., "Closes #42")
   - Fill out the checklist

7. **Respond to feedback**:
   - Address review comments promptly
   - Push additional commits to the same branch
   - Mark conversations as resolved when addressed

### Pull Request Checklist

Before submitting, ensure:

- [ ] Code follows style guidelines
- [ ] Changes have been tested locally
- [ ] Documentation has been updated (README, DEVELOPMENT.md, CLAUDE.md if applicable)
- [ ] Commit messages are clear and descriptive
- [ ] No secrets or API keys are committed
- [ ] Frontend builds successfully (`npm run build`)

## Code Style Guidelines

### Python (Backend)

- **Follow PEP 8**: Use standard Python style conventions
- **Type hints**: Add type hints to function parameters and return values
- **Docstrings**: Document complex functions with docstrings
- **Imports**: Group imports (standard library, third-party, local) with blank lines between groups
- **Line length**: Keep lines under 100 characters when practical

**Example:**

```python
from typing import Optional
from backend.database import db
from backend.models import Job

def get_job_by_id(job_id: int) -> Optional[Job]:
    """
    Retrieve a job by its ID.

    Args:
        job_id: The job's primary key

    Returns:
        Job object if found, None otherwise
    """
    return Job.query.get(job_id)
```

### JavaScript/React (Frontend)

- **Functional components**: Use functional components with hooks (no class components)
- **ESLint**: Follow project's ESLint configuration
- **Consistent naming**:
  - Components: `PascalCase` (e.g., `JobForm`)
  - Functions: `camelCase` (e.g., `fetchJobs`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `API_BASE_URL`)
- **Props**: Destructure props in function parameters
- **Tailwind CSS**: Use utility classes for styling (no separate CSS files)

**Example:**

```javascript
import { useState, useEffect } from 'react';
import { fetchJobs } from '../api';

export default function JobList({ onJobSelect }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadJobs() {
      const data = await fetchJobs();
      setJobs(data);
      setLoading(false);
    }
    loadJobs();
  }, []);

  if (loading) return <div className="text-gray-500">Loading...</div>;

  return (
    <div className="space-y-4">
      {jobs.map(job => (
        <JobCard key={job.id} job={job} onClick={() => onJobSelect(job)} />
      ))}
    </div>
  );
}
```

### General Guidelines

- **Keep changes focused**: One feature or fix per PR
- **Prefer editing over creating**: Edit existing files rather than creating new ones when possible
- **No console.log**: Remove debugging statements before committing
- **Error handling**: Handle errors gracefully and provide user-friendly messages
- **Security**: Never commit API keys, passwords, or sensitive data

## Commit Message Conventions

Use clear, descriptive commit messages that explain what changed and why:

### Format

```
type: short description

Optional longer explanation of the change.

Closes #123
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring (no feature or bug fix)
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build config)

### Examples

**Good:**

```
feat: add CSV export for jobs

Add an "Export CSV" button to the job list that downloads all jobs
as a CSV file with all fields included.

Closes #42
```

```
fix: resolve chat panel scrolling issue

The chat panel now auto-scrolls to the latest message when a new
message is received via SSE streaming.

Closes #58
```

**Bad:**

```
Update code
```

```
Fixed bug
```

```
Changes
```

## Questions?

If you have questions about contributing, feel free to:

- Open a [GitHub Discussion](../../discussions)
- Ask in an existing issue
- Reach out to the maintainers

Thank you for contributing to Job Application Helper!
