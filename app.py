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

# --- Remaining code unchanged (create_final_zip, Streamlit UI, etc.) ---
