# Installation Guide

Welcome! This guide will help you install and run the Shortlist on your computer. Don't worry if you're not familiar with programming—we'll walk through everything step by step.

## What You'll Need

- A computer running Windows, Mac, or Linux
- An internet connection
- An API key from at least one AI provider (we'll show you how to get these)

## Table of Contents

1. [Option A: Desktop App (Recommended)](#option-a-desktop-app-recommended)
2. [Getting Your API Keys](#getting-your-api-keys)
3. [First-Time Setup](#first-time-setup)
4. [Using the App](#using-the-app)
5. [Option B: Running from Source (Advanced)](#option-b-running-from-source-advanced)
6. [Troubleshooting](#troubleshooting)
7. [Updating the App](#updating-the-app)

---

## Option A: Desktop App (Recommended)

The easiest way to use Shortlist is to download the desktop app. No programming tools required—just download, install, and run.

### Step 1: Download

Go to the [GitHub Releases page](https://github.com/JBoggsy/shortlist/releases) and download the installer for your operating system:

| Platform | File to Download | Notes |
|----------|-----------------|-------|
| **Windows** | `.exe` or `.msi` | Choose `.msi` for a standard Windows installer |
| **macOS** | `.dmg` | Requires macOS 11 (Big Sur) or newer |
| **Linux (Debian/Ubuntu)** | `.deb` | For Debian-based distributions |
| **Linux (Fedora/RHEL)** | `.rpm` | For Red Hat-based distributions |
| **Linux (Other)** | `.AppImage` | Works on most Linux distributions |

### Step 2: Install

**Windows:**
1. Double-click the downloaded `.exe` or `.msi` file
2. If you see a "Windows protected your PC" (SmartScreen) warning, click **"More info"** then **"Run anyway"** — this appears because the app is not yet code-signed
3. Follow the installation prompts

**macOS:**
1. Double-click the downloaded `.dmg` file
2. Drag the app to your Applications folder
3. When you first open the app, you may see a warning that it's from an unidentified developer. Go to **System Settings → Privacy & Security** and click **"Open Anyway"**
   - This happens because the app is not yet code-signed with an Apple Developer certificate

**Linux (.deb):**
```bash
sudo dpkg -i shortlist_*.deb
```

**Linux (.rpm):**
```bash
sudo rpm -i shortlist-*.rpm
```

**Linux (.AppImage):**
```bash
chmod +x shortlist_*.AppImage
./shortlist_*.AppImage
```

### Step 3: Launch

1. Open the app from your Applications menu, Start menu, or desktop
2. On first launch, a **Setup Wizard** will open automatically to guide you through entering your API key — it includes step-by-step instructions for each provider, so you don't need to hunt for them separately
3. Continue to [First-Time Setup](#first-time-setup) below

---

## Getting Your API Keys

The Shortlist uses AI to help you find and track jobs. To use AI, you need an API key from at least one provider.

### Choose an AI Provider

You only need **one** of these, but you can set up multiple:

- **Anthropic Claude** (Recommended) - High quality, good for complex tasks
- **OpenAI GPT** - Popular and widely used
- **Google Gemini** - Good free tier available
- **Ollama** - Run AI models locally on your computer (no API key needed, but requires a powerful computer)

### Getting an Anthropic API Key (Recommended)

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Click "Sign Up" and create an account
3. Once logged in, click "API Keys" in the left sidebar
4. Click "Create Key"
5. Give it a name like "Shortlist"
6. Copy the key that appears (it starts with "sk-ant-")
7. **Important:** Save this key somewhere safe—you won't be able to see it again!

**Pricing:** Anthropic charges per usage. You'll get some free credits to start. Check [anthropic.com/pricing](https://www.anthropic.com/pricing) for current rates.

### Getting an OpenAI API Key

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Sign up or log in
3. Click your profile icon → "View API Keys"
4. Click "Create new secret key"
5. Copy the key (starts with "sk-")
6. Save it somewhere safe

**Pricing:** Check [openai.com/pricing](https://openai.com/pricing) for current rates.

### Getting a Google Gemini API Key

1. Go to [aistudio.google.com](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click "Get API key"
4. Click "Create API key"
5. Copy the key and save it

**Pricing:** Gemini has a generous free tier. Check [ai.google.dev/pricing](https://ai.google.dev/pricing) for details.

### Using Ollama (Local AI, No API Key)

If you have a powerful computer (16GB+ RAM recommended), you can run AI models locally:

1. Go to [ollama.com](https://ollama.com/)
2. Download and install Ollama for your operating system
3. Open a terminal and download a model:
   ```bash
   ollama pull llama3.2
   ```
4. No API key needed! Just set your provider to "ollama" in the configuration.

> **Note:** Even with the desktop app, Ollama must be running separately. Start it with `ollama serve` before using the app.

### Getting a Search API Key (Recommended)

The AI assistant can search the web for job information — this is one of its most useful features. It requires a Tavily API key:

1. Go to [tavily.com](https://tavily.com/)
2. Sign up for a free account
3. Go to your dashboard
4. Copy your API key
5. Save it somewhere safe

**Pricing:** Tavily offers a free tier with 1,000 searches/month.

### Getting Job Search API Keys (Optional)

For enhanced job searching, you can set up one of these:

**JSearch (Recommended if you want job search):**
1. Go to [rapidapi.com](https://rapidapi.com/)
2. Sign up for a free account
3. Search for "JSearch" API
4. Subscribe to the free tier
5. Go to "Endpoints" and copy your API key from the code examples
6. Save it somewhere safe

**Adzuna (Alternative):**
1. Go to [developer.adzuna.com](https://developer.adzuna.com/)
2. Click "Register"
3. Fill out the form
4. Check your email for your App ID and App Key
5. Save both somewhere safe

---

## First-Time Setup

When you open the app for the first time, a **Setup Wizard** will appear automatically. It walks you through four steps:

### Step 1 — Welcome

A brief introduction to the app. Click **"Continue →"** to proceed.

### Step 2 — Choose a Provider

Pick which AI service to use. You only need one:

- **Anthropic Claude** *(Recommended)* — High quality, great for complex tasks
- **OpenAI GPT** — Popular and widely used
- **Google Gemini** — Good free tier available
- **Ollama** *(Free)* — Runs locally on your machine; no API key needed, but requires a powerful computer (16GB+ RAM)

### Step 3 — Enter Your API Key

The wizard shows step-by-step instructions for getting a key from the provider you chose, with a direct link to the right page. You don't need to look anything up separately.

1. Follow the instructions shown in the wizard to get your API key
2. Paste the key into the input field
3. Click **"Test Connection"** to verify it works — you'll see a green success message
4. Click **"Continue →"** (only enabled after a successful test)

> **Ollama users**: No key needed. Just make sure Ollama is running (`ollama serve`) with a model pulled (`ollama pull llama3.2`), then click "Test Connection".

### Step 4 — Done

Click **"Meet Your AI Assistant →"** to go straight into the onboarding interview. Or click "Skip for now" if you want to explore the app first and do the interview later.

### Onboarding Interview

After completing the wizard, the AI Assistant chat panel will open and interview you about your job search preferences.

**What to Expect:**

The AI will ask questions like:
- What types of roles are you looking for?
- What industries interest you?
- What skills do you have?
- What's your experience level?
- What are your salary expectations?
- Where are you located? Are you open to remote work?

**How to Respond:**

1. Type your answers in the chat box at the bottom
2. Be as detailed or brief as you like—the AI will adapt
3. You can skip questions by saying "skip" or "I'd rather not say"
4. The AI will use this information to help you find relevant jobs later

**Completing Onboarding:**

1. Answer the questions naturally—there are no wrong answers
2. When you've answered enough questions, the AI will thank you and save your profile
3. The onboarding is complete, and you can start using the app!

### Editing Settings or Profile Later

**To change your API keys or provider:**
1. Click the "Settings" button (gear icon) in the top navigation
2. Update any fields you want to change — each key field has a collapsible **"How do I get this key?"** guide built in
3. Click "Save Settings"

**To view or edit your job search profile:**
1. Click the "Profile" button in the top navigation
2. View your saved information
3. Click "Edit Profile" to make changes
4. Click "Save" when done

**To upload your resume:**
1. Click the "Profile" button in the top navigation
2. In the **Resume** section at the top, click **Upload** (or **Replace** if you already have one)
3. Select a PDF or DOCX file from your computer
4. The file will be parsed and stored — click **Preview** to verify the extracted text
5. The AI assistant will automatically reference your resume when evaluating job fit

---

## Using the App

Now that you're set up, here's how to get started:

1. **Add your first job:** Click "Add Job" to manually track a position you're interested in
2. **Try the AI assistant:** Click "Chat" and ask it to find jobs for you — try something like "Find software engineer jobs in San Francisco" or "Scrape this job posting: [paste a URL]"
3. **Track your progress:** Update job statuses as you move through the pipeline (saved → applied → interviewing → offer/rejected)
4. **Upload your resume:** Click the Profile button and use the resume section at the top to upload a PDF or DOCX file. The AI assistant will reference your resume when evaluating job fit and searching for jobs
5. **Manage your profile:** Click the Profile button to view or update your job preferences — the AI uses this to give you better recommendations
6. **Get help:** Click the "?" button in the header for built-in guides and tips

---

## Option B: Running from Source (Advanced)

If you prefer to run the application from source code (for development or customization), follow the steps below. This requires installing Python, Node.js, and other developer tools.

> **Note:** Most users should use [Option A: Desktop App](#option-a-desktop-app-recommended) instead. Running from source is intended for developers or users who want to modify the code.

### Prerequisites

You need to install three programs before you can run the Shortlist.

#### Install Python (3.12 or newer)

Python is the programming language that powers the backend of this application.

**Windows:**
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Scroll down past the big yellow button and find the **"Windows installer (64-bit)"** link under the latest stable release — this is the standalone installer. (The big yellow button sometimes downloads the wrong version or redirects to the Microsoft Store.)
3. Run the downloaded installer
4. **Important:** Check the box that says "Add Python to PATH" before clicking Install
5. Click "Install Now"

**Mac:**
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the yellow "Download Python 3.12" button
3. Open the downloaded .pkg file and follow the installation steps

**Linux (Ubuntu/Debian):**
Open a terminal and run:
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

**Verify Python is installed:**
Open a terminal/command prompt and type:
```bash
python --version
```
You should see something like "Python 3.12.x"

#### Install Node.js and npm

Node.js and npm are needed to run the web interface.

1. Go to [nodejs.org](https://nodejs.org/)
2. Click the big green "Get Node.js" button
3. Click the "Windows Installer" or "macOS Installer" depending on your OS
4. Run the installer and follow the default options
5. Verify installation by opening a terminal/command prompt and typing:
```bash
node --version
npm --version
```

#### Install uv (Python Package Manager)

uv is a fast tool for managing Python dependencies.

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Mac/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installing, close and reopen your terminal, then verify:
```bash
uv --version
```

#### Install Git (Optional but Recommended)

Git helps you download and update the code easily.

1. Go to [git-scm.com/downloads](https://git-scm.com/downloads)
2. Download the installer for your operating system
3. Run the installer with default settings

### Downloading the Code

#### Using Git (Recommended)

1. Open a terminal/command prompt
2. Navigate to where you want to store the app. For example:
   ```bash
   cd Documents
   ```
3. Download the code:
   ```bash
   git clone https://github.com/JBoggsy/shortlist.git
   ```
4. Go into the new folder:
   ```bash
   cd shortlist
   ```

#### Download as ZIP (Alternative)

1. Go to the [GitHub repository](https://github.com/JBoggsy/shortlist) in your web browser
2. Click the green "Code" button
3. Click "Download ZIP"
4. Extract the ZIP file to a location you'll remember (like Documents)
5. Open a terminal/command prompt and navigate to the extracted folder:
   ```bash
   cd Documents/shortlist-main
   ```

### Running the Application

We've made this easy! There's a single command that starts everything automatically.

**Windows:**
1. Open a command prompt or PowerShell
2. Navigate to the shortlist folder:
   ```bash
   cd path\to\shortlist
   ```
3. Run the start script:
   ```bash
   start.bat
   ```

**Mac/Linux:**
1. Open a terminal
2. Navigate to the shortlist folder:
   ```bash
   cd path/to/shortlist
   ```
3. Run the start script:
   ```bash
   ./start.sh
   ```
   (If you get a "permission denied" error, run `chmod +x start.sh` first)

The script will:
- Check that Python, Node.js, and uv are installed
- Install any missing dependencies automatically
- Start both the backend and frontend servers
- Automatically open your browser to [http://localhost:3000](http://localhost:3000)

Press **Ctrl+C** in the terminal when you want to stop the app.

#### Manual Method

If you prefer to start the backend and frontend separately:

1. **Backend:** In one terminal, run:
   ```bash
   cd path/to/shortlist
   uv run python main.py
   ```

2. **Frontend:** In another terminal, run:
   ```bash
   cd path/to/shortlist/frontend
   npm run dev
   ```

3. **Browser:** Go to [http://localhost:3000](http://localhost:3000)

### Running Again Later

Just run the start script again — it handles everything automatically:

**Windows:**
```bash
cd path\to\shortlist
start.bat
```

**Mac/Linux:**
```bash
cd path/to/shortlist
./start.sh
```

After starting, continue to [First-Time Setup](#first-time-setup) to configure the app via the setup wizard.

---

## Troubleshooting

### Desktop App Issues

#### Windows SmartScreen warning

**Problem:** When installing, you see "Windows protected your PC."

**Solution:** Click **"More info"** then **"Run anyway"**. This warning appears because the app is not yet code-signed. It's safe to proceed.

#### macOS "unidentified developer" warning

**Problem:** macOS won't open the app, showing a security warning.

**Solution:**
1. Go to **System Settings → Privacy & Security**
2. Scroll down and click **"Open Anyway"** next to the message about the app
3. The app will open normally from now on

#### Linux AppImage won't run

**Problem:** The `.AppImage` file doesn't launch when double-clicked.

**Solution:** Make it executable first:
```bash
chmod +x shortlist_*.AppImage
./shortlist_*.AppImage
```

#### Desktop app shows blank screen

**Problem:** The app window opens but shows nothing.

**Solution:**
- Wait a few seconds — the backend may still be starting up
- Try closing and reopening the app
- Check if your antivirus/firewall is blocking the app
- If the issue persists, try [running from source](#option-b-running-from-source-advanced) instead

#### API key errors

**Problem:** You see "Invalid API key" or "Authentication failed" errors.

**Solution:**
- Double-check that you copied the full API key (no extra spaces)
- Open Settings and use the "Test Connection" button to verify your configuration
- Verify your API key is still valid (check the provider's dashboard)
- Make sure you have credits/quota remaining with your AI provider
- If you just signed up, some providers take a few minutes to activate new API keys

### Run from Source Issues

#### "Command not found" errors

**Problem:** When you try to run `python`, `npm`, or `uv`, you get a "command not found" error.

**Solution:**
- Make sure you installed the software correctly (see [Prerequisites](#prerequisites))
- Close and reopen your terminal after installing
- On Windows, make sure you checked "Add to PATH" during Python installation
- Try `python3` instead of `python` on Mac/Linux

#### Port already in use

**Problem:** You see an error like "Port 5000 is already in use" or "Port 3000 is already in use"

**Solution:**
- You might already have the app running in another terminal
- Close other terminals running the app
- On Windows, restart your computer
- On Mac/Linux, find and kill the process using that port:
  ```bash
  # For port 5000
  lsof -ti:5000 | xargs kill -9
  # For port 3000
  lsof -ti:3000 | xargs kill -9
  ```

#### Frontend shows blank page

**Problem:** The browser loads but shows nothing or shows an error.

**Solution:**
- Make sure both the backend AND frontend are running (you should have two terminal windows open)
- Check the backend terminal for errors
- Try refreshing the browser (press F5 or Cmd+R)
- Clear your browser cache
- Try a different browser

#### Installation fails during `uv sync` or `npm install`

**Problem:** You get errors when installing dependencies.

**Solution:**
- Make sure you have a stable internet connection
- On Windows, try running the terminal as Administrator
- Delete the `.venv` folder (if it exists) and the `frontend/node_modules` folder, then try again
- Update uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (Mac/Linux) or reinstall from the website (Windows)

#### Windows: "Python was not found" but it's installed

**Problem:** Running `python --version` says "Python was not found" or opens the Microsoft Store.

**Solution:**
1. Open **Settings → Apps → Advanced app settings → App execution aliases**
2. Turn **OFF** both `python.exe` and `python3.exe` aliases
3. Close and reopen your terminal
4. Run `start.bat` again

#### Windows: "uv is not recognized" after installation

**Problem:** The script says it installed `uv` but then says "uv is not recognized."

**Solution:** Restart your Command Prompt/PowerShell and run `start.bat` again. The script automatically uses `python -m uv` as a fallback.

### General Issues

#### AI responses are very slow

**Problem:** The AI takes a long time to respond.

**Solution:**
- This is normal for some providers, especially with free tiers
- Consider switching to a different provider
- If using Ollama, make sure you have enough RAM and a good CPU/GPU
- Check your internet connection

#### Setup wizard doesn't open automatically

**Problem:** The setup wizard doesn't appear when you first launch the app.

**Solution:**
- Click the "Settings" button (gear icon) in the top navigation bar to configure the app manually
- Try refreshing the browser page (if running from source)
- Check the browser console for errors (press F12, click "Console" tab)

#### Ollama connection failed

**Problem:** Can't connect to Ollama for local LLM.

**Solution:**
1. Make sure Ollama is installed: [ollama.com](https://ollama.com/)
2. Start the Ollama server: `ollama serve`
3. Pull a model: `ollama pull llama3.2`
4. In Settings, select "Ollama (Local)" as your provider

> **Note:** Even with the desktop app, Ollama must be running as a separate process.

---

## Updating the App

### Desktop App

The desktop app **checks for updates automatically** on startup. When a new version is available, you'll see a banner at the top of the app with the new version number. Click "Update Now" to download and install, then "Restart Now" to apply the update.

If you prefer to update manually:

1. Go to the [GitHub Releases page](https://github.com/JBoggsy/shortlist/releases)
2. Download the latest installer for your platform
3. Install it over the existing version — your data (jobs, profile, settings) is preserved because it's stored in a separate data directory

### Running from Source

```bash
cd path/to/shortlist

# Pull latest code
git pull

# Update backend dependencies
uv sync

# Update frontend dependencies
cd frontend && npm install
```

Then restart the app with `./start.sh` or `start.bat`.

---

## Getting Help

If you run into issues not covered here:

1. Check the built-in help panel (click the "?" button in the app header)
2. Check the `logs/app.log` file for error messages (in the app folder for source installs, or in your system's app data directory for desktop installs)
3. Open an issue on the [GitHub repository](https://github.com/JBoggsy/shortlist/issues) with:
   - Whether you're using the desktop app or running from source
   - What you were trying to do
   - What error message you saw
   - Your operating system
   - Screenshots if applicable
