"""Initial schema – all platform tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision       = "001_initial_schema"
down_revision  = None
branch_labels  = None
depends_on     = None


def upgrade() -> None:
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"pg_trgm\"")

    # ── tenants ───────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("tenant_id",  sa.String(),    primary_key=True),
        sa.Column("name",       sa.String(),    nullable=False),
        sa.Column("plan",       sa.String(),    nullable=False, server_default="starter"),
        sa.Column("created_at", sa.DateTime(),  nullable=False, server_default=sa.text("now()")),
        sa.Column("settings",   postgresql.JSONB(), nullable=False, server_default="{}"),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("user_id",   postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", sa.String(),  nullable=False),
        sa.Column("username",  sa.String(),  nullable=False),
        sa.Column("email",     sa.String()),
        sa.Column("role",      sa.String(),  nullable=False, server_default="analyst"),
        sa.Column("created_at",sa.DateTime(),nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
    )

    # ── ingestion_jobs ────────────────────────────────────────────────────────
    op.create_table(
        "ingestion_jobs",
        sa.Column("job_id",    postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id", sa.String(),  nullable=False),
        sa.Column("user_id",   sa.String(),  nullable=False),
        sa.Column("file_name", sa.String(),  nullable=False),
        sa.Column("file_type", sa.String(),  nullable=False),
        sa.Column("status",    sa.String(),  nullable=False, server_default="pending"),
        sa.Column("chunks",    sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error",     sa.Text()),
        sa.Column("created_at",sa.DateTime(),nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",sa.DateTime()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_jobs_tenant", "ingestion_jobs", ["tenant_id"])
    op.create_index("idx_jobs_status", "ingestion_jobs", ["status"])

    # ── datasets ──────────────────────────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("dataset_id",  postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id",   sa.String(),  nullable=False),
        sa.Column("name",        sa.String(),  nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("row_count",   sa.BigInteger(), server_default="0"),
        sa.Column("schema_json", postgresql.JSONB()),
        sa.Column("created_at",  sa.DateTime(),   nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_datasets_tenant_name"),
    )
    op.create_index("idx_datasets_tenant", "datasets", ["tenant_id"])

    # ── query_audit ───────────────────────────────────────────────────────────
    op.create_table(
        "query_audit",
        sa.Column("id",         sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id",  sa.String(),  nullable=False),
        sa.Column("user_id",    sa.String(),  nullable=False),
        sa.Column("session_id", sa.String()),
        sa.Column("query_text", sa.Text(),    nullable=False),
        sa.Column("intent",     sa.String()),
        sa.Column("answer_len", sa.Integer()),
        sa.Column("confidence", sa.Float()),
        sa.Column("latency_ms", sa.Float()),
        sa.Column("sources",    postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(),      nullable=False,
                  server_default=sa.text("now()"), index=True),
    )
    op.create_index("idx_audit_tenant",  "query_audit", ["tenant_id"])
    op.create_index("idx_audit_session", "query_audit", ["session_id"],
                    postgresql_where=sa.text("session_id IS NOT NULL"))
    op.execute(
        "CREATE INDEX idx_audit_fts ON query_audit "
        "USING GIN (to_tsvector('english', query_text))"
    )

    # ── analytics_cache ───────────────────────────────────────────────────────
    op.create_table(
        "analytics_cache",
        sa.Column("cache_key",   sa.String(),  primary_key=True),
        sa.Column("tenant_id",   sa.String(),  nullable=False),
        sa.Column("operation",   sa.String(),  nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at",  sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at",  sa.DateTime(), nullable=False),
    )
    op.create_index("idx_analytics_cache_exp", "analytics_cache", ["expires_at"])

    # ── rule_snapshots ────────────────────────────────────────────────────────
    op.create_table(
        "rule_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("tenant_id",   sa.String(),  nullable=False),
        sa.Column("version",     sa.String(),  nullable=False),
        sa.Column("rules_yaml",  sa.Text(),    nullable=False),
        sa.Column("deployed_at", sa.DateTime(),nullable=False, server_default=sa.text("now()")),
        sa.Column("deployed_by", sa.String()),
        sa.Column("active",      sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
    )

    # ── Seed demo tenant + user ───────────────────────────────────────────────
    op.execute(
        "INSERT INTO tenants (tenant_id, name, plan) "
        "VALUES ('tenant-demo', 'Demo Organisation', 'enterprise') "
        "ON CONFLICT DO NOTHING"
    )
    op.execute(
        "INSERT INTO users (tenant_id, username, role) "
        "VALUES ('tenant-demo', 'demo_user', 'admin') "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("rule_snapshots")
    op.drop_table("analytics_cache")
    op.drop_table("query_audit")
    op.drop_table("datasets")
    op.drop_table("ingestion_jobs")
    op.drop_table("users")
    op.drop_table("tenants")
