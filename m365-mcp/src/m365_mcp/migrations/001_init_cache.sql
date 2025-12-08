-- M365 MCP Cache System - Initial Schema Migration
-- Version: 001
-- Description: Creates encrypted cache database with multi-level TTL support
-- Encryption: AES-256 via SQLCipher (encryption key managed by EncryptionKeyManager)

-- ============================================================================
-- CACHE ENTRIES TABLE
-- ============================================================================
-- Stores cached API responses with compression and TTL management
CREATE TABLE IF NOT EXISTS cache_entries (
    -- Primary Key
    cache_key TEXT PRIMARY KEY NOT NULL,

    -- Account and Resource Identification
    account_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,  -- e.g., 'folder_get_tree', 'email_list', 'file_list'
    resource_id TEXT,              -- Optional specific resource identifier

    -- Cache Data (encrypted at rest via SQLCipher)
    data_json TEXT NOT NULL,       -- JSON-serialized response data
    is_compressed INTEGER NOT NULL DEFAULT 0,  -- 1 if gzip compressed, 0 if not
    data_size_bytes INTEGER NOT NULL,          -- Size of cached data in bytes

    -- TTL Management (fresh/stale/expired states)
    created_at REAL NOT NULL,      -- Unix timestamp when cached
    accessed_at REAL NOT NULL,     -- Last access timestamp (for LRU)
    fresh_until REAL NOT NULL,     -- Timestamp when data becomes stale
    expires_at REAL NOT NULL,      -- Timestamp when data expires

    -- Statistics
    hit_count INTEGER NOT NULL DEFAULT 0,  -- Number of cache hits

    -- Metadata
    etag TEXT,                     -- Optional ETag from Graph API
    version INTEGER NOT NULL DEFAULT 1
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_cache_account_resource
    ON cache_entries(account_id, resource_type);

CREATE INDEX IF NOT EXISTS idx_cache_expires
    ON cache_entries(expires_at);

CREATE INDEX IF NOT EXISTS idx_cache_accessed
    ON cache_entries(accessed_at);

CREATE INDEX IF NOT EXISTS idx_cache_account_fresh
    ON cache_entries(account_id, fresh_until);


-- ============================================================================
-- CACHE TASKS TABLE
-- ============================================================================
-- Background task queue for cache warming and asynchronous operations
CREATE TABLE IF NOT EXISTS cache_tasks (
    -- Primary Key
    task_id TEXT PRIMARY KEY NOT NULL,

    -- Task Identification
    account_id TEXT NOT NULL,
    operation TEXT NOT NULL,       -- Tool name (e.g., 'folder_get_tree', 'email_list')

    -- Task Parameters
    parameters_json TEXT NOT NULL, -- JSON-serialized operation parameters

    -- Task State
    status TEXT NOT NULL DEFAULT 'queued',  -- 'queued', 'running', 'completed', 'failed'
    priority INTEGER NOT NULL DEFAULT 5,    -- 1=highest, 10=lowest

    -- Retry Management
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,               -- Error message from last failure

    -- Timestamps
    created_at REAL NOT NULL,
    started_at REAL,               -- When task started running
    completed_at REAL,             -- When task completed

    -- Result
    result_json TEXT,              -- JSON result if completed

    -- Metadata
    version INTEGER NOT NULL DEFAULT 1
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority
    ON cache_tasks(status, priority);

CREATE INDEX IF NOT EXISTS idx_tasks_account
    ON cache_tasks(account_id);

CREATE INDEX IF NOT EXISTS idx_tasks_created
    ON cache_tasks(created_at);


-- ============================================================================
-- CACHE INVALIDATION LOG TABLE
-- ============================================================================
-- Audit trail for cache invalidation operations
CREATE TABLE IF NOT EXISTS cache_invalidation (
    -- Primary Key
    invalidation_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Invalidation Details
    account_id TEXT NOT NULL,
    pattern TEXT NOT NULL,         -- Pattern used for invalidation (e.g., 'email_list:*')
    reason TEXT NOT NULL,          -- Reason for invalidation (e.g., 'write_operation', 'manual')
    operation TEXT,                -- Tool that triggered invalidation

    -- Statistics
    entries_invalidated INTEGER NOT NULL DEFAULT 0,

    -- Timestamp
    invalidated_at REAL NOT NULL,

    -- Metadata
    triggered_by TEXT,             -- Optional user/system identifier
    version INTEGER NOT NULL DEFAULT 1
);

-- Performance Index
CREATE INDEX IF NOT EXISTS idx_invalidation_account_time
    ON cache_invalidation(account_id, invalidated_at);


-- ============================================================================
-- CACHE STATISTICS TABLE
-- ============================================================================
-- System-wide cache performance metrics and statistics
CREATE TABLE IF NOT EXISTS cache_stats (
    -- Statistics Period
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start REAL NOT NULL,
    period_end REAL,

    -- Hit Rate Statistics
    total_requests INTEGER NOT NULL DEFAULT 0,
    cache_hits INTEGER NOT NULL DEFAULT 0,
    cache_misses INTEGER NOT NULL DEFAULT 0,
    stale_hits INTEGER NOT NULL DEFAULT 0,     -- Served stale data

    -- Performance Metrics
    total_response_time_ms INTEGER NOT NULL DEFAULT 0,
    avg_response_time_ms REAL,

    -- Storage Statistics
    total_entries INTEGER NOT NULL DEFAULT 0,
    total_size_bytes INTEGER NOT NULL DEFAULT 0,
    compressed_entries INTEGER NOT NULL DEFAULT 0,

    -- Operation Counts
    writes INTEGER NOT NULL DEFAULT 0,
    invalidations INTEGER NOT NULL DEFAULT 0,
    cleanups INTEGER NOT NULL DEFAULT 0,
    evictions INTEGER NOT NULL DEFAULT 0,      -- LRU evictions

    -- Resource Type Breakdown (JSON)
    resource_stats_json TEXT,      -- Per-resource-type statistics

    -- Metadata
    version INTEGER NOT NULL DEFAULT 1
);

-- Performance Index
CREATE INDEX IF NOT EXISTS idx_stats_period
    ON cache_stats(period_start, period_end);


-- ============================================================================
-- INITIAL DATA
-- ============================================================================
-- Insert initial system statistics record
INSERT INTO cache_stats (
    period_start,
    total_requests,
    cache_hits,
    cache_misses,
    stale_hits,
    total_response_time_ms,
    total_entries,
    total_size_bytes,
    compressed_entries,
    writes,
    invalidations,
    cleanups,
    evictions
) VALUES (
    -- Use current Unix timestamp
    (julianday('now') - 2440587.5) * 86400.0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
);


-- ============================================================================
-- SCHEMA VERSION TRACKING
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY NOT NULL,
    applied_at REAL NOT NULL,
    description TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_version (version, applied_at, description)
VALUES (
    1,
    (julianday('now') - 2440587.5) * 86400.0,
    'Initial cache system schema with encryption support'
);
