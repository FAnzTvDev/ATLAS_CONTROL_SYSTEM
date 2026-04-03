#!/bin/bash
# V13.3 Stale Project Cleaner
# Use this when you see old cached data instead of fresh V13.3 output

PROJECT_NAME="${1:-ravencroft_v6_upload}"
PIPELINE_DIR="pipeline_outputs"

echo "=============================================="
echo "V13.3 STALE PROJECT CLEANER"
echo "=============================================="

if [ -d "$PIPELINE_DIR/$PROJECT_NAME" ]; then
    echo "Found stale project: $PIPELINE_DIR/$PROJECT_NAME"
    echo ""
    echo "Contents:"
    ls -la "$PIPELINE_DIR/$PROJECT_NAME/"
    echo ""
    echo "Story Bible created: $(stat -c %y "$PIPELINE_DIR/$PROJECT_NAME/story_bible.json" 2>/dev/null || echo 'N/A')"

    # Check if it has old schema
    if [ -f "$PIPELINE_DIR/$PROJECT_NAME/story_bible.json" ]; then
        if grep -q '"schema_version": "13.3' "$PIPELINE_DIR/$PROJECT_NAME/story_bible.json" 2>/dev/null; then
            echo "✅ Already has V13.3 schema"
        else
            echo "⚠️  OLD SCHEMA - needs regeneration"
        fi

        # Count characters
        CHAR_COUNT=$(python3 -c "import json; d=json.load(open('$PIPELINE_DIR/$PROJECT_NAME/story_bible.json')); print(len(d.get('characters',[])))" 2>/dev/null)
        echo "Characters: $CHAR_COUNT"
    fi

    echo ""
    read -p "Delete this project to force re-import? [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$PIPELINE_DIR/$PROJECT_NAME"
        echo "✅ Deleted $PIPELINE_DIR/$PROJECT_NAME"
        echo ""
        echo "Now restart the server and re-upload your script:"
        echo "  1. python3 orchestrator_server.py"
        echo "  2. Open http://localhost:8000/auto"
        echo "  3. Paste your script - it will create fresh V13.3 data"
    else
        echo "Cancelled. Project unchanged."
    fi
else
    echo "Project not found: $PIPELINE_DIR/$PROJECT_NAME"
    echo ""
    echo "Available projects:"
    ls -d "$PIPELINE_DIR"/*/ 2>/dev/null || echo "  (none)"
fi

echo ""
echo "=============================================="
