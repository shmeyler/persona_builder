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
st.title("📂 GPT Persona Ingestion: Recursive Google Drive Parser")

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
                if mime == "application/vnd.google-apps.document":
                    request = drive_service.files().export_media(
                        fileId=file_id,
                        mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                elif mime == "application/vnd.google-apps.spreadsheet":
                    request = drive_service.files().export_media(
                        fileId=file_id,
                        mimeType="text/csv"
                    )
                elif mime == "application/vnd.google-apps.presentation":
                    request = drive_service.files().export_media(
                        fileId=file_id,
                        mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                else:
                    request = drive_service.files().get_media(fileId=file_id)

                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                fh.seek(0)

                if mime in ["text/csv", "application/vnd.google-apps.spreadsheet"] or file_name.endswith(".csv"):
                    df = pd.read_csv(fh, nrows=100)  # limit rows
                    st.dataframe(df.head())
                    text = df.to_csv(index=False)
                elif file_name.endswith(".xlsx") or mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                    df = pd.read_excel(fh, nrows=100)  # limit rows
                    st.dataframe(df.head())
                    text = df.to_csv(index=False)
                # Temporarily skip PDFs and Word Docs for debugging
                elif mime in ["application/pdf"] or file_name.endswith(".pdf"):
                    st.warning(f"⏭️ Skipping PDF file: {file_name}")
                    continue
                elif mime in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.google-apps.document"] or file_name.endswith(".docx"):
                    st.warning(f"⏭️ Skipping Word file: {file_name}")
                    continue
                elif mime in ["application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.google-apps.presentation"] or file_name.endswith(".pptx"):
                    prs = Presentation(fh)
                    slides = []
                    for i, slide in enumerate(prs.slides):
                        if i >= 5: break  # limit slides
                        for shape in slide.shapes:
                            if hasattr(shape, "text"):
                                slides.append(shape.text)
                    text = "\n".join(slides)
                else:
                    st.warning(f"⏭️ Unsupported or unexportable file: {file_name} ({mime})")
                    continue

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

        st.success("✅ All supported files parsed from folder tree and ready for GPT!")
        st.text_area("📄 Preview", full_text[:3000], height=250)

except HttpError as e:
    st.error(f"Drive API error: {e}")

