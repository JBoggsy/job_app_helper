#!/bin/bash

# Shortlist - Unified Startup Script
# This script checks dependencies, starts the backend and frontend, and opens your browser

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════╗"
echo "║      Shortlist Startup      ║"
echo "╚═══════════════════════════════╝"
echo -e "${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get version
get_version() {
    $1 2>&1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1
}

# Function to compare versions
version_ge() {
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

echo -e "${YELLOW}→ Checking dependencies...${NC}"
echo ""

# Check Python
if ! command_exists python3; then
    echo -e "${RED}✗ Python 3 is not installed${NC}"
    echo "  Please install Python 3.12 or higher from:"
    echo -e "  ${BLUE}https://www.python.org/downloads/${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | grep -oE '[0-9]+\.[0-9]+')
if version_ge "$PYTHON_VERSION" "3.12"; then
    echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python $PYTHON_VERSION is too old (need 3.12+)${NC}"
    echo "  Please upgrade Python from:"
    echo -e "  ${BLUE}https://www.python.org/downloads/${NC}"
    exit 1
fi

# Check Node.js
if ! command_exists node; then
    echo -e "${RED}✗ Node.js is not installed${NC}"
    echo "  Please install Node.js 18 or higher from:"
    echo -e "  ${BLUE}https://nodejs.org/${NC}"
    exit 1
fi

NODE_VERSION=$(node --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
if version_ge "$NODE_VERSION" "18.0"; then
    echo -e "${GREEN}✓ Node.js $NODE_VERSION${NC}"
else
    echo -e "${RED}✗ Node.js $NODE_VERSION is too old (need 18+)${NC}"
    echo "  Please upgrade Node.js from:"
    echo -e "  ${BLUE}https://nodejs.org/${NC}"
    exit 1
fi

# Check uv
if ! command_exists uv; then
    echo -e "${RED}✗ uv is not installed${NC}"
    echo "  Installing uv..."
    if command_exists curl; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
    else
        echo "  Please install uv manually:"
        echo -e "  ${BLUE}pip install uv${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ uv${NC}"
echo ""

# Check if dependencies are installed
echo -e "${YELLOW}→ Checking if dependencies are installed...${NC}"
echo ""

if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}  Installing Python dependencies (this may take a minute)...${NC}"
    uv sync
    echo -e "${GREEN}  ✓ Python dependencies installed${NC}"
else
    echo -e "${GREEN}  ✓ Python dependencies already installed${NC}"
fi

if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}  Installing Node dependencies (this may take a minute)...${NC}"
    cd frontend && npm install && cd ..
    echo -e "${GREEN}  ✓ Node dependencies installed${NC}"
else
    echo -e "${GREEN}  ✓ Node dependencies already installed${NC}"
fi

echo ""

# Check configuration
if [ ! -f "config.json" ] && [ -z "$LLM_API_KEY" ]; then
    echo -e "${YELLOW}⚠ No configuration found${NC}"
    echo "  The app will start, but you'll need to configure your LLM API key"
    echo "  in the Settings panel (gear icon in the top right)."
    echo ""
fi

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    # Kill all child processes
    pkill -P $$ 2>/dev/null || true
    exit 0
}

# Set trap for Ctrl+C
trap cleanup SIGINT SIGTERM

echo -e "${GREEN}→ Starting Shortlist...${NC}"
echo ""

# Start backend
echo -e "${BLUE}  Starting backend server...${NC}"
uv run python main.py &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 3

# Start frontend
echo -e "${BLUE}  Starting frontend dev server...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for frontend to be ready
sleep 3

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          🚀 App is running!          ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}Frontend:${NC} http://localhost:3000"
echo -e "  ${BLUE}Backend:${NC}  http://localhost:5000"
echo ""
echo -e "${YELLOW}  Press Ctrl+C to stop the app${NC}"
echo ""

# Try to open browser (works on Mac and Linux)
if command_exists open; then
    # macOS
    sleep 2
    open http://localhost:3000 2>/dev/null || true
elif command_exists xdg-open; then
    # Linux
    sleep 2
    xdg-open http://localhost:3000 2>/dev/null || true
fi

# Wait for processes
wait
