#!/bin/bash
echo "🌐 Testing UI server setup..."
echo ""
echo "Checking media files:"
ls -lh /Users/quantum/Desktop/atlas_output/nano_banana/*.mp4 | wc -l
echo "videos found"
echo ""
echo "Starting orchestrator on port 8888..."
echo "Dashboard will be at: http://localhost:8888/dashboard"
echo ""
echo "Press Ctrl+C to stop"
