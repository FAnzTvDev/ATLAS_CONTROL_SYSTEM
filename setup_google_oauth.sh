#!/bin/bash
# ============================================================
# VYBE Google OAuth Setup
# ============================================================
# STEP 1: Go to https://console.cloud.google.com/apis/credentials
# STEP 2: Click "Create Credentials" → "OAuth 2.0 Client ID"
#         Application type: Web application
# STEP 3: Add Authorized Redirect URIs:
#           https://vybe.rumbletv64.workers.dev/auth/google/callback
#           https://vybe.rumbletv64.workers.dev/auth/youtube/callback
# STEP 4: Enable YouTube Data API v3:
#           https://console.cloud.google.com/apis/library/youtube.googleapis.com
# STEP 5: Copy your Client ID and Client Secret, then run this script
# ============================================================

read -p "Paste your Google Client ID: " CLIENT_ID
read -s -p "Paste your Google Client Secret: " CLIENT_SECRET
echo

echo ""
echo "Setting Cloudflare secrets for VYBE worker..."

echo "$CLIENT_ID"     | wrangler secret put GOOGLE_CLIENT_ID     --name vybe
echo "$CLIENT_SECRET" | wrangler secret put GOOGLE_CLIENT_SECRET  --name vybe
echo "$CLIENT_ID"     | wrangler secret put YOUTUBE_CLIENT_ID    --name vybe
echo "$CLIENT_SECRET" | wrangler secret put YOUTUBE_CLIENT_SECRET --name vybe

echo ""
echo "Deploying VYBE worker..."
wrangler deploy --name vybe

echo ""
echo "Done! OAuth endpoints live at:"
echo "  https://vybe.rumbletv64.workers.dev/auth/google/callback"
echo "  https://vybe.rumbletv64.workers.dev/auth/youtube/callback"
