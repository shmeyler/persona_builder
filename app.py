import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Authenticate
creds = service_account.Credentials.from_service_account_info(st.secrets["gcp"])
drive_service = build("drive", "v3", credentials=creds)

st.title("📁 Google Drive Connection Test")

try:
    # Try to list any 5 files shared with the service account
    results = drive_service.files().list(
        pageSize=5,
        fields="files(id, name)"
    ).execute()

    files = results.get("files", [])

    if not files:
        st.warning("✅ Connected, but no shared files found.")
    else:
        st.success("✅ Successfully connected to Google Drive!")
        for file in files:
            st.write(f"📄 {file['name']} ({file['id']})")

except HttpError as error:
    st.error(f"🚨 Google Drive API error:\n{error}")

