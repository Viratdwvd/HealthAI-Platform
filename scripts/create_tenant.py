#!/usr/bin/env python3
"""
create_tenant.py
----------------
Create and manage tenants in the HealthAI platform.
Provisions: PostgreSQL tenant record + demo user + Qdrant collection namespace.

Usage:
    python scripts/create_tenant.py create --name "City Hospital" --id city-hospital
    python scripts/create_tenant.py list
    python scripts/create_tenant.py delete --id city-hospital
    python scripts/create_tenant.py reset-demo
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime


# ─── Tenant operations ────────────────────────────────────────────────────────

async def create_tenant(
    tenant_id:   str,
    name:        str,
    plan:        str = "starter",
    admin_user:  str = "admin",
    postgres_dsn: str = "",
) -> None:
    import asyncpg

    dsn = postgres_dsn or os.getenv(
        "POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/healthcare"
    ).replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        # Insert tenant
        await conn.execute(
            """
            INSERT INTO tenants (tenant_id, name, plan, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (tenant_id) DO UPDATE SET name = $2, plan = $3
            """,
            tenant_id, name, plan, datetime.utcnow(),
        )

        # Insert admin user
        await conn.execute(
            """
            INSERT INTO users (tenant_id, username, role)
            VALUES ($1, $2, 'admin')
            ON CONFLICT (tenant_id, username) DO NOTHING
            """,
            tenant_id, admin_user,
        )

        print(f"  ✅  Tenant '{tenant_id}' created ({plan} plan)")
        print(f"  👤  Admin user: {admin_user}")
        print(f"  🔑  Login: username={admin_user}, password=demo, tenant_id={tenant_id}")

    finally:
        await conn.close()


async def list_tenants(postgres_dsn: str = "") -> None:
    import asyncpg

    dsn = postgres_dsn or os.getenv(
        "POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/healthcare"
    ).replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT tenant_id, name, plan, created_at FROM tenants ORDER BY created_at DESC"
        )
        if not rows:
            print("  No tenants found.")
            return

        print(f"\n  {'ID':<25} {'Name':<30} {'Plan':<12} {'Created'}")
        print("  " + "─" * 80)
        for row in rows:
            print(f"  {row['tenant_id']:<25} {row['name']:<30} {row['plan']:<12} {row['created_at'].strftime('%Y-%m-%d %H:%M')}")
        print()

    finally:
        await conn.close()


async def delete_tenant(tenant_id: str, postgres_dsn: str = "") -> None:
    import asyncpg

    dsn = postgres_dsn or os.getenv(
        "POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/healthcare"
    ).replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        result = await conn.execute(
            "DELETE FROM tenants WHERE tenant_id = $1", tenant_id
        )
        if "DELETE 1" in result:
            print(f"  ✅  Tenant '{tenant_id}' deleted.")
        else:
            print(f"  ⚠️   Tenant '{tenant_id}' not found.")
    finally:
        await conn.close()


async def reset_demo(postgres_dsn: str = "") -> None:
    """Re-create the demo tenant (useful after full wipe)."""
    await create_tenant(
        tenant_id="tenant-demo",
        name="Demo Organisation",
        plan="enterprise",
        admin_user="demo_user",
        postgres_dsn=postgres_dsn,
    )
    print("  ✅  Demo tenant reset complete.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description="HealthAI Tenant Manager")
    parser.add_argument("--dsn", default="", help="PostgreSQL DSN override")

    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Create a new tenant")
    p_create.add_argument("--id",    required=True, help="Unique tenant identifier (slug)")
    p_create.add_argument("--name",  required=True, help="Human-readable tenant name")
    p_create.add_argument("--plan",  default="starter", choices=["starter", "pro", "enterprise"])
    p_create.add_argument("--admin", default="admin", help="Admin username")

    # list
    sub.add_parser("list", help="List all tenants")

    # delete
    p_delete = sub.add_parser("delete", help="Delete a tenant")
    p_delete.add_argument("--id", required=True)

    # reset-demo
    sub.add_parser("reset-demo", help="Re-create the demo tenant")

    args = parser.parse_args()

    print(f"\n🏥  HealthAI Tenant Manager  →  {args.command}\n")

    if args.command == "create":
        await create_tenant(args.id, args.name, args.plan, args.admin, args.dsn)
    elif args.command == "list":
        await list_tenants(args.dsn)
    elif args.command == "delete":
        await delete_tenant(args.id, args.dsn)
    elif args.command == "reset-demo":
        await reset_demo(args.dsn)

    print()


if __name__ == "__main__":
    asyncio.run(main())
