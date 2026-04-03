#!/bin/bash
# ===========================================================================
# ATLAS V18 — Cloudflare R2 + Tunnel Setup
# ===========================================================================
# This script helps you configure Cloudflare R2 storage and Tunnel access.
# Run this once, then add the exports to your .zshrc or .bash_profile.
# ===========================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           ATLAS V18 — CLOUDFLARE R2 + TUNNEL SETUP         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# --- STEP 1: Check prerequisites ---
echo "━━━ STEP 1: Prerequisites ━━━"
echo ""

# Check wrangler (Cloudflare CLI — used for R2 uploads)
if command -v wrangler &>/dev/null; then
    echo "  ✅ wrangler installed ($(wrangler --version 2>&1 | head -1))"
elif npx wrangler --version &>/dev/null 2>&1; then
    echo "  ✅ wrangler available via npx ($(npx wrangler --version 2>&1 | head -1))"
else
    echo "  ❌ wrangler not installed"
    echo "  → npm install -g wrangler"
    echo "  → Then: wrangler login"
    echo ""
fi

# Check cloudflared
if command -v cloudflared &>/dev/null; then
    echo "  ✅ cloudflared installed ($(cloudflared --version 2>&1 | head -1))"
else
    echo "  ❌ cloudflared not installed"
    echo "  → brew install cloudflared  (macOS)"
    echo "  → Or: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    echo ""
fi

echo ""
echo "━━━ STEP 2: Cloudflare R2 API Token ━━━"
echo ""
echo "  You need an R2 API token from Cloudflare Dashboard:"
echo ""
echo "  1. Go to: https://dash.cloudflare.com"
echo "  2. Click your account → R2 Object Storage"
echo "  3. Click 'Manage R2 API Tokens' (top right)"
echo "  4. Click 'Create API token'"
echo "  5. Give it 'Object Read & Write' permission"
echo "  6. Select bucket: rumble-fanz (or All buckets)"
echo "  7. Copy the Access Key ID and Secret Access Key"
echo ""
echo "  Your Account ID is on the R2 overview page (right sidebar)"
echo ""

# --- STEP 3: Show current env status ---
echo "━━━ STEP 3: Current Environment ━━━"
echo ""
echo "  ATLAS_R2_PUBLIC_URL:    ${ATLAS_R2_PUBLIC_URL:-(not set)}"
echo "  ATLAS_R2_BUCKET:        ${ATLAS_R2_BUCKET:-rumble-fanz (default)}"
echo ""

# --- STEP 4: Show what to add to shell profile ---
echo "━━━ STEP 4: Add to your ~/.zshrc ━━━"
echo ""
echo "  Copy these lines (fill in your values):"
echo ""
echo '  # ATLAS V18 — Cloudflare R2 Storage (wrangler handles auth via login)'
echo '  export ATLAS_R2_BUCKET="rumble-fanz"'
echo '  export ATLAS_R2_PUBLIC_URL="https://media.rumbletv.com"'
echo ""
echo "  NOTE: Make sure you've run 'wrangler login' first."
echo "  Wrangler handles authentication — no API keys needed in env vars."
echo ""

# --- STEP 5: Quick test ---
echo "━━━ STEP 5: Quick Test ━━━"
echo ""
if command -v wrangler &>/dev/null || npx wrangler --version &>/dev/null 2>&1; then
    echo "  Testing R2 connection via wrangler..."
    WRANGLER_CMD="wrangler"
    command -v wrangler &>/dev/null || WRANGLER_CMD="npx wrangler"
    printf "ATLAS_TEST_%s" "$(date +%s)" | $WRANGLER_CMD r2 object put "${ATLAS_R2_BUCKET:-rumble-fanz}/atlas-frames/_health_check.txt" --pipe --content-type text/plain 2>/dev/null && {
        echo "  ✅ R2 connected! Upload successful."
        echo "  Testing public URL..."
        curl -s -o /dev/null -w "  Public URL status: %{http_code}\n" "${ATLAS_R2_PUBLIC_URL:-https://media.rumbletv.com}/atlas-frames/_health_check.txt"
    } || echo "  ❌ R2 upload failed — run 'wrangler login' and try again"
else
    echo "  ⚠️  Install wrangler first: npm install -g wrangler && wrangler login"
fi

echo ""
echo "━━━ STEP 6: Start ATLAS ━━━"
echo ""
echo "  # Start server (with R2 enabled):"
echo "  cd /Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM"
echo "  python3 orchestrator_server.py"
echo ""
echo "  # Test R2 status:"
echo "  curl http://localhost:9999/api/v18/r2/status | python3 -m json.tool"
echo ""
echo "  # Sync media to R2 (from UI: ☁️ R2 Sync button):"
echo "  curl -X POST http://localhost:9999/api/v18/r2/sync -H 'Content-Type: application/json' -d '{\"project\":\"ravencroft_v17\"}'"
echo ""
echo "  # Start tunnel for mobile (from UI: 📱 Go Live button):"
echo "  curl -X POST http://localhost:9999/api/v18/tunnel/start -H 'Content-Type: application/json' -d '{}'"
echo ""
echo "  # Or manually:"
echo "  cloudflared tunnel --url http://localhost:9999"
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Once set up, you can:"
echo "  ☁️  Sync frames/videos to R2 with one click"
echo "  📱  Go Live to get a mobile URL instantly"
echo "  🔗  Run Kling with permanent R2 image URLs"
echo "══════════════════════════════════════════════════════════════"
