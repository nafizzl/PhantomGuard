import os
from dotenv import load_dotenv

# Load .env file from workspace root using find_dotenv
from dotenv import find_dotenv
load_dotenv(find_dotenv(), override=True)

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
# Our custom fine-tuned Gemma 4 model adapter
FINE_TUNED_MODEL = "accounts/nafizzl/models/ft-w4dd2z1a-xxn0j"
# Standard base model as a fallback or for comparison
BASE_MODEL = "accounts/fireworks/models/deepseek-v4-pro"

# Security Settings
# If True, runs the fine-tuned model. If False, runs in Few-Shot In-Context learning mode on the base model.
USE_FINE_TUNED = True

# Server Configuration
HOST = "127.0.0.1"
PORT = 8000
