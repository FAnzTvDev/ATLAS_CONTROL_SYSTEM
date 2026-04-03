#!/bin/bash

###############################################################################
# 🎬 ATLAS MULTI-TAB CONTROL SYSTEM - LAUNCHER
# Starts the orchestrator server and opens the control dashboard
###############################################################################

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║       🎬 ATLAS MULTI-TAB CONTROL SYSTEM                          ║
║       Distributed Movie Generation Orchestrator                   ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check Python dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"

MISSING_DEPS=()

python3 -c "import fastapi" 2>/dev/null || MISSING_DEPS+=("fastapi")
python3 -c "import uvicorn" 2>/dev/null || MISSING_DEPS+=("uvicorn")
python3 -c "import websockets" 2>/dev/null || MISSING_DEPS+=("websockets")
python3 -c "import requests" 2>/dev/null || MISSING_DEPS+=("requests")

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Installing missing dependencies: ${MISSING_DEPS[*]}${NC}"
    pip3 install fastapi uvicorn websockets requests
else
    echo -e "${GREEN}✅ All dependencies installed${NC}"
fi

# Start orchestrator server in background
echo -e "${YELLOW}Starting orchestrator server...${NC}"

cd "$(dirname "$0")"

# Kill any existing server on port 8888
lsof -ti:8888 | xargs kill -9 2>/dev/null || true

# Start server in background
python3 orchestrator_server.py > atlas_orchestrator.log 2>&1 &
SERVER_PID=$!

echo -e "${GREEN}✅ Server started (PID: $SERVER_PID)${NC}"
echo -e "${GREEN}   Log: $(pwd)/atlas_orchestrator.log${NC}"

# Wait for server to be ready
echo -e "${YELLOW}Waiting for server to be ready...${NC}"
sleep 3

MAX_RETRIES=10
RETRY_COUNT=0

while ! curl -s http://localhost:8888 > /dev/null; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${YELLOW}⚠️  Server taking longer than expected to start${NC}"
        echo -e "${YELLOW}   Check atlas_orchestrator.log for details${NC}"
        break
    fi
    sleep 1
done

echo -e "${GREEN}✅ Server is ready!${NC}"

# Open dashboard in default browser
echo -e "${YELLOW}Opening control dashboard...${NC}"
sleep 1

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "http://localhost:8888"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open "http://localhost:8888" 2>/dev/null || sensible-browser "http://localhost:8888" 2>/dev/null
else
    echo -e "${YELLOW}Please open http://localhost:8888 in your browser${NC}"
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                   ║${NC}"
echo -e "${GREEN}║   ✅ ATLAS CONTROL SYSTEM RUNNING                                ║${NC}"
echo -e "${GREEN}║                                                                   ║${NC}"
echo -e "${GREEN}║   Dashboard:  http://localhost:8888                              ║${NC}"
echo -e "${GREEN}║   API Docs:   http://localhost:8888/docs                         ║${NC}"
echo -e "${GREEN}║   Server PID: $SERVER_PID                                          ║${NC}"
echo -e "${GREEN}║                                                                   ║${NC}"
echo -e "${GREEN}║   Usage from Claude Code:                                        ║${NC}"
echo -e "${GREEN}║   >>> from atlas_commander import AtlasCommander                 ║${NC}"
echo -e "${GREEN}║   >>> commander = AtlasCommander()                               ║${NC}"
echo -e "${GREEN}║   >>> commander.print_status()                                   ║${NC}"
echo -e "${GREEN}║                                                                   ║${NC}"
echo -e "${GREEN}║   Stop server: kill $SERVER_PID                                    ║${NC}"
echo -e "${GREEN}║                                                                   ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Optionally tail the log
if [ "$1" == "--follow" ] || [ "$1" == "-f" ]; then
    echo -e "${YELLOW}Following server log (Ctrl+C to stop)...${NC}"
    echo ""
    tail -f atlas_orchestrator.log
fi
