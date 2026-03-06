import os
import requests
import zipfile
import shutil
import sys
import json
from io import BytesIO

# URL of the GitHub repository ZIP file.
# The branch is now correctly set to 'main' based on user feedback,
# but the updater will fail for private repos without a token.
ZIP_URL = "https://github.com/paulweimert2006-commits/JULES_WEB4/archive/refs/heads/main.zip"

# Get the root directory of the application.
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_FILE = os.path.join(APP_ROOT, 'acencia_hub', 'data', 'secrets.json')

# List of files and directories to exclude from being overwritten during an update.
EXCLUSIONS = [
    ".git",
    "venv",
    ".idea",
    "__pycache__",
    "_snapshots",
    "_history",
    "exports",
    os.path.join("acencia_hub", "data"),
    os.path.join("acencia_hub", "updater.py"),
    "start.bat",
]

def load_secrets():
    """
    Lädt Geheimnisse aus der JSON-Datei.
    
    Returns:
        dict: Dictionary der Geheimnisse oder leeres Dictionary bei Fehlern
    """
    if not os.path.exists(SECRETS_FILE):
        return {}
    with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

def is_excluded(path, root_dir):
    """
    Überprüft, ob ein gegebener Pfad ausgeschlossen werden soll.
    
    Args:
        path (str): Der zu überprüfende Pfad
        root_dir (str): Das Root-Verzeichnis für relative Pfadberechnungen
    
    Returns:
        bool: True, wenn der Pfad ausgeschlossen werden soll, False sonst
    """
    relative_path = os.path.normpath(os.path.relpath(path, root_dir))
    for exclusion in EXCLUSIONS:
        if relative_path.startswith(os.path.normpath(exclusion)):
            return True
    return False

def copy_files(source_dir, target_dir):
    """
    Kopiert Dateien von der Quelle zum Ziel und respektiert dabei Ausschlüsse.
    
    Args:
        source_dir (str): Das Quellverzeichnis
        target_dir (str): Das Zielverzeichnis
    
    Returns:
        None
    """
    print(f"[Updater] Copying new files from {source_dir} to {target_dir}")
    for item in os.listdir(source_dir):
        source_item = os.path.join(source_dir, item)
        target_item = os.path.join(target_dir, item)

        if is_excluded(target_item, target_dir):
            print(f"[Updater] -> Skipping excluded path: {target_item}")
            continue

        if os.path.isdir(source_item):
            if not os.path.exists(target_item):
                os.makedirs(target_item)
            copy_files(source_item, target_item)
        else:
            shutil.copy2(source_item, target_item)
            # print(f"[Updater] -> Updated file: {target_item}") # This is too verbose

def run_update():
    """
    Hauptfunktion zum Ausführen des gesamten Update-Prozesses.
    
    Lädt die neueste Version von GitHub herunter, extrahiert sie und
    kopiert die Dateien unter Berücksichtigung der Ausschlüsse.
    
    Returns:
        bool: True, wenn das Update erfolgreich war, False bei Fehlern
    """
    temp_extract_path = os.path.join(APP_ROOT, "update_temp")

    try:
        # --- 0. Load secrets ---
        secrets = load_secrets()
        pat = secrets.get('github_pat')
        if not pat:
            print("[Updater] WARN: GitHub Personal Access Token not found. Skipping update check.", file=sys.stderr)
            print("[Updater] WARN: Please set the token in Master Settings to enable updates.", file=sys.stderr)
            return False

        # --- 1. Download the ZIP file ---
        print(f"[Updater] Downloading latest version from GitHub...")
        headers = {"Authorization": f"token {pat}"}
        response = requests.get(ZIP_URL, headers=headers, timeout=30)
        response.raise_for_status()
        zip_content = BytesIO(response.content)
        print("[Updater] Download complete.")

        # --- 2. Extract the ZIP file ---
        print(f"[Updater] Extracting files to temporary directory: {temp_extract_path}")
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path)
        os.makedirs(temp_extract_path)

        with zipfile.ZipFile(zip_content, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_path)
        print("[Updater] Extraction complete.")

        extracted_folders = os.listdir(temp_extract_path)
        if not extracted_folders:
            raise Exception("ZIP file was empty after extraction.")

        source_root = os.path.join(temp_extract_path, extracted_folders[0])
        if not os.path.isdir(source_root):
             raise Exception(f"Could not find the root directory inside the extracted ZIP: {source_root}")

        # --- 3. Copy new files ---
        copy_files(source_root, APP_ROOT)
        print("[Updater] File update process complete.")
        return True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print("[Updater] ERROR: 404 Not Found. The repository URL or branch name is likely incorrect.", file=sys.stderr)
        elif e.response.status_code == 401:
            print("[Updater] ERROR: 401 Unauthorized. Your GitHub Personal Access Token is likely invalid or has expired.", file=sys.stderr)
        else:
            print(f"[Updater] ERROR: Failed to download update due to an HTTP error: {e}", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"[Updater] ERROR: Failed to download update. Please check your internet connection. Details: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[Updater] ERROR: An unexpected error occurred during the update process: {e}", file=sys.stderr)
        return False
    finally:
        # --- 4. Clean up ---
        if os.path.exists(temp_extract_path):
            try:
                shutil.rmtree(temp_extract_path)
            except OSError as e:
                print(f"[Updater] WARN: Could not remove temporary extraction directory: {e}", file=sys.stderr)
