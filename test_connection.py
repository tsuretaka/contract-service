from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text
from supabase import create_client

# Load env
load_dotenv()

print("--- Supabase Connection Test ---")

# 1. Database Test
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("❌ DATABASE_URL is missing in .env")
else:
    try:
        if db_url.startswith("postgres://"):
             db_url = db_url.replace("postgres://", "postgresql://", 1)
        
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Database Connected! Version: {version}")
    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")

# 2. Storage Test
supa_url = os.environ.get("SUPABASE_URL")
supa_key = os.environ.get("SUPABASE_KEY")
bucket_name = os.environ.get("SUPABASE_BUCKET", "contracts")

if not supa_url or not supa_key:
    print("❌ SUPABASE_URL or SUPABASE_KEY missing in .env")
else:
    try:
        supabase = create_client(supa_url, supa_key)
        # List buckets to verify key and permissions
        buckets = supabase.storage.list_buckets()
        
        found = False
        for b in buckets:
            if b.name == bucket_name:
                found = True
                print(f"✅ Storage Bucket '{bucket_name}' Found!")
                break
        
        if not found:
            print(f"⚠️ Storage Bucket '{bucket_name}' NOT found. Please create it in dashboard.")
            
    except Exception as e:
        print(f"❌ Storage Connection Failed: {e}")
