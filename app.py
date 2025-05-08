import streamlit as st
import pandas as pd
import io
import fitz  # PyMuPDF
import docx
from pptx import Presentation
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import signal
import time

class TimeoutException(Exception): pass

def timeout_handler(signum, frame):
    raise TimeoutException("Timed out while processing file")

signal.signal(signal.SIGALRM, timeout_handler)

# Authenticate
st.write("🔑 Authenticating with Google Drive...")
creds = service_account.Credentials.from_service_account_info(st.secrets["gcp"])
drive_service = build("drive", "v3", credentials=creds)

FOLDER_ID = "1QBUwWvuaLvJrie3cblt8d4ch9cyaogWg"
st.title("📂 PPTX Timeout Debug Mode")

# Recursive folder scan
def list_all_files(folder_id):
    all_files = []
    try:
        query = f"'{folder_id}' in parents"
        st.write(f"🔍 Listing files in folder: {folder_id}")
        results = drive_service.files().list(
            q=query,
            pageSize=100,
            fields="files(id, name, mimeType)"
        ).execute()

        for file in results.get("files", []):
            if file["mimeType"] == "application/vnd.google-apps.folder":
                all_files.extend(list_all_files(file["id"]))
            else:
                all_files.append(file)
    except Exception as e:
        st.error(f"Error accessing folder {folder_id}: {e}")
    return all_files

try:
    st.write("📁 Scanning for files...")
    files = list_all_files(FOLDER_ID)[:3]
    st.write("📦 Files to be processed:")
    for f in files:
        st.write(f["name"], f["mimeType"])

    if not files:
        st.warning("No files found in the folder tree.")
    else:
        all_texts = []
        for file in files:
            file_id = file["id"]
            file_name = file["name"]
            mime = file["mimeType"]
            st.write(f"📄 Attempting `{file_name}`")

            fh = io.BytesIO()

            try:
                if mime == "application/vnd.google-apps.presentation":
                    st.write("🛰 Exporting Google Slides to pptx format...")
                    request = drive_service.files().export_media(
                        fileId=file_id,
                        mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                elif mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation" or file_name.endswith(".pptx"):
                    st.write("📥 Downloading .pptx from Drive...")
                    request = drive_service.files().get_media(fileId=file_id)
                else:
                    st.warning(f"⏭️ Skipping non-pptx file: {file_name} ({mime})")
                    continue

                st.write("📦 Starting download...")
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                st.write("✅ Download complete")
                fh.seek(0)

                try:
                    st.write("🧠 Parsing pptx file...")
                    signal.alarm(10)
                    prs = Presentation(fh)
                    slides = []
                    for i, slide in enumerate(prs.slides):
                        if i >= 5: break
                        for shape in slide.shapes:
                            if hasattr(shape, "text"):
                                slides.append(shape.text)
                    signal.alarm(0)
                    text = "\n".join(slides)
                    all_texts.append(f"\n---\n# {file_name}\n{text.strip()[:2000]}\n")
                    st.write(f"✅ Finished parsing: {file_name}")

                except TimeoutException:
                    st.warning(f"⏱️ Timeout while parsing {file_name}. Skipped.")

            except HttpError as e:
                if e.resp.status == 403:
                    st.warning(f"⛔ Skipping unexportable Google file: {file_name}")
                else:
                    st.error(f"❌ Failed to process {file_name}: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error for {file_name}: {e}")

        full_text = "\n\n".join(all_texts)
        st.session_state["persona_input_text"] = full_text

        st.success("✅ PPTX parse attempt complete")
        st.text_area("📄 Preview", full_text[:3000], height=250)

except HttpError as e:
    st.error(f"Drive API error: {e}")

