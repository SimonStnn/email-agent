#!/usr/bin/env bash

################################################################################
# MCP Server Startup Script with Monitoring
#
# This script starts the M365 MCP server in HTTP mode with comprehensive
# logging and automatic monitoring for failures.
#
# Features:
#   - Starts server in background with logging
#   - Monitors health and auto-restarts on failure
#   - Captures all output to log files
#   - Graceful shutdown on SIGTERM/SIGINT
#
# Usage:
#   ./start_mcp_with_monitoring.sh
#
# Environment Variables (required):
#   M365_MCP_CLIENT_ID  - Azure app client ID
#
# Environment Variables (optional):
#   MCP_HOST                 - Server host (default: 127.0.0.1)
#   MCP_PORT                 - Server port (default: 8000)
#   MCP_AUTH_TOKEN          - Bearer token for authentication
#   MCP_LOG_LEVEL           - Log level (default: INFO)
#   MCP_LOG_DIR             - Log directory (default: ./logs)
################################################################################

set -euo pipefail

# === Load Environment Variables ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env file if it exists (.env takes precedence over shell environment)
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    log_info() { echo -e "\033[0;32m[INFO]\033[0m $*"; }
    log_info "Loading environment variables from .env file..."

    # Read .env file, ignoring comments and empty lines
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue

        # Remove leading/trailing whitespace and quotes from value
        value="${value#"${value%%[![:space:]]*}"}"  # Remove leading whitespace
        value="${value%"${value##*[![:space:]]}"}"  # Remove trailing whitespace
        value="${value#\"}"  # Remove leading quote
        value="${value%\"}"  # Remove trailing quote
        value="${value#\'}"  # Remove leading single quote
        value="${value%\'}"  # Remove trailing single quote

        # Export variable (.env takes precedence)
        export "$key=$value"
    done < <(grep -v '^[[:space:]]*$' "${SCRIPT_DIR}/.env" | grep -v '^[[:space:]]*#')
fi

# === Configuration ===
LOG_DIR="${MCP_LOG_DIR:-${SCRIPT_DIR}/logs}"
REPORT_DIR="${MCP_REPORT_DIR:-${SCRIPT_DIR}/reports}"
PID_FILE="${LOG_DIR}/mcp_server.pid"
MONITOR_PID_FILE="${LOG_DIR}/mcp_monitor.pid"
SERVER_OUTPUT_LOG="${LOG_DIR}/server_output.log"

# Server configuration
MCP_HOST="${MCP_HOST:-127.0.0.1}"
MCP_PORT="${MCP_PORT:-8000}"
MCP_TRANSPORT="http"
MCP_AUTH_METHOD="${MCP_AUTH_METHOD:-bearer}"
MCP_LOG_LEVEL="${MCP_LOG_LEVEL:-INFO}"

# Create directories
mkdir -p "${LOG_DIR}" "${REPORT_DIR}"

# === Color output ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# === Validation ===
validate_environment() {
    log_info "Validating environment..."

    if [[ -z "${M365_MCP_CLIENT_ID:-}" ]]; then
        log_error "M365_MCP_CLIENT_ID environment variable is required"
        log_error "Set it with: export M365_MCP_CLIENT_ID=your-client-id"
        exit 1
    fi

    if [[ "${MCP_AUTH_METHOD}" == "bearer" ]] && [[ -z "${MCP_AUTH_TOKEN:-}" ]]; then
        log_warn "MCP_AUTH_TOKEN not set - generating random token"
        MCP_AUTH_TOKEN="$(openssl rand -hex 32)"
        export MCP_AUTH_TOKEN
        log_warn "Generated token: ${MCP_AUTH_TOKEN}"
        log_warn "Save this token to connect clients!"
    fi

    log_info "Configuration:"
    log_info "  Client ID: ${M365_MCP_CLIENT_ID:0:8}...${M365_MCP_CLIENT_ID: -4}"
    log_info "  Host: ${MCP_HOST}"
    log_info "  Port: ${MCP_PORT}"
    log_info "  Auth: ${MCP_AUTH_METHOD}"
    log_info "  Log Level: ${MCP_LOG_LEVEL}"
    log_info "  Log Dir: ${LOG_DIR}"
}

# === Process Management ===
check_if_running() {
    if [[ -f "${PID_FILE}" ]]; then
        local pid
        pid="$(cat "${PID_FILE}")"
        if kill -0 "${pid}" 2>/dev/null; then
            return 0  # Running
        fi
    fi
    return 1  # Not running
}

# shellcheck disable=SC2329  # Called from cleanup() signal handler
stop_server() {
    log_info "Stopping MCP server..."

    # Stop monitor
    if [[ -f "${MONITOR_PID_FILE}" ]]; then
        local monitor_pid
        monitor_pid="$(cat "${MONITOR_PID_FILE}")"
        if kill -0 "${monitor_pid}" 2>/dev/null; then
            log_info "Stopping monitor (PID: ${monitor_pid})"
            kill -TERM "${monitor_pid}" 2>/dev/null || true
            wait "${monitor_pid}" 2>/dev/null || true
        fi
        rm -f "${MONITOR_PID_FILE}"
    fi

    # Stop server
    if [[ -f "${PID_FILE}" ]]; then
        local server_pid
        server_pid="$(cat "${PID_FILE}")"
        if kill -0 "${server_pid}" 2>/dev/null; then
            log_info "Stopping server (PID: ${server_pid})"
            kill -TERM "${server_pid}" 2>/dev/null || true

            # Wait up to 10 seconds for graceful shutdown
            local waited=0
            while kill -0 "${server_pid}" 2>/dev/null && [[ ${waited} -lt 10 ]]; do
                sleep 1
                ((waited++))
            done

            # Force kill if still running
            if kill -0 "${server_pid}" 2>/dev/null; then
                log_warn "Server didn't stop gracefully, force killing"
                kill -9 "${server_pid}" 2>/dev/null || true
            fi
        fi
        rm -f "${PID_FILE}"
    fi

    log_info "Server stopped"
}

start_server() {
    log_info "Starting MCP server..."

    # Export environment variables
    export M365_MCP_CLIENT_ID
    export MCP_TRANSPORT
    export MCP_HOST
    export MCP_PORT
    export MCP_AUTH_METHOD
    export MCP_AUTH_TOKEN
    export MCP_LOG_LEVEL
    export MCP_LOG_DIR
    export MCP_ALLOW_INSECURE="${MCP_ALLOW_INSECURE:-false}"

    # Start server in background
    cd "${SCRIPT_DIR}"

    # Use uv run to start the server
    nohup uv run m365-mcp > "${SERVER_OUTPUT_LOG}" 2>&1 &
    local server_pid=$!

    echo "${server_pid}" > "${PID_FILE}"
    log_info "Server started (PID: ${server_pid})"
    log_info "Server output: ${SERVER_OUTPUT_LOG}"

    # Wait for server to be ready
    log_info "Waiting for server to be ready..."
    local max_wait=30
    local waited=0

    # Determine health check address (can't connect TO 0.0.0.0)
    local health_host="${MCP_HOST}"
    if [[ "${MCP_HOST}" == "0.0.0.0" || "${MCP_HOST}" == "::" ]]; then
        health_host="localhost"
    fi

    while [[ ${waited} -lt ${max_wait} ]]; do
        if curl -sf --max-time 2 "http://${health_host}:${MCP_PORT}/health" > /dev/null 2>&1; then
            log_info "Server is ready!"
            return 0
        fi

        sleep 1
        ((waited++))
    done

    log_error "Server failed to become ready within ${max_wait} seconds"
    log_error "Check logs: ${SERVER_OUTPUT_LOG}"
    return 1
}

start_monitor() {
    log_info "Starting health monitor..."

    # Determine health check address (can't connect TO 0.0.0.0)
    local health_host="${MCP_HOST}"
    if [[ "${MCP_HOST}" == "0.0.0.0" || "${MCP_HOST}" == "::" ]]; then
        health_host="localhost"
    fi

    local health_url="http://${health_host}:${MCP_PORT}/health"

    # Start monitor in background
    "${SCRIPT_DIR}/monitor_mcp_server.sh" --health-check-url "${health_url}" &
    local monitor_pid=$!

    echo "${monitor_pid}" > "${MONITOR_PID_FILE}"
    log_info "Monitor started (PID: ${monitor_pid})"
}

# === Signal Handlers ===
# shellcheck disable=SC2329  # Invoked by trap on SIGTERM/SIGINT
cleanup() {
    log_info ""
    log_info "Shutting down..."
    stop_server
    exit 0
}

trap cleanup SIGTERM SIGINT

# === Main ===
main() {
    log_info "=========================================="
    log_info "MCP Server with Monitoring"
    log_info "=========================================="

    # Check if already running
    if check_if_running; then
        log_error "Server is already running"
        log_error "Stop it first with: kill $(cat "${PID_FILE}")"
        exit 1
    fi

    # Validate environment
    validate_environment

    # Start server
    if ! start_server; then
        log_error "Failed to start server"
        exit 1
    fi

    # Start monitor
    start_monitor

    log_info "=========================================="
    log_info "MCP Server running with monitoring"
    log_info "=========================================="
    log_info "Health check: http://${MCP_HOST}:${MCP_PORT}/health"
    log_info "MCP endpoint: http://${MCP_HOST}:${MCP_PORT}/mcp"
    log_info ""
    log_info "Server PID: $(cat "${PID_FILE}")"
    log_info "Monitor PID: $(cat "${MONITOR_PID_FILE}")"
    log_info ""
    log_info "Logs:"
    log_info "  Server output: ${SERVER_OUTPUT_LOG}"
    log_info "  Server logs: ${LOG_DIR}/mcp_server.log"
    log_info "  Monitor log: ${LOG_DIR}/monitor.log"
    log_info ""
    log_info "To stop: Press Ctrl+C or run: kill $(cat "${PID_FILE}")"
    log_info "=========================================="

    # Wait for monitor to exit (which happens on failure)
    # Note: Monitor only exits on failure, so this blocks indefinitely in normal operation
    local monitor_pid
    monitor_pid="$(cat "${MONITOR_PID_FILE}")"

    wait "${monitor_pid}" 2>/dev/null || true

    log_error "Monitor exited - server failure detected"
    log_error "Check error reports in: ${REPORT_DIR}"
    exit 1
}

main "$@"
