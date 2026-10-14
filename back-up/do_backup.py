import os
import shutil
import sys
import re
from datetime import datetime

def perform_backup(title=None):
    backup_base = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(backup_base)
    
    # Generate timestamped folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Process optional title
    clean_title = ""
    if not title and len(sys.argv) > 1:
        title = " ".join(sys.argv[1:])
    
    if not title:
        title = os.environ.get("BACKUP_TITLE") or os.environ.get("BACKUP_DESC")
        
    if not title and sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        try:
            val = input("Enter a short description for this backup: ").strip()
            if val:
                title = val
        except Exception:
            pass
    
    if title:
        clean_title = str(title).strip()
        clean_title = re.sub(r'[\s\-]+', '_', clean_title)
        clean_title = re.sub(r'[^a-zA-Z0-9_]', '', clean_title).strip('_')
        if len(clean_title) > 60:
            clean_title = clean_title[:60].rstrip('_')

    if not clean_title:
        clean_title = "snapshot"
            
    folder_suffix = f"_{clean_title}" if clean_title else ""
    dest_dir = os.path.join(backup_base, f"backup_{timestamp}{folder_suffix}")
    
    print(f"Starting backup from '{src_dir}' to '{dest_dir}'...")
    
    # Ignored directories and files
    def ignore_patterns(path, names):
        ignored = []
        for name in names:
            name_lower = name.lower()
            if (name_lower in ["__pycache__", ".git", "back-up", "build", "dist", "chrome_profile", "user_data", "output", ".tmp", "tmp", ".temp", "temp", ".pytest_cache", ".system_generated", "venv", ".venv"] or 
                name_lower.endswith(".pyc") or 
                name_lower.endswith(".tmp") or 
                name_lower.endswith(".zip") or 
                name_lower.endswith(".db") or 
                name_lower.endswith(".sqlite") or 
                name_lower.endswith(".sqlite3") or 
                "-journal" in name_lower or 
                name_lower.endswith(".db-journal") or 
                name_lower.endswith(".db-wal") or 
                name_lower.endswith(".db-shm")):
                ignored.append(name)
        return ignored

    try:
        shutil.copytree(src_dir, dest_dir, ignore=ignore_patterns)
        try:
            os.utime(dest_dir, None)
        except Exception:
            pass
        print(f"SUCCESS: Backup folder created at '{dest_dir}'")

        # Create zip archive from the clean backup folder
        zip_suffix = f"_{clean_title}" if clean_title else ""
        zip_filename = f"IFMIS_VLC_Reconciliation_Backup_{timestamp}{zip_suffix}.zip"
        zip_dest = os.path.join(backup_base, zip_filename)
        print(f"Creating zip archive '{zip_dest}'...")
        shutil.make_archive(os.path.splitext(zip_dest)[0], 'zip', root_dir=dest_dir)
        zip_size_mb = os.path.getsize(zip_dest) / (1024 * 1024)
        print(f"SUCCESS: Source Backup Zip created: {zip_dest} ({zip_size_mb:.2f} MB)")

        # Also copy to '00 BACKUP FILES' if it exists
        central_backup_dir = r"D:\BUILDING and TESTING\00 BACKUP FILES"
        if os.path.isdir(central_backup_dir):
            central_zip = os.path.join(central_backup_dir, zip_filename)
            shutil.copy2(zip_dest, central_zip)
            print(f"SUCCESS: Also copied to '{central_zip}'")

        return {"folder": dest_dir, "zip": zip_dest}
    except Exception as e:
        print(f"ERROR: Backup failed: {e}")
        return None

if __name__ == "__main__":
    perform_backup()
