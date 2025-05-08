import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Authenticate with Google Drive using secrets
creds = service_account.Credentials.from_service_account_info(st.secrets["gcp"])
drive_service = build("drive", "v3", credentials=creds)

# List the first 5 accessible files
results = drive_service.files().list(
    pageSize=5,
    fields="files(id, name)"
).execute()

files = results.get("files", [])

st.title("📁 Google Drive Connection Test")
if not files:
    st.write("✅ Connected to Google Drive, but no files were found.")
else:
    st.success("✅ Successfully connected to Google Drive!")
    for file in files:
        st.write(f"📄 {file['name']} ({file['id']})")
