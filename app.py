import streamlit as st
import pandas as pd
import io
from pptx import Presentation
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

# === App Title ===
st.title("📂 Persona Builder — Safe PPTX Parser with Timeout")

# === Authenticate with Google Drive ===
creds = service_account.Credentials.from_service_account_info(st.secrets["gcp"])
drive_service = build("drive", "v3", credentials=creds)

# === Set Folder ID ===
FOLDER_ID = "1QBUwWvuaLvJrie3cblt8d4ch9cyaogWg"

# === Recursively List All Files ===
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

# === Safe .pptx Parsing with Timeout ===
def safe_parse_pptx(fh):
    def parse():
        prs = Presentation(fh)
        text = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    content = shape.text.strip()
                    if content:
                        text.append(content)
        return "\n".join(text)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(parse)
        return future.result(timeout=5)

# === Load Files ===
st.write("🔍 Scanning Google Drive folder...")
files = list_all_files(FOLDER_ID)[:3]

if not files:
    st.warning("No files found.")
else:
    st.success(f"✅ Found {len(files)} files.")
    all_texts = []

    for file in files:
        file_id = file["id"]
        file_name = file["name"]
        mime = file["mimeType"]

        st.write(f"📄 Processing: {file_name} ({mime})")

        if not (file_name.endswith(".pptx") or "presentation" in mime):
            st.info(f"⏭️ Skipping unsupported file: {file_name}")
            continue

        try:
            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)

            text = safe_parse_pptx(fh)
            if text:
                all_texts.append(f"\n---\n# {file_name}\n{text}")
                st.success(f"✅ Parsed: {file_name}")
            else:
                st.warning(f"⚠️ No text found in: {file_name}")

        except TimeoutError:
            st.error(f"⏱️ Skipped {file_name} — parsing timed out.")
        except Exception as e:
            st.error(f"❌ Error processing {file_name}: {e}")

    # === Combine and Show Output ===
    combined = "\n\n".join(all_texts)
    st.session_state["persona_input_text"] = combined
    st.write(f"📊 Parsed content from {len(all_texts)} file(s)")
    st.text_area("📄 Combined Extracted Text", value=combined[:3000], height=300)


