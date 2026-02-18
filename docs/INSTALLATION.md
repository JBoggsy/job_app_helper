# Installation Guide

Welcome! This guide will help you install and run the Job Application Helper on your computer. Don't worry if you're not familiar with programming—we'll walk through everything step by step.

## What You'll Need

- A computer running Windows, Mac, or Linux
- An internet connection
- About 30 minutes to complete the setup
- An API key from at least one AI provider (we'll show you how to get these)

## Table of Contents

1. [Installing Required Software](#step-1-installing-required-software)
2. [Downloading the Code](#step-2-downloading-the-code)
3. [Getting Your API Keys](#step-3-getting-your-api-keys)
4. [Setting Up the Application](#step-4-setting-up-the-application)
5. [Running the Application](#step-5-running-the-application)
6. [First-Time Setup](#step-6-first-time-setup)
7. [Accessing the App Later](#step-7-accessing-the-app-later)
8. [Troubleshooting](#troubleshooting)

---

## Step 1: Installing Required Software

You need to install three programs before you can run the Job Application Helper.

### 1.1 Install Python (3.12 or newer)

Python is the programming language that powers the backend of this application.

**Windows:**
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download the **standalone installer** which is linked beneaththe big yellow button. Avoid the big
   yellow button itself.
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

### 1.2 Install Node.js and npm

Node.js and npm are needed to run the web interface.

1. Go to [nodejs.org](https://nodejs.org/)
2. Click the big green "Get Node.js" button
3. Click the green "Windows Installer" or "macOS Installer" depending on your OS
3. Run the installer and follow the default options
4. Verify installation by opening a terminal/command prompt and typing:
```bash
node --version
npm --version
```

### 1.3 Install uv (Python Package Manager)

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

### 1.4 Install Git (Optional but Recommended)

Git helps you download and update the code easily.

1. Go to [git-scm.com/downloads](https://git-scm.com/downloads)
2. Download the installer for your operating system
3. Run the installer with default settings

---

## Step 2: Downloading the Code

Now let's get the Job Application Helper code onto your computer.

### Option A: Using Git (Recommended)

1. Open a terminal/command prompt
2. Navigate to where you want to store the app. For example:
   ```bash
   cd Documents
   ```
3. Download the code:
   ```bash
   git clone https://github.com/YOUR-USERNAME/job_app_helper.git
   ```
   (Replace `YOUR-USERNAME` with the actual GitHub username or organization)
4. Go into the new folder:
   ```bash
   cd job_app_helper
   ```

### Option B: Download as ZIP (Alternative)

1. Go to the GitHub repository in your web browser
2. Click the green "Code" button
3. Click "Download ZIP"
4. Extract the ZIP file to a location you'll remember (like Documents)
5. Open a terminal/command prompt and navigate to the extracted folder:
   ```bash
   cd Documents/job_app_helper-main
   ```

---

## Step 3: Getting Your API Keys

The Job Application Helper uses AI to help you find and track jobs. To use AI, you need an API key from at least one provider.

### 3.1 Choose an AI Provider

You only need **one** of these, but you can set up multiple:

- **Anthropic Claude** (Recommended) - High quality, good for complex tasks
- **OpenAI GPT** - Popular and widely used
- **Google Gemini** - Good free tier available
- **Ollama** - Run AI models locally on your computer (no API key needed, but requires a powerful computer)

### 3.2 Getting an Anthropic API Key (Recommended)

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Click "Sign Up" and create an account
3. Once logged in, click "API Keys" in the left sidebar
4. Click "Create Key"
5. Give it a name like "Job App Helper"
6. Copy the key that appears (it starts with "sk-ant-")
7. **Important:** Save this key somewhere safe—you won't be able to see it again!

**Pricing:** Anthropic charges per usage. You'll get some free credits to start. Check [anthropic.com/pricing](https://www.anthropic.com/pricing) for current rates.

### 3.3 Getting an OpenAI API Key

1. Go to [platform.openai.com](https://platform.openai.com/)
2. Sign up or log in
3. Click your profile icon → "View API Keys"
4. Click "Create new secret key"
5. Copy the key (starts with "sk-")
6. Save it somewhere safe

**Pricing:** Check [openai.com/pricing](https://openai.com/pricing) for current rates.

### 3.4 Getting a Google Gemini API Key

1. Go to [aistudio.google.com](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click "Get API key"
4. Click "Create API key"
5. Copy the key and save it

**Pricing:** Gemini has a generous free tier. Check [ai.google.dev/pricing](https://ai.google.dev/pricing) for details.

### 3.5 Using Ollama (Local AI, No API Key)

If you have a powerful computer (16GB+ RAM recommended), you can run AI models locally:

1. Go to [ollama.ai](https://ollama.ai/)
2. Download and install Ollama for your operating system
3. Open a terminal and download a model:
   ```bash
   ollama pull llama3.2
   ```
4. No API key needed! Just set your provider to "ollama" in the configuration.

### 3.6 Getting a Search API Key

The AI assistant can search the web for job information. This requires a Tavily API key:

1. Go to [tavily.com](https://tavily.com/)
2. Sign up for a free account
3. Go to your dashboard
4. Copy your API key
5. Save it somewhere safe

**Pricing:** Tavily offers a free tier with 1,000 searches/month.

### 3.7 Getting Job Search API Keys (Optional)

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

## Step 4: Setting Up the Application

Now we'll install all the necessary components.

### 4.1 Install Python Dependencies

1. Make sure you're in the job_app_helper folder:
   ```bash
   cd job_app_helper
   ```
2. Install Python packages:
   ```bash
   uv sync
   ```
   This will take a few minutes as it downloads everything needed.

### 4.2 Install Frontend Dependencies

1. Navigate to the frontend folder:
   ```bash
   cd frontend
   ```
2. Install JavaScript packages:
   ```bash
   npm install
   ```
   This will also take a few minutes.
3. Go back to the main folder:
   ```bash
   cd ..
   ```

**Note:** You don't need to create any configuration files manually. The app will create a `config.json` file automatically, and you'll enter your settings through a user-friendly interface in the next step!

---

## Step 5: Running the Application

We've made this easy! There's a single command that starts everything automatically.

### 5.1 Start the Application

**Windows:**
1. Open a command prompt or PowerShell
2. Navigate to the job_app_helper folder:
   ```bash
   cd path\to\job_app_helper
   ```
   (Replace `path\to` with the actual location, e.g., `cd Documents\job_app_helper`)
3. Run the start script:
   ```bash
   start.bat
   ```
4. The script will:
   - Check that Python, Node.js, and uv are installed
   - Install any missing dependencies automatically
   - Start the backend in a new window
   - Start the frontend in another new window
   - Automatically open your browser to [http://localhost:3000](http://localhost:3000)
6. Press **Ctrl+C** in the terminal when you want to stop the app

**Mac/Linux:**
1. Open a terminal
2. Navigate to the job_app_helper folder:
   ```bash
   cd path/to/job_app_helper
   ```
   (Replace `path/to` with the actual location, e.g., `cd Documents/job_app_helper`)
3. Run the start script:
   ```bash
   ./start.sh
   ```
   (If you get a "permission denied" error, run `chmod +x start.sh` first)
4. The script will:
   - Check that Python, Node.js, and uv are installed
   - Install any missing dependencies automatically
   - Start both the backend and frontend
   - Automatically open your browser to [http://localhost:3000](http://localhost:3000)
5. You'll see a nice startup message:
   ```
   ╔═══════════════════════════════════════╗
   ║          🚀 App is running!          ║
   ╚═══════════════════════════════════════╝
   ```
6. Press **Ctrl+C**/**Cmd+C** in the terminal when you want to stop the app

### 5.2 What to Expect

- Two windows will open (Windows) or one terminal will show both processes (Mac/Linux)
- Your browser will automatically open to the app
- If your browser doesn't open automatically, go to [http://localhost:3000](http://localhost:3000) manually

### 5.3 Manual Method (Alternative)

If you prefer to start the backend and frontend separately, or if the start script doesn't work:

1. **Backend:** In one terminal, run:
   ```bash
   cd path/to/job_app_helper
   uv run python main.py
   ```

2. **Frontend:** In another terminal, run:
   ```bash
   cd path/to/job_app_helper/frontend
   npm run dev
   ```

3. **Browser:** Go to [http://localhost:3000](http://localhost:3000)

---

## Step 6: First-Time Setup

When you open the app for the first time, a **Settings** panel will automatically open on the right side of the screen. This is where you'll enter your API keys.

### 6.1 Entering Your Settings

The Settings panel has two main sections:

#### AI Assistant (LLM) - **Required**

This section configures the AI that powers the assistant.

1. **Provider**: Select your AI provider from the dropdown:
   - Anthropic Claude (Recommended)
   - OpenAI GPT
   - Google Gemini
   - Ollama (local, no API key needed)

2. **API Key**: Paste your API key here (the one you saved in Step 3)
   - This field won't show if you selected Ollama
   - Your key will be masked with asterisks for security

3. **Model Override** (optional): Leave this empty to use the default model
   - The default model for your selected provider is shown below the dropdown
   - Only change this if you want to use a specific model version

4. **Test Connection**: Click this button to verify your API key works
   - You'll see a success message if everything is configured correctly
   - If there's an error, double-check your API key

#### Integrations (Optional)

This section adds extra capabilities to the AI assistant. You can skip these for now and add them later.

- **Tavily Search API Key**: Allows the AI to search the web for job information
- **JSearch API Key**: Enables the AI to search job boards (recommended if you want job search)
- **Adzuna App ID & Key**: Alternative job board search (use either JSearch or Adzuna)

### 6.2 Saving Your Settings

1. Once you've entered at least your **Provider** and **API Key**, click **"Save Settings"** at the bottom
2. You'll see a "Settings saved successfully!" message
3. The app will automatically close the Settings panel and start the onboarding interview

### 6.3 Onboarding Interview

After saving your settings, the AI Assistant chat panel will automatically open and interview you about your job search preferences.

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

### 6.4 Editing Settings or Profile Later

**To change your API keys or provider:**
1. Click the "Settings" button (⚙️ icon) in the top navigation
2. Update any fields you want to change
3. Click "Save Settings"

**To view or edit your job search profile:**
1. Click the "Profile" button in the top navigation
2. View your saved information
3. Click "Edit Profile" to make changes
4. Click "Save" when done

---

## Step 7: Accessing the App Later

After you close the terminal windows or restart your computer, here's how to run the app again:

### Quick Start (Recommended)

This is the easiest way to restart the app:

**Windows:**
1. Open a command prompt
2. Navigate to the job_app_helper folder:
   ```bash
   cd path\to\job_app_helper
   ```
3. Run:
   ```bash
   start.bat
   ```

**Mac/Linux:**
1. Open a terminal
2. Navigate to the job_app_helper folder:
   ```bash
   cd path/to/job_app_helper
   ```
3. Run:
   ```bash
   ./start.sh
   ```

The start script handles everything automatically, just like the first time!

### Creating a Desktop Shortcut (Optional)

For even easier access, you can create a shortcut on your desktop:

**Windows:**
1. Right-click on your desktop → New → Shortcut
2. For the location, enter:
   ```
   cmd /c "cd /d C:\path\to\job_app_helper && start.bat"
   ```
   (Replace `C:\path\to\job_app_helper` with the actual path)
3. Name it "Job App Helper"
4. Click Finish
5. Now you can double-click this shortcut to start the app!

**Mac:**
1. Open Automator (search in Spotlight)
2. Create a new "Application"
3. Add a "Run Shell Script" action
4. Paste this code:
   ```bash
   cd /path/to/job_app_helper
   ./start.sh
   ```
   (Replace `/path/to/job_app_helper` with the actual path)
5. Save it to your Desktop as "Job App Helper"
6. Double-click to run!

**Linux:**
1. Create a file on your desktop called `job-app-helper.desktop`
2. Add this content:
   ```ini
   [Desktop Entry]
   Type=Application
   Name=Job App Helper
   Exec=/path/to/job_app_helper/start.sh
   Path=/path/to/job_app_helper
   Terminal=true
   ```
   (Replace `/path/to/job_app_helper` with the actual path)
3. Make it executable: `chmod +x job-app-helper.desktop`
4. Double-click to run!

### Manual Method (Alternative)

If you prefer not to use the start script:

1. **Open two terminal/command prompt windows**
2. **In the first terminal:**
   ```bash
   cd path/to/job_app_helper
   uv run python main.py
   ```
3. **In the second terminal:**
   ```bash
   cd path/to/job_app_helper/frontend
   npm run dev
   ```
4. **Open your browser** and go to [http://localhost:3000](http://localhost:3000)

---

## Troubleshooting

### "Command not found" errors

**Problem:** When you try to run `python`, `npm`, or `uv`, you get a "command not found" error.

**Solution:**
- Make sure you installed the software correctly in Step 1
- Close and reopen your terminal after installing
- On Windows, make sure you checked "Add to PATH" during Python installation
- Try `python3` instead of `python` on Mac/Linux

### Port already in use

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

### Frontend shows blank page

**Problem:** The browser loads but shows nothing or shows an error.

**Solution:**
- Make sure both the backend AND frontend are running (you should have two terminal windows open)
- Check the backend terminal for errors
- Try refreshing the browser (press F5 or Cmd+R)
- Clear your browser cache
- Try a different browser

### API key errors

**Problem:** You see "Invalid API key" or "Authentication failed" errors.

**Solution:**
- Double-check that you copied the full API key (no extra spaces)
- Open Settings and use the "Test Connection" button to verify your configuration
- Verify your API key is still valid (check the provider's dashboard)
- Make sure you have credits/quota remaining with your AI provider
- If you just signed up, some providers take a few minutes to activate new API keys

### Installation fails during `uv sync` or `npm install`

**Problem:** You get errors when installing dependencies.

**Solution:**
- Make sure you have a stable internet connection
- On Windows, try running the terminal as Administrator
- Delete the `.venv` folder (if it exists) and the `frontend/node_modules` folder, then try again
- Update uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (Mac/Linux) or reinstall from the website (Windows)

### AI responses are very slow

**Problem:** The AI takes a long time to respond.

**Solution:**
- This is normal for some providers, especially with free tiers
- Consider switching to a different provider
- If using Ollama, make sure you have enough RAM and a good CPU/GPU
- Check your internet connection

### Settings panel doesn't open automatically

**Problem:** The Settings panel doesn't open when you first launch the app.

**Solution:**
- Click the "Settings" button (⚙️ icon) in the top navigation bar to open it manually
- Make sure both the backend and frontend are running (check your terminal windows)
- Try refreshing the browser page
- Check the browser console for errors (press F12, click "Console" tab)

### Can't save settings

**Problem:** When you click "Save Settings", nothing happens or you get an error.

**Solution:**
- Make sure you've selected a Provider and entered an API key (required fields are marked with *)
- Check that the backend server is running (should see output in the terminal)
- Look for error messages in the Settings panel (shown in red at the top)
- Try clicking "Test Connection" first to verify your API key works
- Check the browser console for errors (press F12, click "Console" tab)

### Can't find where I saved the folder

**Problem:** You can't remember where you saved the job_app_helper folder.

**Solution:**
- Use your file browser's search feature to search for "job_app_helper"
- On Windows: Press Win+S and search for "job_app_helper"
- On Mac: Press Cmd+Space and search for "job_app_helper"
- If you used Git, it's likely in your home folder or Documents

---

## Getting Help

If you run into issues not covered here:

1. Check the `logs/app.log` file in the job_app_helper folder for error messages
2. Make sure all software is up to date
3. Try searching for the error message online
4. Open an issue on the GitHub repository with:
   - What you were trying to do
   - What error message you saw
   - Your operating system
   - Screenshots if applicable

---

## Desktop App (Advanced, Optional)

If you'd prefer to run the Job Application Helper as a native desktop application instead of in a browser, the project supports [Tauri v2](https://v2.tauri.app/) for building standalone desktop apps. This requires additional developer tools (Rust toolchain, Tauri system dependencies) and is intended for advanced users.

See [DEVELOPMENT.md](DEVELOPMENT.md#desktop-development-tauri) for detailed instructions on building and running the desktop version.

The browser-based setup described above is the recommended approach for most users.

---

## Next Steps

Now that you're all set up:

1. **Add your first job:** Click "Add Job" to manually track a position
2. **Try the AI assistant:** Click "Chat" and ask it to find jobs for you based on your profile
3. **Explore features:** Update job statuses, add notes, track your progress
4. **Customize your profile:** Keep your profile updated as your job search evolves

Happy job hunting!
