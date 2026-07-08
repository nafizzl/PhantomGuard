import os
import json
import urllib.request
import urllib.error
import time
import random

# Helper to read .env file manually if python-dotenv is not installed
def load_env():
    env_path = "c:/Users/19295/Agent Trust Firewall/.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

load_env()

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
    
    # Try to register dataset
    payload = {
        "datasetId": dataset_id,
        "dataset": {
            "userUploaded": {}
        }
    }
    
    # If it already exists, registering might throw an error, so we catch it
    try:
        api_request("POST", "datasets", payload=payload)
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
    api_request("POST", upload_path, payload=body, headers=headers)
    print(f"  Successfully uploaded {file_path} to dataset {dataset_id}")

def trigger_fine_tune(account_id, train_id, val_id):
    # Unique job suffix
    job_suffix = str(int(time.time()))
    job_id = f"phantomguard-ft-{job_suffix}"
    
    payload = {
        "supervisedFineTuningJob": {
            "name": f"accounts/{account_id}/supervisedFineTuningJobs/{job_id}",
            "dataset": f"accounts/{account_id}/datasets/{train_id}",
            "validationDataset": f"accounts/{account_id}/datasets/{val_id}",
            "model": "accounts/fireworks/models/gemma-4-26b-a4b-it",
            "hyperparameters": {
                "learningRate": 0.0001,
                "epochs": 3,
                "loraRank": 8
            }
        }
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
    
    train_dataset_id = "phantomguard_train_set"
    val_dataset_id = "phantomguard_val_set"
    
    # Upload datasets
    upload_dataset(account_id, "c:/Users/19295/Agent Trust Firewall/data/train.jsonl", train_dataset_id)
    upload_dataset(account_id, "c:/Users/19295/Agent Trust Firewall/data/val.jsonl", val_dataset_id)
    
    # Trigger Job
    job_id = trigger_fine_tune(account_id, train_dataset_id, val_dataset_id)
    
    # Monitor Job
    monitor_job(account_id, job_id)

if __name__ == "__main__":
    main()
