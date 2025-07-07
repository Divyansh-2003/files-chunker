# Final Streamlit app with full functionality
# - Intelligent chunking
# - Separate handling for large files
# - Rejoinable vs Independent zips
# - Flat structure in final ALL_CHUNKS.zip with README

# --- STREAMLIT APP START ---

import streamlit as st
import os
import zipfile
import shutil
from pathlib import Path
import humanfriendly
import uuid
from io import BytesIO

# --- Setup persistent session directory ---
SESSION_ID = st.session_state.get("session_id", str(uuid.uuid4()))
st.session_state["session_id"] = SESSION_ID
BASE_TEMP_DIR = f"temp_storage_{SESSION_ID}"
INPUT_DIR = os.path.join(BASE_TEMP_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_TEMP_DIR, "output")
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Utility Functions ---
def create_zip_from_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(folder_path)
                zipf.write(file_path, arcname)

def split_large_file_into_folder(file_path, max_size, output_dir):
    folder_name = file_path.stem
    target_dir = output_dir / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    part_num = 1

    with open(file_path, "rb") as f:
        while chunk := f.read(max_size):
            part_path = target_dir / f"{folder_name}_part{part_num}"
            with open(part_path, "wb") as part_file:
                part_file.write(chunk)
            parts.append(part_path)
            part_num += 1

    # zip the folder
    zip_path = output_dir / f"{folder_name}_rejoinable.zip"
    create_zip_from_folder(target_dir, zip_path)
    shutil.rmtree(target_dir)
    return [zip_path.name]

def split_folder_intelligently(input_folder, max_chunk_size, output_dir):
    rejoinable, independent = [], []
    temp_independent = []

    for file_path in Path(input_folder).rglob("*"):
        if file_path.is_file():
            size = file_path.stat().st_size
            if size > max_chunk_size:
                parts = split_large_file_into_folder(file_path, max_chunk_size, Path(output_dir))
                rejoinable.extend(parts)
            else:
                dest = Path(output_dir) / file_path.name
                shutil.copy(file_path, dest)
                temp_independent.append(dest)

    zip_parts = []
    current_chunk, current_size, part_num = [], 0, 1
    for file in temp_independent:
        f_size = file.stat().st_size
        if current_size + f_size > max_chunk_size and current_chunk:
            zip_name = f"independent_part{part_num}.zip"
            zip_path = Path(output_dir) / zip_name
            create_zip_from_folder(Path(output_dir), zip_path)
            zip_parts.append(zip_path.name)
            for f in current_chunk:
                f.unlink()
            current_chunk, current_size, part_num = [], 0, part_num + 1

        current_chunk.append(file)
        current_size += f_size

    if current_chunk:
        zip_name = f"independent_part{part_num}.zip"
        zip_path = Path(output_dir) / zip_name
        create_zip_from_folder(Path(output_dir), zip_path)
        zip_parts.append(zip_path.name)
        for f in current_chunk:
            f.unlink()

    return rejoinable, zip_parts

# --- Final ZIP creator ---
def create_final_zip(rejoinable_chunks, independent_chunks, output_dir):
    all_zip_bytes = BytesIO()
    with zipfile.ZipFile(all_zip_bytes, 'w', zipfile.ZIP_DEFLATED) as allzip:
        for zip_file in rejoinable_chunks:
            arcname = f"Rejoinable/{zip_file}"
            allzip.write(Path(output_dir) / zip_file, arcname=arcname)

        for zip_file in independent_chunks:
            arcname = f"Independent/{zip_file}"
            allzip.write(Path(output_dir) / zip_file, arcname=arcname)

        readme = """
README - How to use this ZIP archive

This archive contains chunked ZIP files divided into two categories:

1. Rejoinable/
   - Contains parts of large files (e.g., PDFs, videos) that were split due to size.
   - Use tools like 7-Zip, WinRAR, or `cat` to merge before extracting.

2. Independent/
   - Contains ZIPs of small files or folders which can be used independently.
"""
        allzip.writestr("README.txt", readme.strip())

    all_zip_bytes.seek(0)
    return all_zip_bytes

# --- Streamlit UI ---
st.set_page_config(page_title="Smart File Chunker", layout="wide")
st.title("🗂️ Smart File Chunker")

st.markdown("""
> 📁 **To upload folders**, please **ZIP them first** before uploading.
> Individual files like PDFs or videos can be uploaded directly.
""")

# Reset button
if st.button("🔄 RESET SESSION"):
    if os.path.exists(BASE_TEMP_DIR):
        shutil.rmtree(BASE_TEMP_DIR)
    del st.session_state["session_id"]
    st.rerun()

# Sidebar chunk size selection
st.sidebar.header("Settings")
if "chunk_size" not in st.session_state:
    st.session_state.chunk_size = "5MB"

def update_chunk_size(size):
    st.session_state.chunk_size = size

for size in ["2MB", "5MB", "7MB", "10MB"]:
    if st.sidebar.button(size):
        update_chunk_size(size)

chunk_size_input = st.sidebar.text_input("Max chunk size", value=st.session_state.chunk_size)
try:
    max_chunk_size = humanfriendly.parse_size(chunk_size_input)
    st.sidebar.success(f"Chunk size: {humanfriendly.format_size(max_chunk_size)}")
except:
    st.sidebar.error("Invalid size format. Use 2MB, 5MB, etc.")
    max_chunk_size = 5 * 1024 * 1024

# File upload
uploaded_files = st.file_uploader("Upload files or ZIPs", accept_multiple_files=True)

if uploaded_files and st.button("🚀 Process Files"):
    if os.path.exists(BASE_TEMP_DIR):
        shutil.rmtree(BASE_TEMP_DIR)
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for uploaded_file in uploaded_files:
        file_path = os.path.join(INPUT_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        if uploaded_file.name.endswith(".zip"):
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(INPUT_DIR)
                os.remove(file_path)
            except zipfile.BadZipFile:
                st.error(f"Invalid ZIP: {uploaded_file.name}")

    rejoinable, independent = split_folder_intelligently(INPUT_DIR, max_chunk_size, OUTPUT_DIR)
    final_zip = create_final_zip(rejoinable, independent, OUTPUT_DIR)

    st.success("✅ Processing complete! Download below.")
    st.download_button("📦 Download ALL_CHUNKS.zip", final_zip, file_name="ALL_CHUNKS.zip", mime="application/zip")

    if rejoinable:
        st.subheader("🔗 Rejoinable ZIPs")
        for z in rejoinable:
            with open(Path(OUTPUT_DIR) / z, "rb") as f:
                st.download_button(f"📥 {z}", f, file_name=z)

    if independent:
        st.subheader("📎 Independent ZIPs")
        for z in independent:
            with open(Path(OUTPUT_DIR) / z, "rb") as f:
                st.download_button(f"📥 {z}", f, file_name=z)
