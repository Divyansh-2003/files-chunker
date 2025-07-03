import streamlit as st
import os
import zipfile
import shutil
from pathlib import Path
import tempfile
import humanfriendly

def get_folder_size(folder_path):
    """Calculate total size of a folder"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total += os.path.getsize(filepath)
    return total

def split_folder_intelligently(input_folder, max_chunk_size, output_dir):
    """Split folders while preserving structure and logical grouping"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all immediate subfolders
    subfolders = [f for f in Path(input_folder).iterdir() if f.is_dir()]
    
    results = []
    
    for subfolder in subfolders:
        folder_name = subfolder.name
        folder_size = get_folder_size(subfolder)
        
        if folder_size <= max_chunk_size:
            # Folder fits in one chunk
            zip_name = f"{folder_name}.zip"
            zip_path = os.path.join(output_dir, zip_name)
            create_zip_from_folder(subfolder, zip_path)
            results.append({
                'original': folder_name,
                'chunks': [zip_name],
                'size': folder_size
            })
        else:
            # Need to split this folder
            parts = split_large_folder(subfolder, folder_name, max_chunk_size, output_dir)
            results.append({
                'original': folder_name,
                'chunks': parts,
                'size': folder_size
            })
    
    return results

def split_large_folder(folder_path, folder_name, max_size, output_dir):
    """Split a large folder into multiple parts"""
    files = list(folder_path.rglob('*'))
    files = [f for f in files if f.is_file()]
    
    chunks = []
    current_chunk = []
    current_size = 0
    part_num = 1
    
    for file in files:
        file_size = os.path.getsize(file)
        
        if current_size + file_size > max_size and current_chunk:
            # Save current chunk
            zip_name = f"{folder_name}_part{part_num}.zip"
            zip_path = os.path.join(output_dir, zip_name)
            create_zip_from_files(current_chunk, zip_path, folder_path)
            chunks.append(zip_name)
            
            # Reset for next chunk
            current_chunk = []
            current_size = 0
            part_num += 1
        
        current_chunk.append(file)
        current_size += file_size
    
    # Save final chunk
    if current_chunk:
        zip_name = f"{folder_name}_part{part_num}.zip"
        zip_path = os.path.join(output_dir, zip_name)
        create_zip_from_files(current_chunk, zip_path, folder_path)
        chunks.append(zip_name)
    
    return chunks

def create_zip_from_folder(folder_path, zip_path):
    """Create zip from entire folder"""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(folder_path.parent)
                zipf.write(file_path, arcname)

def create_zip_from_files(files, zip_path, base_folder):
    """Create zip from list of files, preserving relative structure"""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files:
            arcname = file_path.relative_to(base_folder.parent)
            zipf.write(file_path, arcname)

# Streamlit UI
st.title("🗂️ Smart Folder Chunker")
st.write("Upload folders and split them intelligently while preserving structure")

# Sidebar controls
st.sidebar.header("Settings")
chunk_size_input = st.sidebar.text_input("Max chunk size", value="2MB")
try:
    max_chunk_size = humanfriendly.parse_size(chunk_size_input)
    st.sidebar.success(f"Chunk size: {humanfriendly.format_size(max_chunk_size)}")
except:
    st.sidebar.error("Invalid size format. Use: 2MB, 5MB, etc.")
    max_chunk_size = 2 * 1024 * 1024

# File upload
uploaded_files = st.file_uploader(
    "Upload files (they'll be organized by folder structure)",
    accept_multiple_files=True,
    type=None
)

if uploaded_files and st.button("Process Files"):
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create input structure
        input_dir = os.path.join(temp_dir, "input")
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(input_dir, exist_ok=True)
        
        # Save uploaded files (organize by folder if path info available)
        for uploaded_file in uploaded_files:
            file_path = os.path.join(input_dir, uploaded_file.name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
        
        # Process the files
        st.write("Processing...")
        results = split_folder_intelligently(input_dir, max_chunk_size, output_dir)
        
        # Display results
        st.success("✅ Processing complete!")
        
        for result in results:
            st.write(f"**{result['original']}** ({humanfriendly.format_size(result['size'])})")
            for chunk in result['chunks']:
                chunk_path = os.path.join(output_dir, chunk)
                if os.path.exists(chunk_path):
                    with open(chunk_path, "rb") as f:
                        st.download_button(
                            label=f"📥 Download {chunk}",
                            data=f.read(),
                            file_name=chunk,
                            mime="application/zip"
                        )
