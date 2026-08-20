#!/usr/bin/env python3
"""
migrate_db.py
-------------
Applies the platform's PostgreSQL schema (analytics datasets, audit logs).
Run once before starting analytics-service in production.

Usage:
    python scripts/migrate_db.py
    python scripts/migrate_db.py --dsn postgresql://user:pass@host:5432/healthcare
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import asyncpg


SCHEMA_SQL = """
-- ─────────────────────────────────────────────────────────────────────────────
-- Healthcare Platform – PostgreSQL Schema v1
-- ─────────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- fuzzy text search

-- ── Tenants ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id   TEXT        PRIMARY KEY,
    name        TEXT        NOT NULL,
    plan        TEXT        NOT NULL DEFAULT 'starter',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settings    JSONB       NOT NULL DEFAULT '{}'
);

INSERT INTO tenants (tenant_id, name, plan)
VALUES ('tenant-demo', 'Demo Organisation', 'enterprise')
ON CONFLICT DO NOTHING;

-- ── Users ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    user_id     UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   TEXT        NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    username    TEXT        NOT NULL,
    email       TEXT,
    role        TEXT        NOT NULL DEFAULT 'analyst',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, username)
);

INSERT INTO users (tenant_id, username, role)
VALUES ('tenant-demo', 'demo_user', 'admin')
ON CONFLICT DO NOTHING;

-- ── Ingestion jobs ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id      UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   TEXT        NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id     TEXT        NOT NULL,
    file_name   TEXT        NOT NULL,
    file_type   TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'pending',
    chunks      INT         NOT NULL DEFAULT 0,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON ingestion_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON ingestion_jobs(status);

-- ── Datasets (named collections for analytics) ────────────────────────────────

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id  UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   TEXT        NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    description TEXT,
    source_jobs UUID[]      NOT NULL DEFAULT '{}',
    schema_json JSONB,
    row_count   BIGINT      DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_datasets_tenant ON datasets(tenant_id);

-- ── Query audit log ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS query_audit (
    id          BIGSERIAL   PRIMARY KEY,
    tenant_id   TEXT        NOT NULL,
    user_id     TEXT        NOT NULL,
    session_id  TEXT,
    query_text  TEXT        NOT NULL,
    intent      TEXT,
    answer_len  INT,
    confidence  FLOAT,
    latency_ms  FLOAT,
    sources     JSONB       NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant    ON query_audit(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_created   ON query_audit(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_session   ON query_audit(session_id) WHERE session_id IS NOT NULL;

-- Full-text search on queries
CREATE INDEX IF NOT EXISTS idx_audit_query_fts
    ON query_audit USING GIN (to_tsvector('english', query_text));

-- ── Analytics results cache ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analytics_cache (
    cache_key   TEXT        PRIMARY KEY,
    tenant_id   TEXT        NOT NULL,
    operation   TEXT        NOT NULL,
    result_json JSONB       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_cache_exp ON analytics_cache(expires_at);

-- ── Knowledge rule snapshots ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS rule_snapshots (
    snapshot_id UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   TEXT        NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    version     TEXT        NOT NULL,
    rules_yaml  TEXT        NOT NULL,
    deployed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deployed_by TEXT,
    active      BOOLEAN     NOT NULL DEFAULT TRUE
);

-- ── Utility functions ─────────────────────────────────────────────────────────

-- Auto-update updated_at on ingestion_jobs
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_updated ON ingestion_jobs;
CREATE TRIGGER trg_jobs_updated
    BEFORE UPDATE ON ingestion_jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Cleanup expired analytics cache (call from a cron or pg_cron)
CREATE OR REPLACE FUNCTION purge_expired_analytics_cache()
RETURNS INT AS $$
DECLARE deleted INT;
BEGIN
    DELETE FROM analytics_cache WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RETURN deleted;
END;
$$ LANGUAGE plpgsql;
"""


async def run_migrations(dsn: str) -> None:
    print(f"\n🗄️  Healthcare Platform – Database Migration")
    print(f"   DSN: {dsn[:dsn.rindex('@') + 1]}****\n")

    conn = await asyncpg.connect(dsn)
    try:
        print("   Applying schema … ", end="", flush=True)
        await conn.execute(SCHEMA_SQL)
        print("✅")

        # Print table summary
        tables = await conn.fetch(
            """
            SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        )
        print("\n   Tables created/verified:")
        for row in tables:
            print(f"     • {row['tablename']:<35} {row['size']}")

        print("\n✅  Migration complete.\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dsn",
        default=os.getenv(
            "POSTGRES_DSN",
            "postgresql://postgres:postgres@localhost:5432/healthcare",
        ),
        help="PostgreSQL DSN (asyncpg format)",
    )
    args = parser.parse_args()

    # Convert asyncpg DSN → standard if needed
    dsn = args.dsn.replace("postgresql+asyncpg://", "postgresql://")

    asyncio.run(run_migrations(dsn))
