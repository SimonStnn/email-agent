#!/bin/bash
# Test script for MCP HTTP endpoint

set -e

HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-8000}"
TOKEN="${MCP_AUTH_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "Error: MCP_AUTH_TOKEN environment variable is required"
    exit 1
fi

echo "Testing MCP HTTP endpoint..."
echo "Host: $HOST:$PORT"
echo ""

# Test 1: Health check (no auth required)
echo "1. Testing /health endpoint (no auth)..."
curl -s "http://$HOST:$PORT/health" | jq '.'
echo ""

# Test 2: MCP endpoint without auth (should fail)
echo "2. Testing /mcp endpoint without auth (should return 401)..."
curl -s -w "\n  HTTP Status: %{http_code}\n" "http://$HOST:$PORT/mcp"
echo ""

# Test 3: MCP endpoint with auth (should work)
echo "3. Testing /mcp endpoint with Bearer token..."
curl -s -w "\n  HTTP Status: %{http_code}\n" \
    -H "Authorization: Bearer $TOKEN" \
    "http://$HOST:$PORT/mcp" | head -20
echo ""

echo "✅ Test complete!"
