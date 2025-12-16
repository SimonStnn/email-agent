#!/usr/bin/env bash

################################################################################
# MCP Server Monitor and Diagnostic Collection Script
#
# This script monitors the M365 MCP server and collects comprehensive
# diagnostic information. On failure, it kills the server and generates
# a detailed diagnostic report (NO AUTO-RESTART).
#
# Features:
#   - Continuous metrics collection (memory, CPU, response times)
#   - Health check monitoring via HTTP endpoint
#   - Process hang detection
#   - Automatic cleanup on failure (NO RESTART)
#   - Comprehensive diagnostic report generation
#
# Usage:
#   ./monitor_mcp_server.sh [--health-check-url URL] [--check-interval SECONDS]
#
# Environment Variables:
#   MCP_HEALTH_URL      - Health check endpoint (default: http://127.0.0.1:8000/health)
#   MCP_CHECK_INTERVAL  - Seconds between checks (default: 10)
#   MCP_MAX_FAILURES    - Max consecutive failures before kill (default: 3)
#   MCP_LOG_DIR         - Directory for logs (default: ./logs)
#   MCP_REPORT_DIR      - Directory for error reports (default: ./reports)
#   MCP_METRICS_FILE    - Metrics log file (default: logs/metrics.log)
################################################################################

set -euo pipefail

# === Configuration ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_URL="${MCP_HEALTH_URL:-http://127.0.0.1:8000/health}"
CHECK_INTERVAL="${MCP_CHECK_INTERVAL:-10}"
MAX_FAILURES="${MCP_MAX_FAILURES:-3}"
LOG_DIR="${MCP_LOG_DIR:-${SCRIPT_DIR}/logs}"
REPORT_DIR="${MCP_REPORT_DIR:-${SCRIPT_DIR}/reports}"
MONITOR_LOG="${LOG_DIR}/monitor.log"
METRICS_LOG="${MCP_METRICS_FILE:-${LOG_DIR}/metrics.log}"
PID_FILE="${LOG_DIR}/mcp_server.pid"

# Create directories
mkdir -p "${LOG_DIR}" "${REPORT_DIR}"

# === Logging Functions ===
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    local log_line="[${timestamp}] [${level}] ${message}"
    echo "${log_line}" >> "${MONITOR_LOG}"
    echo "${log_line}"
}

log_info() {
    log "INFO" "$@"
}

log_warn() {
    log "WARN" "$@"
}

log_error() {
    log "ERROR" "$@"
}

log_critical() {
    log "CRITICAL" "$@"
}

# === Metrics Collection Functions ===
collect_process_metrics() {
    local pids="$1"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

    for pid in ${pids}; do
        if [[ ! -d "/proc/${pid}" ]]; then
            continue
        fi

        # Memory usage (RSS in KB)
        local mem_rss
        mem_rss=$(awk '/VmRSS:/ {print $2}' "/proc/${pid}/status" 2>/dev/null || echo "0")

        # CPU usage
        local cpu_percent
        cpu_percent=$(ps -p "${pid}" -o %cpu= 2>/dev/null | tr -d ' ' || echo "0")

        # Thread count
        local threads
        threads=$(ps -p "${pid}" -o nlwp= 2>/dev/null | tr -d ' ' || echo "0")

        # Open files count
        local open_files
        open_files=$(lsof -p "${pid}" 2>/dev/null | wc -l || echo "0")

        # Log metrics
        echo "${timestamp},${pid},${mem_rss},${cpu_percent},${threads},${open_files}" >> "${METRICS_LOG}"
    done
}

check_health_with_timing() {
    local url="$1"
    local timeout="${2:-5}"
    local start_time
    local end_time
    local duration_ms

    start_time=$(date +%s%3N)

    if command -v curl &> /dev/null; then
        curl -sf --max-time "${timeout}" "${url}" > /dev/null 2>&1
        local result=$?
        end_time=$(date +%s%3N)
        duration_ms=$((end_time - start_time))

        # Log response time
        local timestamp
        timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
        echo "${timestamp},health_check,${duration_ms},${result}" >> "${METRICS_LOG}"

        return $result
    else
        log_error "curl not found for health checks"
        return 2
    fi
}

# === Health Check Functions ===
check_health() {
    local url="$1"
    local timeout="${2:-5}"

    if command -v curl &> /dev/null; then
        curl -sf --max-time "${timeout}" "${url}" > /dev/null 2>&1
        return $?
    elif command -v wget &> /dev/null; then
        wget -q -O /dev/null --timeout="${timeout}" "${url}" 2>&1
        return $?
    else
        log_error "Neither curl nor wget found. Cannot perform health checks."
        return 2
    fi
}

# === Process Management Functions ===
get_server_pids() {
    # Find all MCP server processes
    pgrep -f "m365-mcp|m365_mcp" || true
}

kill_server_processes() {
    local signal="$1"  # TERM or KILL
    local pids

    pids="$(get_server_pids)"

    if [[ -z "${pids}" ]]; then
        log_info "No MCP server processes found"
        return 0
    fi

    log_warn "Sending SIG${signal} to PIDs: ${pids}"

    for pid in ${pids}; do
        if kill "-${signal}" "${pid}" 2>/dev/null; then
            log_info "Sent SIG${signal} to PID ${pid}"
        else
            log_warn "Failed to send SIG${signal} to PID ${pid} (may have already exited)"
        fi
    done

    # Wait for processes to die
    local max_wait=10
    local waited=0

    while [[ ${waited} -lt ${max_wait} ]]; do
        pids="$(get_server_pids)"
        if [[ -z "${pids}" ]]; then
            log_info "All processes terminated"
            return 0
        fi

        sleep 1
        ((waited++))
    done

    # If still alive, return failure
    pids="$(get_server_pids)"
    if [[ -n "${pids}" ]]; then
        log_warn "Processes still alive after ${max_wait}s: ${pids}"
        return 1
    fi

    return 0
}

force_kill_all() {
    log_critical "Force killing all MCP server processes"

    # Try graceful shutdown first
    if ! kill_server_processes "TERM"; then
        log_warn "Graceful shutdown failed, using SIGKILL"
        kill_server_processes "KILL"
    fi

    # Nuclear option: kill -9
    local pids
    pids="$(get_server_pids)"

    if [[ -n "${pids}" ]]; then
        log_critical "Using kill -9 on remaining processes: ${pids}"
        for pid in ${pids}; do
            kill -9 "${pid}" 2>/dev/null || true
        done
    fi

    # Verify everything is dead
    sleep 2
    pids="$(get_server_pids)"

    if [[ -n "${pids}" ]]; then
        log_error "CRITICAL: Unable to kill processes: ${pids}"
        return 1
    fi

    log_info "All processes successfully terminated"
    return 0
}

# === Diagnostic Functions ===
collect_logs() {
    local report_file="$1"

    log_info "Collecting log files for error report"

    {
        echo "=== LOG FILES COLLECTED AT $(date) ==="
        echo ""

        # Collect recent errors from error log
        if [[ -f "${LOG_DIR}/mcp_server_errors.jsonl" ]]; then
            echo "=== RECENT ERRORS (last 50 lines) ==="
            tail -n 50 "${LOG_DIR}/mcp_server_errors.jsonl" || echo "Failed to read errors log"
            echo ""
        fi

        # Collect recent activity from main log
        if [[ -f "${LOG_DIR}/mcp_server.log" ]]; then
            echo "=== RECENT ACTIVITY (last 100 lines) ==="
            tail -n 100 "${LOG_DIR}/mcp_server.log" || echo "Failed to read main log"
            echo ""
        fi

        # Collect all JSON logs (last 100 lines)
        if [[ -f "${LOG_DIR}/mcp_server_all.jsonl" ]]; then
            echo "=== RECENT JSON LOGS (last 100 lines) ==="
            tail -n 100 "${LOG_DIR}/mcp_server_all.jsonl" || echo "Failed to read JSON log"
            echo ""
        fi

        # Collect monitor log
        if [[ -f "${MONITOR_LOG}" ]]; then
            echo "=== MONITOR LOG (last 50 lines) ==="
            tail -n 50 "${MONITOR_LOG}" || echo "Failed to read monitor log"
            echo ""
        fi

    } > "${report_file}"

    log_info "Logs collected to: ${report_file}"
}

collect_system_info() {
    local report_file="$1"

    log_info "Collecting system information"

    {
        echo ""
        echo "=== SYSTEM INFORMATION ==="
        echo "Date: $(date)"
        echo "Hostname: $(hostname)"
        echo "Uptime: $(uptime)"
        echo ""

        echo "=== PROCESS INFORMATION ==="
        if pids="$(get_server_pids)"; then
            for pid in ${pids}; do
                echo "--- Process ${pid} ---"
                if [[ -f "/proc/${pid}/status" ]]; then
                    cat "/proc/${pid}/status" 2>/dev/null || echo "Unable to read status"
                fi
                echo ""

                if [[ -f "/proc/${pid}/cmdline" ]]; then
                    echo "Command: $(tr '\0' ' ' < /proc/${pid}/cmdline 2>/dev/null || echo "Unable to read cmdline")"
                fi
                echo ""
            done
        else
            echo "No MCP server processes found"
        fi

        echo ""
        echo "=== PORT INFORMATION ==="
        ss -tlnp 2>/dev/null | grep -E ":(8000|8080)" || echo "No processes listening on ports 8000/8080"
        echo ""

        echo "=== OPEN FILES ==="
        if pids="$(get_server_pids)"; then
            for pid in ${pids}; do
                echo "--- Open files for PID ${pid} ---"
                lsof -p "${pid}" 2>/dev/null | head -n 50 || echo "Unable to list open files"
                echo ""
            done
        fi

        echo ""
        echo "=== MEMORY USAGE ==="
        free -h || echo "Unable to get memory info"
        echo ""

        echo "=== DISK USAGE ==="
        df -h "${LOG_DIR}" || echo "Unable to get disk info"
        echo ""

    } >> "${report_file}"

    log_info "System info collected to: ${report_file}"
}

generate_error_report() {
    local reason="$1"
    local timestamp
    timestamp="$(date '+%Y%m%d_%H%M%S')"
    local report_file="${REPORT_DIR}/error_report_${timestamp}.txt"

    log_critical "Generating error report: ${report_file}"

    {
        echo "################################################################################"
        echo "# MCP SERVER FAILURE REPORT"
        echo "# Timestamp: $(date)"
        echo "# Reason: ${reason}"
        echo "################################################################################"
        echo ""
    } > "${report_file}"

    collect_logs "${report_file}"
    collect_system_info "${report_file}"

    # Add metrics summary
    {
        echo ""
        echo "=== METRICS SUMMARY (last 50 entries) ==="
        if [[ -f "${METRICS_LOG}" ]]; then
            tail -n 50 "${METRICS_LOG}"
        else
            echo "No metrics log found"
        fi
        echo ""
    } >> "${report_file}"

    {
        echo ""
        echo "=== END OF REPORT ==="
        echo "################################################################################"
    } >> "${report_file}"

    log_critical "Error report generated: ${report_file}"
    echo "${report_file}"
}

# === Main Monitoring Loop ===
monitor_server() {
    local consecutive_failures=0
    local check_count=0

    log_info "Starting MCP server monitoring with metrics collection"
    log_info "Health check URL: ${HEALTH_URL}"
    log_info "Check interval: ${CHECK_INTERVAL}s"
    log_info "Max consecutive failures: ${MAX_FAILURES}"
    log_info "Metrics log: ${METRICS_LOG}"

    # Write metrics header
    echo "timestamp,metric_type,value,status" > "${METRICS_LOG}"

    while true; do
        ((check_count++)) || true
        log_info "Health check #${check_count}"

        # Collect process metrics before health check
        local pids
        pids="$(get_server_pids)"
        if [[ -n "${pids}" ]]; then
            collect_process_metrics "${pids}"
        fi

        # Perform health check with timing
        if check_health_with_timing "${HEALTH_URL}"; then
            log_info "Health check passed"
            consecutive_failures=0
        else
            ((consecutive_failures++))
            log_warn "Health check failed (${consecutive_failures}/${MAX_FAILURES})"

            if [[ ${consecutive_failures} -ge ${MAX_FAILURES} ]]; then
                log_critical "Max failures reached! Server hung or unresponsive"
                log_critical "KILLING SERVER - NO AUTO-RESTART"

                # Generate comprehensive error report
                local report_file
                report_file="$(generate_error_report "Health check failed ${consecutive_failures} times")"

                # Force kill everything
                force_kill_all

                log_critical "Server killed successfully"
                log_critical "Error report: ${report_file}"
                log_critical "Metrics log: ${METRICS_LOG}"
                log_critical "Manual investigation required - monitor exiting"

                # Exit with error code (DO NOT RESTART)
                exit 1
            fi
        fi

        sleep "${CHECK_INTERVAL}"
    done
}

# === Signal Handlers ===
cleanup() {
    log_info "Monitor shutting down (received signal)"
    exit 0
}

trap cleanup SIGTERM SIGINT

# === Main Entry Point ===
main() {
    log_info "=========================================="
    log_info "MCP Server Monitor Starting"
    log_info "=========================================="
    log_info "Monitor PID: $$"
    log_info "Monitor log: ${MONITOR_LOG}"
    log_info "Report directory: ${REPORT_DIR}"
    log_info "=========================================="

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --health-check-url)
                HEALTH_URL="$2"
                shift 2
                ;;
            --check-interval)
                CHECK_INTERVAL="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --health-check-url URL    Health check endpoint (default: http://127.0.0.1:8000/health)"
                echo "  --check-interval SECONDS  Seconds between checks (default: 10)"
                echo "  --help                    Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  MCP_HEALTH_URL      Health check endpoint"
                echo "  MCP_CHECK_INTERVAL  Seconds between checks"
                echo "  MCP_MAX_FAILURES    Max consecutive failures before restart"
                echo "  MCP_LOG_DIR         Directory for logs"
                echo "  MCP_REPORT_DIR      Directory for error reports"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Start monitoring
    monitor_server
}

# Run main function
main "$@"
