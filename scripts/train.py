import os
import json
import urllib.request
import urllib.error
import time
import random
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FIREWORKS_API_KEY")
if not API_KEY:
    print("[Error] FIREWORKS_API_KEY environment variable not found.")
    print("Please set it in a .env file under the workspace root, or export it.")
    exit(1)

# Base API url
BASE_URL = "https://api.fireworks.ai/v1"

# Helper function to make JSON API calls
def api_request(method, path, payload=None, headers=None, content_type="application/json"):
    url = f"{BASE_URL}/{path}"
    req_headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    if headers:
        req_headers.update(headers)
        
    data = None
    if payload is not None:
        if isinstance(payload, bytes):
            data = payload
        else:
            data = json.dumps(payload).encode("utf-8")
            req_headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = response.read()
            if res_data:
                return json.loads(res_data.decode("utf-8"))
            return {}
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        print(f"[HTTP Error] {method} {path} returned status {e.code}: {error_msg}")
        raise e
    except Exception as e:
        print(f"[Error] Request failed: {e}")
        raise e

# Helper to construct multipart form-data body
def build_multipart_body(filename, file_data, boundary):
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/jsonl\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body

def get_account_id():
    print("Fetching Fireworks Account ID...")
    accounts_res = api_request("GET", "accounts")
    if "accounts" in accounts_res and len(accounts_res["accounts"]) > 0:
        # Get the first account name (which serves as the account ID in path parameters)
        # Account resource name format: "accounts/{account_id}"
        account_name = accounts_res["accounts"][0]["name"]
        account_id = account_name.split("/")[-1]
        print(f"Using Account ID: {account_id}")
        return account_id
    else:
        print("[Error] No accounts found associated with this API key.")
        exit(1)

def upload_dataset(account_id, file_path, dataset_id):
    print(f"Checking/Registering dataset placeholder '{dataset_id}'...")
    
    # Count examples in file
    example_count = 0
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            example_count = sum(1 for line in f if line.strip())
            
    # Try to register dataset
    payload = {
        "datasetId": dataset_id,
        "dataset": {
            "userUploaded": {},
            "exampleCount": example_count
        }
    }
    
    # If it already exists, registering might throw an error, so we catch it
    try:
        api_request("POST", f"accounts/{account_id}/datasets", payload=payload)
        print(f"  Registered dataset placeholder: {dataset_id}")
    except urllib.error.HTTPError as e:
        # 409 Conflict means it already exists, which is fine
        if e.code == 409:
            print(f"  Dataset placeholder '{dataset_id}' already exists.")
        else:
            raise e

    # Read the file content
    with open(file_path, "rb") as f:
        file_data = f.read()

    # Upload file
    print(f"Uploading file '{file_path}' to dataset '{dataset_id}'...")
    boundary = "----WebKitFormBoundary" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=16))
    body = build_multipart_body(os.path.basename(file_path), file_data, boundary)
    
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    
    upload_path = f"accounts/{account_id}/datasets/{dataset_id}:upload"
    try:
        api_request("POST", upload_path, payload=body, headers=headers)
        print(f"  Successfully uploaded {file_path} to dataset {dataset_id}")
    except urllib.error.HTTPError as e:
        if e.code == 400:
            print(f"  Dataset file for '{dataset_id}' already uploaded. Proceeding...")
        else:
            raise e

def trigger_fine_tune(account_id, train_id, val_id):
    # Unique job suffix
    job_suffix = str(int(time.time()))
    job_id = f"phantomguard-ft-{job_suffix}"
    
    payload = {
        "name": f"accounts/{account_id}/supervisedFineTuningJobs/{job_id}",
        "dataset": f"accounts/{account_id}/datasets/{train_id}",
        "baseModel": "accounts/fireworks/models/gemma-4-26b-a4b-it",
        "epochs": 3,
        "learningRate": 0.0001,
        "loraRank": 8
    }
    
    print(f"Triggering Supervised Fine-Tuning Job '{job_id}'...")
    job_path = f"accounts/{account_id}/supervisedFineTuningJobs"
    response = api_request("POST", job_path, payload=payload)
    print(f"Job triggered successfully! Resource name: {response.get('name')}")
    return job_id

def monitor_job(account_id, job_id):
    print(f"Monitoring fine-tuning job '{job_id}' status...")
    job_path = f"accounts/{account_id}/supervisedFineTuningJobs/{job_id}"
    
    while True:
        try:
            job = api_request("GET", job_path)
            state = job.get("state", "UNKNOWN")
            print(f"[{time.strftime('%H:%M:%S')}] Job State: {state}")
            
            if state in ["COMPLETED", "SUCCEEDED"]:
                print(f"\n[Success] Training completed successfully!")
                print(f"Your model adapter is available at:")
                print(f"  accounts/{account_id}/models/{job_id}")
                break
            elif state in ["FAILED", "CANCELLED"]:
                print(f"\n[Error] Fine-tuning job terminated with state: {state}")
                exit(1)
                
        except Exception as e:
            print(f"  Warning: Error retrieving status: {e}. Retrying...")
            
        time.sleep(30)

def main():
    account_id = get_account_id()
    
    train_dataset_id = "phantomguard-train-set"
    val_dataset_id = "phantomguard-val-set"
    
    # Upload datasets
    upload_dataset(account_id, "c:/Users/19295/PhantomGuard/data/train.jsonl", train_dataset_id)
    upload_dataset(account_id, "c:/Users/19295/PhantomGuard/data/val.jsonl", val_dataset_id)
    
    # Trigger Job
    job_id = trigger_fine_tune(account_id, train_dataset_id, val_dataset_id)
    
    # Monitor Job
    monitor_job(account_id, job_id)

if __name__ == "__main__":
    main()
