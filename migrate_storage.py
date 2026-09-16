"""Legacy Supabase Storage migration utility; unrelated to the Cloudflare PoC."""
import os
from supabase import create_client, Client


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def run_storage_migration():
    bucket_name = os.environ.get("SUPABASE_BUCKET", "contracts")
    old_client: Client = create_client(required_env("OLD_SUPABASE_URL"), required_env("OLD_SUPABASE_KEY"))
    new_client: Client = create_client(required_env("NEW_SUPABASE_URL"), required_env("NEW_SUPABASE_SERVICE_ROLE_KEY"))
    print("Starting storage migration...")
    try:
        new_client.storage.get_bucket(bucket_name)
        print(f"Bucket '{bucket_name}' already exists.")
    except Exception:
        print(f"Creating bucket '{bucket_name}'...")
        new_client.storage.create_bucket(bucket_name, options={"public": False})

    def copy_files(folder_path=""):
        files = old_client.storage.from_(bucket_name).list(folder_path)
        for item in files or []:
            name = item.get("name")
            if not name or name == ".emptyFolderPlaceholder":
                continue
            file_path = f"{folder_path}/{name}" if folder_path else name
            if item.get("id") is None:
                copy_files(file_path)
                continue
            print(f"Copying: {file_path}")
            payload = old_client.storage.from_(bucket_name).download(file_path)
            new_client.storage.from_(bucket_name).upload(file_path, payload, file_options={"upsert": "true"})

    copy_files()
    print("Storage migration completed successfully!")


if __name__ == "__main__":
    run_storage_migration()
