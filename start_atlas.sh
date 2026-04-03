#!/bin/bash

echo "🎬 ATLAS DIRECTOR - AUTO STARTUP"
echo "================================"

# Step 1: Health Check
echo ""
echo "🏥 Running health check..."
python3 atlas_health_check.py

if [ $? -ne 0 ]; then
    echo "❌ Health check failed with critical errors"
    echo "Please fix errors above before continuing"
    exit 1
fi

# Step 2: Start Web Server
echo ""
echo "🌐 Starting web server on port 5001..."
python3 atlas_director_web.py &
SERVER_PID=$!

sleep 3

# Step 3: Check if server started
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ Web server running (PID: $SERVER_PID)"
    echo ""
    echo "🎉 ATLAS DIRECTOR IS READY!"
    echo "================================"
    echo "Local Access:    http://localhost:5001"
    echo "Network Access:  http://$(ipconfig getifaddr en0 2>/dev/null || echo '0.0.0.0'):5001"
    echo ""
    echo "For online access, run in new terminal:"
    echo "  ngrok http 5001"
    echo ""
    echo "Press Ctrl+C to stop server"
    echo "================================"

    # Keep script running
    wait $SERVER_PID
else
    echo "❌ Failed to start web server"
    exit 1
fi
