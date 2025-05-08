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

# Authenticate
creds = service_account.Credentials.from_service_account_info(st.secrets["gcp"])
drive_service = build("drive", "v3", credentials=creds)

FOLDER_ID = "1QBUwWvuaLvJrie3cblt8d4ch9cyaogWg"  # Your root folder ID
st.title("📂 GPT Persona Ingestion: Recursive Google Drive Parser (Testing .pptx only)")

# Recursive function to gather all file metadata from a folder and its subfolders
def list_all_files(folder_id):
    all_files = []
    try:
        query = f"'{folder_id}' in parents"
        results = drive_service.files().list(
            q=query,
            pageSize=100,
            fields="files(id, name, mimeType)"
        ).execute()

        for file in results.get("files", []):
            if file["mimeType"] == "application/vnd.google-apps.folder":
                all_files.extend(list_all_files(file["id"]))  # recurse into subfolder
            else:
                all_files.append(file)
    except Exception as e:
        st.error(f"Error accessing folder {folder_id}: {e}")
    return all_files

try:
    files = list_all_files(FOLDER_ID)[:3]  # Limit to first 3 files for testing
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
            st.write(f"📄 Processing `{file_name}`")

            fh = io.BytesIO()

            try:
                if mime == "application/vnd.google-apps.presentation":
                    request = drive_service.files().export_media(
                        fileId=file_id,
                        mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                elif mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation" or file_name.endswith(".pptx"):
                    request = drive_service.files().get_media(fileId=file_id)
                else:
                    st.warning(f"⏭️ Skipping non-pptx file: {file_name} ({mime})")
                    continue

                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                fh.seek(0)

                prs = Presentation(fh)
                slides = []
                for i, slide in enumerate(prs.slides):
                    if i >= 5: break  # limit slides
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            slides.append(shape.text)
                text = "\n".join(slides)

                all_texts.append(f"\n---\n# {file_name}\n{text.strip()[:2000]}\n")
                st.write(f"✅ Finished: {file_name}")

            except HttpError as e:
                if e.resp.status == 403:
                    st.warning(f"⛔ Skipping unexportable Google file: {file_name}")
                else:
                    st.error(f"❌ Failed to process {file_name}: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error for {file_name}: {e}")

        full_text = "\n\n".join(all_texts)
        st.session_state["persona_input_text"] = full_text

        st.success("✅ PPTX-only test completed")
        st.text_area("📄 Preview", full_text[:3000], height=250)

except HttpError as e:
    st.error(f"Drive API error: {e}")

