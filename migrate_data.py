import os
from sqlalchemy import create_engine, text
from supabase import create_client, Client

# Sleep-Monitor (旧) Database URL
OLD_DB_URL = "postgresql://postgres.mhslyqrqlfbmdmbwwfri:qaqjym-pyXdif-9befne@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

# yui-inventory (新) Supabase URL & Service Role Key
NEW_SUPABASE_URL = "https://ovtrtfeogayavadfquuo.supabase.co"
NEW_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im92dHJ0ZmVvZ2F5YXZhZGZxdXVvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY5ODM2OSwiZXhwIjoyMDg3Mjc0MzY5fQ.e3FAAfuN_bcEbHxGf9_ypfKEkyEwiOPvIeTu2dKBH-Q"

def run_migration():
    print("Starting data migration...")
    
    # 1. Connect to Old DB
    engine = create_engine(OLD_DB_URL)
    
    # 2. Connect to New Supabase
    new_supabase: Client = create_client(NEW_SUPABASE_URL, NEW_SUPABASE_KEY)
    
    tables_to_migrate = [
        ("contracts", "cs_contracts"),
        ("parties", "cs_parties"),
        ("signing_sessions", "cs_signing_sessions"),
        ("audit_events", "cs_audit_events")
    ]
    
    with engine.connect() as conn:
        for old_table, new_table in tables_to_migrate:
            print(f"Migrating {old_table} -> {new_table}...")
            
            # Fetch all rows
            result = conn.execute(text(f"SELECT * FROM {old_table}"))
            rows = [dict(row._mapping) for row in result]
            
            if not rows:
                print(f"No data found in {old_table}.")
                continue
                
            # Date/Datetime serialization fix
            for row in rows:
                for key, val in row.items():
                    if hasattr(val, "isoformat"):
                        row[key] = val.isoformat()
            
            # Insert into new table
            res = new_supabase.table(new_table).insert(rows).execute()
            print(f"Successfully inserted {len(rows)} rows into {new_table}.")

if __name__ == "__main__":
    run_migration()
