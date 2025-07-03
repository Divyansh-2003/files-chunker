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
def get_folder_size(folder_path):
    total = 0
    for dirpath, _, filenames in os.walk(folder_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total += os.path.getsize(filepath)
    return total

def create_zip_from_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(folder_path.parent)
                zipf.write(file_path, arcname)

def create_zip_from_files(files, zip_path, base_folder):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files:
            arcname = file_path.relative_to(base_folder.parent)
            zipf.write(file_path, arcname)

def split_large_folder(folder_path, folder_name, max_size, output_dir):
    files = [f for f in folder_path.rglob('*') if f.is_file()]
    chunks, current_chunk, current_size, part_num = [], [], 0, 1

    for file in files:
        file_size = os.path.getsize(file)
        if current_size + file_size > max_size and current_chunk:
            zip_name = f"{folder_name}_part{part_num}.zip"
            zip_path = os.path.join(output_dir, zip_name)
            create_zip_from_files(current_chunk, zip_path, folder_path)
            chunks.append(zip_name)
            current_chunk, current_size, part_num = [], 0, part_num + 1

        current_chunk.append(file)
        current_size += file_size

    if current_chunk:
        zip_name = f"{folder_name}_part{part_num}.zip"
        zip_path = os.path.join(output_dir, zip_name)
        create_zip_from_files(current_chunk, zip_path, folder_path)
        chunks.append(zip_name)

    return chunks

def split_folder_intelligently(input_folder, max_chunk_size, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    subfolders = [f for f in Path(input_folder).iterdir() if f.is_dir()]
    results = []

    for subfolder in subfolders:
        folder_name = subfolder.name
        folder_size = get_folder_size(subfolder)

        if folder_size <= max_chunk_size:
            zip_name = f"{folder_name}.zip"
            zip_path = os.path.join(output_dir, zip_name)
            create_zip_from_folder(subfolder, zip_path)
            results.append({'original': folder_name, 'chunks': [zip_name], 'size': folder_size})
        else:
            parts = split_large_folder(subfolder, folder_name, max_chunk_size, output_dir)
            results.append({'original': folder_name, 'chunks': parts, 'size': folder_size})
    return results

# --- Streamlit UI ---
st.set_page_config(page_title="Smart Folder Chunker", layout="wide")
st.title("🗂️ Smart Folder Chunker")
st.write("Upload folders or ZIPs. Files will be chunked and zipped intelligently while preserving folder structure.")

# Reset button
if st.button("🔄 Reset Session"):
    if "zip_results" in st.session_state:
        del st.session_state["zip_results"]
    if "session_id" in st.session_state:
        folder = f"temp_storage_{st.session_state['session_id']}"
        if os.path.exists(folder):
            shutil.rmtree(folder)
        del st.session_state["session_id"]
    st.rerun()

# Sidebar
st.sidebar.header("Settings")
chunk_size_input = st.sidebar.text_input("Max chunk size", value="2MB")
try:
    max_chunk_size = humanfriendly.parse_size(chunk_size_input)
    st.sidebar.success(f"Chunk size: {humanfriendly.format_size(max_chunk_size)}")
except:
    st.sidebar.error("Invalid size format. Use: 2MB, 5MB, etc.")
    max_chunk_size = 2 * 1024 * 1024

# File Upload
uploaded_files = st.file_uploader(
    "Upload files or folders (ZIPs will be auto-extracted)",
    accept_multiple_files=True
)

# Process Button
if uploaded_files and st.button("Process Files"):
    # Clean old files
    if os.path.exists(BASE_TEMP_DIR):
        shutil.rmtree(BASE_TEMP_DIR)
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Save files
    for uploaded_file in uploaded_files:
        file_path = os.path.join(INPUT_DIR, uploaded_file.name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        if uploaded_file.name.endswith(".zip"):
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(INPUT_DIR)
                os.remove(file_path)
            except zipfile.BadZipFile:
                st.error(f"{uploaded_file.name} is not a valid ZIP file.")

    results = split_folder_intelligently(INPUT_DIR, max_chunk_size, OUTPUT_DIR)
    st.session_state["zip_results"] = results

# --- Display Results ---
results = st.session_state.get("zip_results", [])

if results:
    st.success("✅ Processing complete!")
    all_chunks = []

    for result in results:
        st.write(f"**📁 {result['original']}** ({humanfriendly.format_size(result['size'])})")
        for chunk in result["chunks"]:
            chunk_path = os.path.join(OUTPUT_DIR, chunk)
            all_chunks.append(chunk_path)
            with open(chunk_path, "rb") as f:
                st.download_button(
                    label=f"📥 Download {chunk}",
                    data=f.read(),
                    file_name=chunk,
                    mime="application/zip"
                )

    # Create combined ZIP
    all_zip_bytes = BytesIO()
    with zipfile.ZipFile(all_zip_bytes, 'w', zipfile.ZIP_DEFLATED) as allzip:
        for zip_path in all_chunks:
            allzip.write(zip_path, arcname=os.path.basename(zip_path))
    all_zip_bytes.seek(0)

    st.download_button(
        label="📦 Download All as ZIP",
        data=all_zip_bytes,
        file_name="ALL_CHUNKS.zip",
        mime="application/zip"
    )
