import os
import subprocess
import glob
import math
import shutil

REPO_URL = "https://github.com/openshift/runbooks.git"
REPO_DIR = "periodic_runbooks_repo"
OUTPUT_DIR = "extracted_runbooks"
NUM_OUTPUT_FILES = 5

import stat

def remove_readonly(func, path, _):
    """Clear the readonly bit and reattempt the removal"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def clone_or_update_repo():
    """Clones the repository afresh to ensure we have the latest updates."""
    if os.path.exists(REPO_DIR):
        print(f"Directory '{REPO_DIR}' already exists. Removing it to fetch a fresh copy...")
        shutil.rmtree(REPO_DIR, onerror=remove_readonly)
        
    print(f"Cloning repository into '{REPO_DIR}'...")
    subprocess.run(
        ["git", "clone", "--depth", "1", REPO_URL, REPO_DIR], 
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print("Clone complete.")

def extract_files():
    """Finds all markdown files and combines them into 5 evenly split text files."""
    alerts_dir = os.path.join(REPO_DIR, "alerts")
    
    # Recursively find all markdown files in the alerts directory
    md_files = glob.glob(os.path.join(alerts_dir, "**", "*.md"), recursive=True)
    
    if not md_files:
        print("No markdown files found in the alerts directory.")
        return

    # Sort files to ensure deterministic behavior across runs
    md_files.sort()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Found {len(md_files)} markdown files. Combining into {NUM_OUTPUT_FILES} files in '{OUTPUT_DIR}/'...")
    
    # Calculate chunk sizes to distribute files evenly across 5 chunks
    chunk_size = math.ceil(len(md_files) / NUM_OUTPUT_FILES)
    
    for chunk_idx in range(NUM_OUTPUT_FILES):
        start_idx = chunk_idx * chunk_size
        end_idx = min(start_idx + chunk_size, len(md_files))
        
        chunk_files = md_files[start_idx:end_idx]
        
        if not chunk_files:
            continue
            
        output_filepath = os.path.join(OUTPUT_DIR, f"combined_runbooks_part_{chunk_idx + 1}.txt")
        
        with open(output_filepath, "w", encoding="utf-8") as out_f:
            for filepath in chunk_files:
                relative_path = os.path.relpath(filepath, start=REPO_DIR)
                
                # Write the header comment
                out_f.write(f"<!-- ========================================== -->\n")
                out_f.write(f"<!-- Source Path: {relative_path} -->\n")
                out_f.write(f"<!-- ========================================== -->\n\n")
                
                # Read and write the markdown content
                try:
                    with open(filepath, "r", encoding="utf-8") as in_f:
                        content = in_f.read()
                    out_f.write(content)
                except Exception as e:
                    out_f.write(f"<!-- Error reading file: {e} -->\n")
                    
                # Add spacing between combined files
                out_f.write("\n\n\n")
                
        print(f"  -> Created '{output_filepath}' containing {len(chunk_files)} alerts.")

if __name__ == "__main__":
    print("Starting periodic runbook extraction task...")
    try:
        clone_or_update_repo()
        extract_files()
        print("Task completed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
