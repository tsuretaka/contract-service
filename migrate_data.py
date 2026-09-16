"""Legacy Supabase-to-Supabase migration utility.

Credentials must be supplied at execution time; never commit them. This utility is
not used by the Cloudflare PoC and must not be run against production for the PoC.
"""
import os
from sqlalchemy import create_engine, text
from supabase import create_client, Client


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def run_migration():
    old_db_url = required_env("OLD_DATABASE_URL")
    new_supabase_url = required_env("NEW_SUPABASE_URL")
    new_supabase_key = required_env("NEW_SUPABASE_SERVICE_ROLE_KEY")
    print("Starting data migration...")
    engine = create_engine(old_db_url)
    new_supabase: Client = create_client(new_supabase_url, new_supabase_key)
    tables_to_migrate = [
        ("contracts", "cs_contracts"),
        ("parties", "cs_parties"),
        ("signing_sessions", "cs_signing_sessions"),
        ("audit_events", "cs_audit_events"),
    ]
    with engine.connect() as connection:
        for old_table, new_table in tables_to_migrate:
            print(f"Migrating {old_table} -> {new_table}...")
            result = connection.execute(text(f"SELECT * FROM {old_table}"))
            rows = [dict(row._mapping) for row in result]
            if not rows:
                print(f"No data found in {old_table}.")
                continue
            for row in rows:
                for key, value in row.items():
                    if hasattr(value, "isoformat"):
                        row[key] = value.isoformat()
            new_supabase.table(new_table).insert(rows).execute()
            print(f"Successfully inserted {len(rows)} rows into {new_table}.")


if __name__ == "__main__":
    run_migration()
