import urllib.request
import zipfile
import shutil
import os
from pathlib import Path

ZIP_URL = "https://github.com/Gamming-SERVICE/INTENT_BOT/archive/refs/tags/Intent%E2%84%A2_BOT_v2.2.zip"

TEMP_ZIP = "bot.zip"
EXTRACT_DIR = "extract"

print("[BOOTSTRAP] Downloading bot...")

urllib.request.urlretrieve(ZIP_URL, TEMP_ZIP)

print("[BOOTSTRAP] Extracting...")

with zipfile.ZipFile(TEMP_ZIP, "r") as zip_ref:
    zip_ref.extractall(EXTRACT_DIR)

root = next(Path(EXTRACT_DIR).iterdir())

print("[BOOTSTRAP] Installing files...")

for item in root.iterdir():
    target = Path(item.name)

    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    shutil.move(str(item), str(target))

print("[BOOTSTRAP] Done.")

os.remove(TEMP_ZIP)

print("[BOOTSTRAP] Bot installed successfully.")
