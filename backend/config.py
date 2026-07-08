import os
from dotenv import load_dotenv

# Load .env file from root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
# Our custom fine-tuned Gemma 4 model adapter
FINE_TUNED_MODEL = "accounts/nafizzl/models/ft-w4dd2z1a-xxn0j"
# Standard base model as a fallback or for comparison
BASE_MODEL = "accounts/fireworks/models/gemma-4-26b-a4b-it"

# Security Settings
# If True, runs the fine-tuned model. If False, runs in Few-Shot In-Context learning mode on the base model.
USE_FINE_TUNED = True

# Server Configuration
HOST = "127.0.0.1"
PORT = 8000
