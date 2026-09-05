import os
from supabase import create_client, Client

OLD_SUPABASE_URL = "https://mhslyqrqlfbmdmbwwfri.supabase.co"
OLD_SUPABASE_KEY = "sb_publishable_wlPNQLFkj4zkXaV9wee26Q_tSAPxRG4" 

NEW_SUPABASE_URL = "https://ovtrtfeogayavadfquuo.supabase.co"
NEW_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im92dHJ0ZmVvZ2F5YXZhZGZxdXVvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY5ODM2OSwiZXhwIjoyMDg3Mjc0MzY5fQ.e3FAAfuN_bcEbHxGf9_ypfKEkyEwiOPvIeTu2dKBH-Q" 

BUCKET_NAME = "contracts"

def run_storage_migration():
    print("Starting storage migration...")
    old_client: Client = create_client(OLD_SUPABASE_URL, OLD_SUPABASE_KEY)
    new_client: Client = create_client(NEW_SUPABASE_URL, NEW_SUPABASE_KEY)
    
    # バケット作成
    try:
        new_client.storage.get_bucket(BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' already exists.")
    except Exception:
        print(f"Creating bucket '{BUCKET_NAME}'...")
        new_client.storage.create_bucket(BUCKET_NAME, options={"public": False})
        
    def copy_files(folder_path=""):
        files = old_client.storage.from_(BUCKET_NAME).list(folder_path)
        if not files: return
        for f in files:
            name = f.get('name')
            if not name or name == '.emptyFolderPlaceholder': continue
            
            file_path = f"{folder_path}/{name}" if folder_path else name
            
            # Storage API list returns id=None for directories/folders
            if f.get('id') is None:
                print(f"Exploring directory: {file_path}")
                copy_files(file_path)
            else:
                print(f"Downloading: {file_path}")
                try:
                    res = old_client.storage.from_(BUCKET_NAME).download(file_path)
                    print(f"Uploading: {file_path}")
                    new_client.storage.from_(BUCKET_NAME).upload(file_path, res, file_options={"upsert": "true"})
                except Exception as e:
                    print(f"Error transferring {file_path}: {e}")

    copy_files("")
    print("Storage migration completed successfully!")

if __name__ == "__main__":
    run_storage_migration()
