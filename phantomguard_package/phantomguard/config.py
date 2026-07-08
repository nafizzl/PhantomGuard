import os
from dotenv import load_dotenv

# Load env variables from current directory
from dotenv import load_dotenv, find_dotenv
dotenv_file = find_dotenv(usecwd=True)
load_status = load_dotenv(dotenv_file, override=True)

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
AMD_NOTEBOOK_URL = os.getenv("AMD_NOTEBOOK_URL")

print(f"[Debug Config] find_dotenv found: {repr(dotenv_file)}")
print(f"[Debug Config] load_status return: {load_status}")
print(f"[Debug Config] config.FIREWORKS_API_KEY evaluated to: {repr(FIREWORKS_API_KEY)}")

# Our default trained model adapter path
DEFAULT_SFT_MODEL = "accounts/nafizzl/models/ft-w4dd2z1a-xxn0j"
# Standard base model fallback
DEFAULT_BASE_MODEL = "accounts/fireworks/models/deepseek-v4-pro"

# Model configuration path overrides
FINE_TUNED_MODEL = os.getenv("PHANTOMGUARD_MODEL", DEFAULT_SFT_MODEL)
BASE_MODEL = DEFAULT_BASE_MODEL

# Control configuration flags
USE_FINE_TUNED = True

# Daemon and Proxy network settings
DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 8001
PROXY_PORT = 8000
PID_FILE = "phantomguard.pid"
