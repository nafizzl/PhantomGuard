import os
import json
import urllib.request
import urllib.error
import time
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

AMD_NOTEBOOK_URL = os.getenv("AMD_NOTEBOOK_URL")
if not AMD_NOTEBOOK_URL:
    print("[Error] AMD_NOTEBOOK_URL environment variable not found in .env.")
    print("Please set AMD_NOTEBOOK_URL pointing to your ngrok tunnel.")
    exit(1)

def send_post_request(path, payload):
    url = f"{AMD_NOTEBOOK_URL.rstrip('/')}/{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[Error] POST {path} failed: {e}")
        raise e

def send_get_request(path):
    url = f"{AMD_NOTEBOOK_URL.rstrip('/')}/{path}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"[Error] GET {path} failed: {e}")
        raise e

def main():
    print(f"Connecting to AMD ROCm Notebook Server at: {AMD_NOTEBOOK_URL}")
    
    # 1. Read local dataset files
    train_path = "c:/Users/19295/PhantomGuard/demo_app/data/train.jsonl"
    val_path = "c:/Users/19295/PhantomGuard/demo_app/data/val.jsonl"
    
    if not os.path.exists(train_path) or not os.path.exists(val_path):
        print("[Error] Dataset files not found under demo_app/data/")
        exit(1)
        
    print("Reading dataset files...")
    with open(train_path, "r", encoding="utf-8") as f:
        train_data = f.read()
    with open(val_path, "r", encoding="utf-8") as f:
        val_data = f.read()
        
    # 2. Trigger SFT training on the ROCm server
    payload = {
        "train_data": train_data,
        "val_data": val_data,
        "epochs": 3,
        "learning_rate": 2e-4
    }
    
    print("Uploading datasets and triggering SFT job on ROCm GPU...")
    try:
        trigger_res = send_post_request("train", payload)
        job_id = trigger_res.get("job_id")
        print(f"Job triggered successfully! Job ID: {job_id}")
    except Exception as e:
        print(f"Failed to start training: {e}")
        exit(1)
        
    # 3. Monitor SFT Training progress
    print(f"Monitoring SFT job '{job_id}' status...")
    while True:
        try:
            status_res = send_get_request(f"train/status?job_id={job_id}")
            state = status_res.get("state", "UNKNOWN")
            progress = status_res.get("progress", "")
            
            print(f"[{time.strftime('%H:%M:%S')}] State: {state} {progress}")
            
            if state == "COMPLETED":
                print("\n[Success] Local training completed successfully on AMD ROCm GPU!")
                print(f"Trained adapter location on notebook server: {status_res.get('model_dir')}")
                break
            elif state in ["FAILED", "CANCELLED"]:
                print(f"\n[Error] Training job failed: {status_res.get('error')}")
                exit(1)
        except Exception as e:
            print(f"  Warning: Error retrieving status: {e}. Retrying in 10s...")
            
        time.sleep(20)

if __name__ == "__main__":
    main()
