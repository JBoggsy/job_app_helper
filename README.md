# Shortlist

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> A desktop application and web app to track and manage job applications with an AI-powered assistant

Shortlist helps you organize your job search. Track applications through the hiring pipeline, store job details, and leverage an AI assistant that can search the web, scrape job postings, and automatically add jobs to your tracker—all through a simple chat interface. Available as a downloadable desktop app or as a web app you can run from source.

## Features

- **Job Tracking Dashboard**: Manage all your job applications in one place with sortable columns and status badges
- **AI-Powered Assistant**: Chat with an AI that can research jobs, scrape URLs, search job boards, and add jobs automatically
- **Multi-LLM Support**: Choose from Anthropic Claude, OpenAI GPT, Google Gemini, or run locally with Ollama
- **Web Search Integration**: Built-in web search (via Tavily) for finding job postings and company information
- **Job Board Integration**: Search Adzuna and JSearch job boards directly from the chat
- **User Profile System**: Personalized onboarding interview to understand your job preferences and goals
- **Resume Upload**: Upload your resume (PDF or DOCX) so the AI assistant can reference it for job fit evaluation and recommendations. An AI agent automatically cleans up PDF extraction artifacts and structures your resume into a rich, browsable format.
- **Rich Job Details**: Track salary ranges, location, remote type, requirements, contact info, and more
- **Job Fit Ratings**: Rate how well each job matches your profile (0-5 stars)
- **Guided Setup Wizard**: First-time setup walks you through choosing a provider and entering your API key, with inline step-by-step instructions for each key
- **Desktop App**: Download and install—no programming tools required. Also runs as a web app from source.

## Download

Download the latest desktop app from [GitHub Releases](https://github.com/JBoggsy/shortlist/releases):

| Platform | Download |
|----------|----------|
| **Windows** | `.exe` or `.msi` installer |
| **macOS** | `.dmg` installer |
| **Linux** | `.deb`, `.rpm`, or `.AppImage` |

Install it, launch it, and a setup wizard will guide you through choosing an AI provider and entering your API key — with inline instructions for every key. See the [Installation Guide](docs/INSTALLATION.md) for detailed step-by-step instructions.

### Run from Source (Alternative)

For developers or users who prefer running from source:

```bash
git clone https://github.com/JBoggsy/shortlist.git
cd shortlist
./start.sh        # Mac/Linux
start.bat          # Windows
```

**Requires:** Python 3.12+, Node.js 18+, uv. See [Installation Guide — Running from Source](docs/INSTALLATION.md#option-b-running-from-source-advanced) for full details.

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

## Configuration

### Using the Settings UI (Recommended)

The easiest way to configure the AI assistant is through the Settings panel:

1. **Open the app** — launch the desktop app, or go to http://localhost:3000 if running from source
2. **Click the Settings icon** (gear icon) in the top-right header
3. **Choose your LLM provider** from the dropdown (Anthropic Claude, OpenAI GPT, Google Gemini, or Ollama)
4. **Enter your API key** (if required - Ollama runs locally and doesn't need one)
5. **Click "Test Connection"** to verify your credentials work
6. **Click "Save Settings"** to persist your configuration

**Optional integrations** (enables additional features):
- **Tavily Search API (Recommended)**: Enables web search tool
- **JSearch API** (RapidAPI): Enables job board search (recommended)
- **Adzuna API**: Alternative job board search

> See the [Installation Guide](docs/INSTALLATION.md) for instructions on obtaining API keys.

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

See [`docs/config.example.json`](docs/config.example.json) for the complete configuration file format.

## Getting Started

1. **Download and install** — Get the app from [GitHub Releases](https://github.com/JBoggsy/shortlist/releases) (or [run from source](#run-from-source-alternative))
2. **Enter your API key** — On first launch, a setup wizard opens automatically. Choose an AI provider, follow the inline instructions to get your API key, and test the connection before continuing
3. **Complete onboarding** — The AI assistant will interview you to build your job search profile
4. **Add jobs manually** — Click "Add Job" to create entries from the dashboard
5. **Upload your resume** — Click the profile icon and upload your resume (PDF or DOCX). The AI assistant will reference it when evaluating job fit
6. **Use the AI assistant** — Click the chat icon to open the assistant panel:
   - Ask it to search for jobs: "Find software engineer jobs in San Francisco"
   - Scrape job postings: "Scrape this URL: https://example.com/job"
   - Research companies: "Search the web for info about Acme Corp"
   - The assistant will automatically add jobs to your tracker
7. **Track your progress** — Update job statuses (saved → applied → interviewing → offer/rejected)
8. **Manage your profile** — Click the profile icon to view or edit your job preferences

## Troubleshooting

### Desktop App Issues

**Windows SmartScreen warning**: Click "More info" → "Run anyway" (the app is not yet code-signed).

**macOS "unidentified developer"**: Go to System Settings → Privacy & Security → Click "Open Anyway".

**Blank screen on launch**: Wait a few seconds for the backend to start. If it persists, try restarting the app.

### General Issues

**"LLM is not configured"**: Click the Settings gear icon, select an LLM provider, enter your API key, and click Save Settings.

**Ollama connection failed**: Make sure Ollama is running separately (`ollama serve`) with a model pulled (`ollama pull llama3.2`).

### Run from Source Issues

**Dependencies not installed**: Install [Python 3.12+](https://www.python.org/downloads/), [Node.js 18+](https://nodejs.org/), and [uv](https://github.com/astral-sh/uv).

**Windows "Python was not found"**: Disable app execution aliases in Settings → Apps → Advanced app settings → App execution aliases.

**Port already in use**: Stop other processes using ports 3000/5000, or restart your computer.

**Missing dependencies after git pull**: Run `uv sync` and `cd frontend && npm install`.

### Need more help?

See the full [Troubleshooting guide](docs/INSTALLATION.md#troubleshooting) or report bugs at [GitHub Issues](https://github.com/JBoggsy/shortlist/issues).

## Tech Stack

- **Backend**: Python, Flask, SQLAlchemy, SQLite
- **Frontend**: React 19, Vite, Tailwind CSS 4
- **Desktop**: Tauri v2 (optional native wrapper, sidecar architecture)
- **AI Providers**: Anthropic Claude, OpenAI GPT, Google Gemini, Ollama
- **Package Managers**: uv (Python), npm (JavaScript)

## Desktop App

The desktop app is built with [Tauri v2](https://v2.tauri.app/), which wraps the React frontend in a native webview and bundles the Flask backend as a sidecar process. No Python or Node.js installation required.

Download the latest release from [GitHub Releases](https://github.com/JBoggsy/shortlist/releases). Data files are stored in platform-standard directories:

| Platform | Data Location |
|----------|---------------|
| **Linux** | `~/.local/share/com.shortlist.app/` |
| **macOS** | `~/Library/Application Support/com.shortlist.app/` |
| **Windows** | `C:\Users\<user>\AppData\Roaming\com.shortlist.app\` |

For building from source or developing the desktop app, see [DEVELOPMENT.md](docs/DEVELOPMENT.md#desktop-development-tauri).

## Development

For detailed technical documentation, development setup, API reference, and contribution guidelines, see:

- **[DEVELOPMENT.md](docs/DEVELOPMENT.md)** — Comprehensive developer guide
- **[CONTRIBUTING.md](docs/CONTRIBUTING.md)** — How to contribute to this project

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Tavily](https://tavily.com/) for web search API
- [Adzuna](https://www.adzuna.com/) and [JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) for job search APIs
- Built with [Flask](https://flask.palletsprojects.com/), [React](https://react.dev/), and [Tailwind CSS](https://tailwindcss.com/)
