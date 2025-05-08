import streamlit as st
import pandas as pd
import io
from pptx import Presentation
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

# === Google Drive Authentication ===
st.title("📂 Persona Builder - PowerPoint Parser")

creds = service_account.Credentials.from_service_account_info(st.secrets["gcp"])
drive_service = build("drive", "v3", credentials=creds)

FOLDER_ID = "1QBUwWvuaLvJrie3cblt8d4ch9cyaogWg"  # replace with your actual folder ID

# === Helper: Recursively collect all files ===
def list_all_files(folder_id):
    query = f"'{folder_id}' in parents"
    results = drive_service.files().list(q=query, pageSize=100, fields="files(id, name, mimeType)").execute()
    items = results.get("files", [])
    all_files = []

    for item in items:
        if item["mimeType"] == "application/vnd.google-apps.folder":
            st.write(f"📁 Entering folder: {item['name']}")
            all_files.extend(list_all_files(item["id"]))
        else:
            all_files.append(item)
    return all_files

# === File Listing ===
st.write("🔍 Scanning Google Drive folder...")
files = list_all_files(FOLDER_ID)[:3]  # Limit to 3 files for testing

if not files:
    st.warning("No files found.")
else:
    st.success(f"✅ Found {len(files)} files. Processing...")

    all_texts = []
    for file in files:
        file_id = file["id"]
        file_name = file["name"]
        mime = file["mimeType"]

        st.write(f"📄 Processing: {file_name} ({mime})")

        # Skip everything except pptx
        if not (file_name.endswith(".pptx") or "presentation" in mime):
            st.warning(f"⏭️ Skipping unsupported file: {file_name}")
            continue

        try:
            # Download
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)

            # Parse .pptx
            prs = Presentation(fh)
            slides = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        slides.append(shape.text)
            text = "\n".join(slides)

            all_texts.append(f"\n---\n# {file_name}\n{text}")
            st.success(f"✅ Parsed: {file_name}")

        except Exception as e:
            st.error(f"❌ Failed to process {file_name}: {e}")

    # Combine and preview
    full_text = "\n\n".join(all_texts)
    st.session_state["persona_input_text"] = full_text
    st.text_area("📄 Combined Extracted Text", value=full_text[:3000], height=300)
