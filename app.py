import streamlit as st
import pandas as pd
import io
import fitz  # PyMuPDF
import docx
from pptx import Presentation
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

# Authenticate
creds = service_account.Credentials.from_service_account_info(st.secrets["gcp"])
drive_service = build("drive", "v3", credentials=creds)

FOLDER_ID = "1QBUwWvuaLvJrie3cblt8d4ch9cyaogWg"  # Your shared folder ID
st.title("📂 GPT Persona Ingestion: Multi-Format Drive Parser")

query = f"'{FOLDER_ID}' in parents"

try:
    results = drive_service.files().list(
        q=query,
        pageSize=20,
        fields="files(id, name, mimeType)"
    ).execute()

    files = results.get("files", [])

    if not files:
        st.warning("No files found in the folder.")
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
                    # Export Google Doc to .docx
                    request = drive_service.files().export_media(fileId=file_id,
                        mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    downloader = MediaIoBaseDownload(fh, request)
                elif mime == "application/vnd.google-apps.spreadsheet":
                    # Export Google Sheet to CSV
                    request = drive_service.files().export_media(fileId=file_id, mimeType="text/csv")
                    downloader = MediaIoBaseDownload(fh, request)
                elif mime == "application/vnd.google-apps.presentation":
                    # Export Google Slides to .pptx
                    request = drive_service.files().export_media(fileId=file_id,
                        mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation")
                    downloader = MediaIoBaseDownload(fh, request)
                else:
                    # All other binary files
                    request = drive_service.files().get_media(fileId=file_id)
                    downloader = MediaIoBaseDownload(fh, request)

                done = False
                while not done:
                    _, done = downloader.next_chunk()
                fh.seek(0)

                if file_name.endswith(".csv") or mime == "application/vnd.google-apps.spreadsheet":
                    df = pd.read_csv(fh)
                    st.dataframe(df.head())
                    text = df.to_csv(index=False)
                elif file_name.endswith(".pdf"):
                    pdf = fitz.open(stream=fh.read(), filetype="pdf")
                    text = "\n".join([page.get_text() for page in pdf])
                elif file_name.endswith(".docx") or mime == "application/vnd.google-apps.document":
                    doc = docx.Document(fh)
                    text = "\n".join([p.text for p in doc.paragraphs])
                elif file_name.endswith(".pptx") or mime == "application/vnd.google-apps.presentation":
                    prs = Presentation(fh)
                    slides = []
                    for slide in prs.slides:
                        for shape in slide.shapes:
                            if hasattr(shape, "text"):
                                slides.append(shape.text)
                    text = "\n".join(slides)
                else:
                    text = "(Unsupported file type — skipped)"

                all_texts.append(f"\n---\n# {file_name}\n{text.strip()[:5000]}")

            except Exception as e:
                st.error(f"❌ Failed to process {file_name}: {e}")

        full_text = "\n\n".join(all_texts)
        st.session_state["persona_input_text"] = full_text

        st.success("✅ All supported files parsed and ready for GPT!")
        st.text_area("📄 Combined Extracted Content", full_text[:15000], height=300)

except HttpError as e:
    st.error(f"Drive API error: {e}")



