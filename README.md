# Job Application Helper

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> A web application to track and manage job applications with an AI-powered assistant

Job Application Helper is a full-stack web app that helps you organize your job search. Track applications through the hiring pipeline, store job details, and leverage an AI assistant that can search the web, scrape job postings, and automatically add jobs to your tracker—all through a simple chat interface.

## Features

- **Job Tracking Dashboard**: Manage all your job applications in one place with sortable columns and status badges
- **AI-Powered Assistant**: Chat with an AI that can research jobs, scrape URLs, search job boards, and add jobs automatically
- **Multi-LLM Support**: Choose from Anthropic Claude, OpenAI GPT, Google Gemini, or run locally with Ollama
- **Web Search Integration**: Built-in web search (via Tavily) for finding job postings and company information
- **Job Board Integration**: Search Adzuna and JSearch job boards directly from the chat
- **User Profile System**: Personalized onboarding interview to understand your job preferences and goals
- **Rich Job Details**: Track salary ranges, location, remote type, requirements, contact info, and more
- **Job Fit Ratings**: Rate how well each job matches your profile (0-5 stars)

## Screenshots

### Dashboard
Manage all your job applications in one place with sortable columns, status badges, and quick actions.

![Job List Dashboard](docs/screenshots/dashboard.png)

### AI Assistant
Chat with the AI assistant to search for jobs, scrape URLs, and get personalized recommendations. The assistant uses tools like web search and job board APIs to help you find opportunities.

![Chat Panel: Searching for Jobs](docs/screenshots/chat-panel.png)

![Chat Panel: Adding a Job to the Tracker](docs/screenshots/chat-panel-2.png)

### Job Details
View comprehensive job information including requirements, nice-to-haves, salary, location, and job fit ratings.

![Job Detail Panel](docs/screenshots/job-detail.png)

### Add/Edit Jobs
Easily add new jobs or update existing ones with a clean, comprehensive form.

![Job Form](docs/screenshots/job-form.png)

### User Profile
Manage your job search profile with preferences, skills, and goals. The AI uses this to personalize recommendations.

![Profile Panel](docs/screenshots/profile-panel.png)

### Onboarding
First-time users go through a friendly interview to build their profile.

![Onboarding Flow](docs/screenshots/onboarding.png)

## Quick Start

### Easy Setup (Recommended)

The easiest way to get started is with our one-command startup script:

1. **Clone the repository**:

```bash
git clone https://github.com/JBoggsy/job_app_helper.git
cd job_app_helper
```

2. **Run the startup script**:

**On Mac/Linux:**
```bash
./start.sh
```

**On Windows:**
```bash
start.bat
```

That's it! The script will:
- ✅ Check if Python, Node.js, and uv are installed (and guide you if not)
- ✅ Install all dependencies automatically
- ✅ Start both backend and frontend servers
- ✅ Open your browser to http://localhost:3000

When you first open the app, configure your LLM API key by clicking the **Settings** (gear icon) in the header.

### Manual Setup (Advanced)

If you prefer to set things up manually or need more control:

#### Prerequisites

- **Python 3.12+** — [Download](https://www.python.org/downloads/)
- **Node.js 18+** — [Download](https://nodejs.org/)
- **uv** — [Install](https://github.com/astral-sh/uv): `pip install uv`

#### Installation Steps

1. **Clone the repository**:

```bash
git clone https://github.com/JBoggsy/job_app_helper.git
cd job_app_helper
```

2. **Set up the backend**:

```bash
# Install Python dependencies
uv sync

# Run the Flask server
uv run python main.py
```

The backend API will be available at `http://localhost:5000`.

3. **Set up the frontend** (in a new terminal):

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`.

## Configuration

### Using the Settings UI (Recommended)

The easiest way to configure the AI assistant is through the Settings panel:

1. **Open the app** in your browser (http://localhost:3000)
2. **Click the Settings icon** (gear icon) in the top-right header
3. **Choose your LLM provider** from the dropdown (Anthropic Claude, OpenAI GPT, Google Gemini, or Ollama)
4. **Enter your API key** (if required - Ollama runs locally and doesn't need one)
5. **Click "Test Connection"** to verify your credentials work
6. **Click "Save Settings"** to persist your configuration

**Optional integrations** (enables additional features):
- **Tavily Search API**: Enables web search tool
- **JSearch API** (RapidAPI): Enables job board search (recommended)
- **Adzuna API**: Alternative job board search

All settings are saved to a local `config.json` file and persist across restarts.

### Available LLM Providers

| Provider | Default Model | API Key Required | Get API Key |
|----------|---------------|------------------|-------------|
| Anthropic Claude | `claude-sonnet-4-5-20250929` | Yes | [console.anthropic.com](https://console.anthropic.com/) |
| OpenAI GPT | `gpt-4o` | Yes | [platform.openai.com](https://platform.openai.com/) |
| Google Gemini | `gemini-2.0-flash` | Yes | [aistudio.google.com](https://aistudio.google.com/) |
| Ollama (Local) | `llama3.1` | No | [ollama.com](https://ollama.com/) |

### Advanced: Environment Variables

For advanced users or automated deployments, you can also configure via environment variables (these override the Settings UI):

```bash
# LLM Configuration
export LLM_PROVIDER=anthropic
export LLM_API_KEY=your-api-key-here
export LLM_MODEL=custom-model-name  # optional

# Optional Integrations
export SEARCH_API_KEY=your-tavily-key
export JSEARCH_API_KEY=your-rapidapi-key

# Logging
export LOG_LEVEL=INFO
```

See `config.example.json` for the complete configuration file format.

## Usage

1. **Start the application** — Follow the Quick Start steps above
2. **Open your browser** — Navigate to `http://localhost:3000`
3. **Complete onboarding** — On first visit, the AI assistant will interview you to build your profile
4. **Add jobs manually** — Click "Add Job" to create entries from the dashboard
5. **Use the AI assistant** — Click the chat icon to open the assistant panel:
   - Ask it to search for jobs: "Find software engineer jobs in San Francisco"
   - Scrape job postings: "Scrape this URL: https://example.com/job"
   - Research companies: "Search the web for info about Acme Corp"
   - The assistant will automatically add jobs to your tracker
6. **Track your progress** — Update job statuses (saved → applied → interviewing → offer/rejected)
7. **Manage your profile** — Click the profile icon to view or edit your job preferences

## Troubleshooting

### "LLM is not configured" error

**Problem**: The AI assistant shows "LLM is not configured" when you try to use it.

**Solution**:
1. Click the **Settings** (gear icon) in the header
2. Select an LLM provider and enter your API key
3. Click **Test Connection** to verify it works
4. Click **Save Settings**

### Dependencies not installed

**Problem**: The startup script says Python, Node.js, or uv is not installed.

**Solution**:
- **Python**: Download from [python.org](https://www.python.org/downloads/) (need 3.12+)
- **Node.js**: Download from [nodejs.org](https://nodejs.org/) (need 18+)
- **uv**: Run `pip install uv` or see [installation guide](https://github.com/astral-sh/uv)

### Port already in use

**Problem**: "Address already in use" error on port 3000 or 5000.

**Solution**:
- Stop any other processes using those ports
- Or change the ports in `vite.config.js` (frontend) and `main.py` (backend)

### Ollama connection failed

**Problem**: Can't connect to Ollama for local LLM.

**Solution**:
1. Make sure Ollama is installed: [ollama.com](https://ollama.com/)
2. Start the Ollama server: `ollama serve`
3. Pull a model: `ollama pull llama3.1`
4. In Settings, select "Ollama (Local)" as your provider

### AI assistant not responding

**Problem**: Messages sent to the AI don't get responses.

**Solution**:
1. Check the browser console (F12) for errors
2. Check the backend terminal for error messages
3. Verify your API key is correct in Settings
4. Try the "Test Connection" button in Settings
5. Check your internet connection (for cloud providers)

### Missing dependencies after git pull

**Problem**: App won't start after pulling latest changes.

**Solution**:
```bash
# Reinstall backend dependencies
uv sync

# Reinstall frontend dependencies
cd frontend && npm install
```

### Need more help?

- Check the [DEVELOPMENT.md](DEVELOPMENT.md) for technical details
- Report bugs at [GitHub Issues](https://github.com/JBoggsy/job_app_helper/issues)
- See logs in `logs/app.log` for backend errors

## Tech Stack

- **Backend**: Python, Flask, SQLAlchemy, SQLite
- **Frontend**: React 19, Vite, Tailwind CSS 4
- **AI Providers**: Anthropic Claude, OpenAI GPT, Google Gemini, Ollama
- **Package Managers**: uv (Python), npm (JavaScript)

## Development

For detailed technical documentation, development setup, API reference, and contribution guidelines, see:

- **[DEVELOPMENT.md](DEVELOPMENT.md)** — Comprehensive developer guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — How to contribute to this project

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Tavily](https://tavily.com/) for web search API
- [Adzuna](https://www.adzuna.com/) and [JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) for job search APIs
- Built with [Flask](https://flask.palletsprojects.com/), [React](https://react.dev/), and [Tailwind CSS](https://tailwindcss.com/)
