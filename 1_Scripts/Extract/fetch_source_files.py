import shutil
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "Common"))

from config import Fetch_Tasks, LOADING_ZONE_PATH

#Define a function to fetch files based on the config file
def fetch_files_from_config():
    print(f"Copying to: {LOADING_ZONE_PATH}\n")
    print("-" * 50)
    
    
    for task in Fetch_Tasks:
        source_dir = Path(task["source_path"]) 
        keyword = task["keywords"].lower()     
        
        if not source_dir.exists():
            print(f"❌ WARNING: Couldn't find {source_dir}，skipping for now.\n")
            continue
        
        #Temp storage for matched files    
        matched_files = []
        for file in source_dir.glob("*.xlsx"):
            file_name = file.name
            if keyword in file_name.lower() and not file_name.startswith("~$"):
                matched_files.append(file)
                
        if not matched_files:
            print(f"Couldn't find excel file with '{keyword}'\n")
            continue
            
        print(f"Found {len(matched_files)} matched files.")
        for file in matched_files:
            destination_file = LOADING_ZONE_PATH / file.name
            try:
                shutil.copy2(file, destination_file)
                print(f"File copied: {file.name}")
            except Exception as e:
                print(f"❌ WARNING: Failed and skipped ({file.name}): {e}")
            
        print("-" * 50)

    print("Finished fetching all files based on the config.")

if __name__ == "__main__":
    fetch_files_from_config()