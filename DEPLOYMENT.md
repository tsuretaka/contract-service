# Deploying to Streamlit Community Cloud

This guide explains how to deploy the Minimal e-Contract Service.

## ⚠️ Important Note specifically for Cloud Hosting

Streamlit Community Cloud (and many other PaaS like Render/Heroku) has an **Ephemeral File System**.
This means any files saved to the disk (uploaded PDFs, SQLite database, Signed Certificates) will be **deleted** when the app restarts or goes to sleep.

**For a production-ready deployment, you MUST use external storage:**
1.  **Database**: Migrate from SQLite (`app.db`) to PostgreSQL (e.g., Supabase, Neon).
2.  **File Storage**: Migrate from local file system (`contracts/`) to Object Storage (e.g., AWS S3, Google Cloud Storage, Supabase Storage).

---

## Instructions for Quick Demo Deployment (Data will reset)

If you only want to demonstrate the app and don't mind data resetting:

1.  **Push to GitHub**
    *   Create a new repository on GitHub.
    *   Push this code to the repository.
    *   Ensure `.gitignore` is working (secrets and local DBs should not be pushed).

2.  **Deploy on Streamlit Community Cloud**
    *   Go to [share.streamlit.io](https://share.streamlit.io/).
    *   Connect your GitHub account.
    *   Select the repository and branch.
    *   Main file path: `app.py`
    *   Click **Deploy**.

3.  **Packages**
    *   The system will automatically detect `requirements.txt` (Python libs) and `packages.txt` (System libs like fonts).

## Future Steps for Persistence

To make this app persistent, we need to:
1.  Connect to **Supabase** (PostgreSQL) for `app.db` replacement.
2.  Use **Supabase Storage** or **S3** for PDF storage.
