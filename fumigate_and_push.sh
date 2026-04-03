#!/bin/bash
# ============================================
# ATLAS FUMIGATION + CLEAN PUSH
# Run from: ~/Desktop/ATLAS_CONTROL_SYSTEM/
# One command: bash fumigate_and_push.sh
# ============================================
set -e

echo "=========================================="
echo "ATLAS FUMIGATION — Phase 1: Cleanup"
echo "=========================================="

# Step 1: Remove accidental directories (created by shell mistakes)
echo "[1/8] Removing accidental directories..."
rm -rf "./-p" 2>/dev/null || true
rm -rf "./cp" 2>/dev/null || true
rm -rf "./echo" 2>/dev/null || true
rm -rf "./ls" 2>/dev/null || true
rm -rf "./mkdir" 2>/dev/null || true
rm -rf "./mv" 2>/dev/null || true
rm -rf "./rm" 2>/dev/null || true
rm -rf "./Backed up and removed old Maya Chen frames" 2>/dev/null || true
rm -rf "./Cleared Scene 001 assets for fresh run" 2>/dev/null || true
echo "  Done."

# Step 2: Clear Python caches
echo "[2/8] Clearing Python caches..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
rm -rf pytest-cache-files-* 2>/dev/null || true
echo "  Done."

# Step 3: Remove .git entirely (2.8GB of history — fresh init)
echo "[3/8] Removing old .git history (2.8GB)..."
rm -rf .git
echo "  Done."

# Step 4: Remove venv (693MB — regenerate on server)
echo "[4/8] Removing venv..."
rm -rf venv .venv
echo "  Done."

# Step 5: Remove .wrangler build cache (701MB)
echo "[5/8] Removing .wrangler cache..."
rm -rf .wrangler
echo "  Done."

# Step 6: Create .env.example (safe for GitHub)
echo "[6/8] Creating .env.example..."
printf 'FAL_KEY=\nGOOGLE_API_KEY=\nOPENROUTER_API_KEY=\nREPLICATE_API_TOKEN=\nELEVENLABS_API_KEY=\nMUAPI_KEY=\nSENTRY_DSN=\nREDIS_HOST=localhost\nREDIS_PORT=6379\nR2_ACCESS_KEY=\nR2_SECRET_KEY=\nR2_BUCKET=atlas\nR2_ENDPOINT=\n' > .env.example
echo "  Done."

echo ""
echo "=========================================="
echo "ATLAS FUMIGATION — Phase 2: Git Init + Push"
echo "=========================================="

# Step 7: Fresh git init
echo "[7/8] Initializing fresh git repo..."
git init
git branch -M main
git remote add origin https://github.com/FAnzTvDev/ATLAS_CONTROL_SYSTEM.git
echo "  Done."

# Step 8: Stage, commit, push
echo "[8/8] Staging code-only files..."
git add .

echo ""
echo "Checking staged size..."
git status --short | wc -l
echo "files staged."
echo ""

# Check approximate size
STAGED_SIZE=$(git diff --cached --stat | tail -1)
echo "Staged changes: $STAGED_SIZE"
echo ""

git commit -m "V37 clean push — code only, media excluded"

echo ""
echo "Pushing to GitHub..."
echo "You may be prompted for credentials."
echo "Username: FAnzTvDev"
echo "Password: use your PAT token (ghp_...)"
echo ""
git push -u origin main

echo ""
echo "=========================================="
echo "DONE. Repo pushed to:"
echo "https://github.com/FAnzTvDev/ATLAS_CONTROL_SYSTEM"
echo "=========================================="
echo ""
echo "Next: SSH to Hetzner and clone:"
echo "  ssh root@5.78.151.20"
echo "  cd /opt && git clone https://github.com/FAnzTvDev/ATLAS_CONTROL_SYSTEM.git atlas"
echo "=========================================="
