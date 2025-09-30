# download_models.py
import os
from insightface.app import FaceAnalysis

print("Initializing InsightFace FaceAnalysis to download models...")
print("This may take a few minutes depending on your internet connection.")

# This line will trigger the download of the 'buffalo_l' model pack
# to the default cache directory (~/.insightface/models).
app = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))

# Get the home directory and construct the model path
home_dir = os.path.expanduser("~")
model_path = os.path.join(home_dir, ".insightface", "models")

print("\n✅ Models have been successfully downloaded and cached.")
print(f"   Model directory: {model_path}")
print("\nYou can now proceed with the Docker setup.")