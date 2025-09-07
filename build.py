# build.py
import subprocess
import re
import sys
import os
from dotenv import load_dotenv

# This will allow running the script locally and seeing the same variables as in Docker
load_dotenv()

PROVIDER = os.getenv("LOCAL_MODEL_PROVIDER", "flux").lower()

if PROVIDER == "qwen":
    BENTO_BUILD_DIR = "bento_qwen_service"
elif PROVIDER == "flux":
    BENTO_BUILD_DIR = "bento_flux_service"
else:
    print(f"❌ ERROR: Unknown LOCAL_MODEL_PROVIDER: '{PROVIDER}'. Must be 'flux' or 'qwen'.")
    sys.exit(1)

# Common image name for Docker Compose
IMAGE_NAME = "local_ml_service:latest"
REQ_FILE = os.path.join(BENTO_BUILD_DIR, "requirements.txt")


def run_command(command: list[str]):
    """Runs a command and exits immediately in case of an error."""
    print(f"▶️ Running command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        print(f"❌ Command failed: {' '.join(command)}")
        sys.exit(1)


print(f"🚀 Building ML service for provider: {PROVIDER}")

# 1. Export dependencies
print("🧠 Exporting requirements from Poetry...")
run_command([
    "poetry",
    "export",
    "-f",
    "requirements.txt",
    "--output",
    REQ_FILE,
    "--without-hashes",
])

# 2. Собираем Bento и "ловим" его вывод
print(f"📦 Building Bento from '{BENTO_BUILD_DIR}' and capturing unique tag...")
result = subprocess.run(
    ["poetry", "run", "bentoml", "build", BENTO_BUILD_DIR],
    check=False,
    capture_output=True,
    text=True,
)

# Check for errors
if result.returncode != 0:
    print("❌ Bento build failed!")
    print("--- STDOUT ---")
    print(result.stdout)
    print("--- STDERR ---")
    print(result.stderr)
    sys.exit(1)

# 3. Extract the tag from the successful output
output = result.stdout
match = re.search(r'Successfully built Bento\(tag="(.*?)"\)', output)
if not match:
    print("❌ Could not find Bento tag in build output.")
    print(output)
    sys.exit(1)

bento_tag = match.group(1)
print(f"✅ Successfully built Bento with tag: {bento_tag}")

print(f"🐳 Building Docker image: {IMAGE_NAME}")
run_command([
    "poetry",
    "run",
    "bentoml",
    "containerize",
    bento_tag,
    "-t",
    IMAGE_NAME,
    "--opt",
    "no-cache",
])

print(f"\n🎉 Build process complete for {PROVIDER} provider!")
