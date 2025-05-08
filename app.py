import streamlit as st
import pandas as pd
import io
import docx
from pptx import Presentation
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

# === Authenticate with Google Drive ===
st.title("📂 Persona Builder — Multi-Format Parser")

creds = service_account.Credentials.from_service_account_info(st.secrets["gcp"])
drive_service = build("drive", "v3", credentials=creds)
FOLDER_ID = "1QBUwWvuaLvJrie3cblt8d4ch9cyaogWg"

# === Recursive File Listing ===
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

# === Safe .pptx Parser ===
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

# === Load and Parse Files ===
st.write("🔍 Scanning Google Drive folder...")
files = list_all_files(FOLDER_ID)

if not files:
    st.warning("No files found.")
else:
    st.success(f"✅ Found {len(files)} files. Parsing...")

    all_texts = []

    for file in files:
        file_id = file["id"]
        file_name = file["name"]
        mime = file["mimeType"]
        st.write(f"📄 Processing: {file_name} ({mime})")

        try:
            fh = io.BytesIO()
            if mime.startswith("application/vnd.google-apps"):
                # === Google-native export handling ===
                export_mime = {
                    "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.google-apps.spreadsheet": "text/csv",
                    "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                }.get(mime)

                if not export_mime:
                    st.warning(f"⏭️ Skipping unsupported Google-native file: {file_name}")
                    continue

                request = drive_service.files().export_media(fileId=file_id, mimeType=export_mime)
            else:
                # === Binary file download ===
                request = drive_service.files().get_media(fileId=file_id)

            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)

            # === Format-specific parsing ===
            text = ""
            if file_name.endswith(".csv"):
                df = pd.read_csv(fh)
                text = df.to_csv(index=False)
            elif file_name.endswith(".xlsx"):
                df = pd.read_excel(fh)
                text = df.to_csv(index=False)
            elif file_name.endswith(".docx"):
                doc = docx.Document(fh)
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            elif file_name.endswith(".pptx") or "presentation" in mime:
                try:
                    text = safe_parse_pptx(fh)
                except TimeoutError:
                    st.warning(f"⏱️ Skipped {file_name} (pptx parse timeout)")
                    continue
            elif file_name.endswith(".pdf"):
                st.info(f"⏭️ PDF parsing not yet enabled in Cloud (consider export to Google Doc or plain text)")
                continue
            else:
                st.warning(f"⏭️ Skipping unknown file type: {file_name}")
                continue

            if text.strip():
                all_texts.append(f"\n---\n# {file_name}\n{text.strip()}")
                st.success(f"✅ Parsed: {file_name}")
            else:
                st.warning(f"⚠️ No usable text in: {file_name}")

        except Exception as e:
            st.error(f"❌ Error processing {file_name}: {e}")

    # === Final Output ===
    combined = "\n\n".join(all_texts)
    st.session_state["persona_input_text"] = combined
    st.write(f"📊 Parsed content from {len(all_texts)} file(s)")
    st.text_area("📄 Combined Extracted Text", value=combined[:3000], height=300)


