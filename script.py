import os
import pathlib
import shutil
import logging

# --- Google Drive Imports ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# --- Basic Configuration ---
REPO_PATH = "."
MAX_FILE_SIZE_KB = 100
INCLUDE_EXTENSIONS = [".py", ".sh", '.yml', '.bot', '.md']
EXCLUDE_NAMES = ["__init__"]
OUTPUT_DIR_NAME = "family_bot"
ZIP_ARCHIVE_NAME = "family_bot_archive.zip"

# --- Google Drive Configuration ---
GDRIVE_CREDENTIALS_FILE = 'credentials.json'
GDRIVE_TOKEN_FILE = 'token.json'
# This scope allows the script to create, modify, and delete files it has created.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def print_tree(root_path):
    # This function remains unchanged
    tree_lines = []
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        level = root.replace(root_path, "").count(os.sep)
        indent = "  " * level
        if "pycache" not in os.path.basename(root) and os.path.basename(root) != OUTPUT_DIR_NAME:
            tree_lines.append(f"{indent}{os.path.basename(root)}/")
            subindent = "  " * (level + 1)
            for f in files:
                if "pyc" not in f:
                    tree_lines.append(f"{subindent}{f}")
    return "\n".join(tree_lines)

def is_hidden_path(path, root_path):
    # This function remains unchanged
    rel_path = os.path.relpath(path, root_path)
    parts = rel_path.split(os.sep)
    if rel_path == '.':
        return False
    return any(part.startswith(".") for part in parts)

def collect_files(root_path, output_dir):
    # This function remains mostly unchanged, just using the constant
    os.makedirs(output_dir, exist_ok=True)
    output_dir_abs = os.path.abspath(output_dir)
    saved_files = []

    for root, dirs, files in os.walk(root_path):
        abs_root = os.path.abspath(root)
        dirs[:] = [d for d in dirs if not d.startswith(".") and os.path.abspath(os.path.join(root, d)) != output_dir_abs]

        if is_hidden_path(abs_root, root_path) or abs_root == output_dir_abs:
            continue

        for file in files:
            path = os.path.join(root, file)
            if is_hidden_path(path, root_path):
                continue

            if any(file.endswith(ext) for ext in INCLUDE_EXTENSIONS) and not any(file.startswith(ex) for ex in EXCLUDE_NAMES):
                size_kb = pathlib.Path(path).stat().st_size / 1024
                if size_kb <= MAX_FILE_SIZE_KB:
                    rel_path = os.path.relpath(path, root_path)
                    target_path = os.path.join(output_dir, rel_path.replace(os.sep, "__"))
                    for ext in INCLUDE_EXTENSIONS:
                        target_path = target_path.replace(ext, ".txt")
                    
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with (
                        open(path, encoding="utf-8", errors="ignore") as fin,
                        open(target_path, "w", encoding="utf-8") as fout,
                    ):
                        fout.write(fin.read())
                    saved_files.append(target_path)
    return saved_files

def create_zip_archive(source_dir, archive_name):
    """Creates a zip archive from the source directory."""
    logging.info(f"📦 Creating zip archive '{archive_name}' from '{source_dir}'...")
    try:
        # We remove the .zip extension for the function, it adds it automatically
        shutil.make_archive(archive_name.replace('.zip', ''), 'zip', source_dir)
        logging.info(f"✅ Zip archive created successfully.")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to create zip archive: {e}")
        return False

def authenticate_gdrive():
    """Handles Google Drive authentication flow."""
    creds = None
    if os.path.exists(GDRIVE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GDRIVE_TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            logging.info("Performing one-time authentication...")
            if not os.path.exists(GDRIVE_CREDENTIALS_FILE):
                logging.error(f"❌ ERROR: Credentials file '{GDRIVE_CREDENTIALS_FILE}' not found.")
                logging.error("Please follow the setup instructions to download it from Google Cloud Console.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(GDRIVE_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(GDRIVE_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logging.info(f"Credentials saved to '{GDRIVE_TOKEN_FILE}'.")
            
    try:
        service = build('drive', 'v3', credentials=creds)
        logging.info("✅ Successfully authenticated with Google Drive.")
        return service
    except HttpError as error:
        logging.error(f"An error occurred during authentication: {error}")
        return None

def upload_or_update_file_on_drive(service, file_path, file_name):
    """Uploads a file to Google Drive, overwriting if it already exists."""
    logging.info(f"☁️ Starting upload process for '{file_name}' to Google Drive...")
    
    try:
        # Search for the file on Drive
        response = service.files().list(
            q=f"name='{file_name}' and trashed=false",
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        files = response.get('files', [])

        media = MediaFileUpload(file_path, mimetype='application/zip')
        
        if files:
            # File exists, update it
            file_id = files[0].get('id')
            logging.info(f"File '{file_name}' found on Drive with ID: {file_id}. Updating it...")
            updated_file = service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            logging.info(f"✅ File updated successfully. ID: {updated_file.get('id')}")
        else:
            # File does not exist, create it
            logging.info(f"File '{file_name}' not found on Drive. Creating new file...")
            file_metadata = {'name': file_name}
            new_file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            logging.info(f"✅ File uploaded successfully. ID: {new_file.get('id')}")
    
    except HttpError as error:
        logging.error(f"❌ An error occurred while uploading to Google Drive: {error}")
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    # 1. Clean up old output directory
    logging.info(f"🗑️ Cleaning up previous output directory '{OUTPUT_DIR_NAME}'...")
    if os.path.exists(OUTPUT_DIR_NAME):
        shutil.rmtree(OUTPUT_DIR_NAME)
    
    # # 2. Print repository structure and collect files
    # logging.info("📂 Repository structure:")
    # print(print_tree(REPO_PATH))

    logging.info("\n📄 Extracting files for upload...")
    files = collect_files(REPO_PATH, OUTPUT_DIR_NAME)
    logging.info(f"✅ {len(files)} files saved to '{OUTPUT_DIR_NAME}'.")

    # 3. Create a zip archive of the output directory
    if files:
        if create_zip_archive(OUTPUT_DIR_NAME, ZIP_ARCHIVE_NAME):
            # 4. Authenticate and upload to Google Drive
            drive_service = authenticate_gdrive()
            if drive_service:
                upload_or_update_file_on_drive(drive_service, ZIP_ARCHIVE_NAME, ZIP_ARCHIVE_NAME)
    else:
        logging.warning("No files were collected, skipping zip and upload.")

    print("\n🎉 Script finished.")