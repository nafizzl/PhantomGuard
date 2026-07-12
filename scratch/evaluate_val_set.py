import os
import json
import re
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from phantomguard.verifier.llm_client import query_llm
from phantomguard import config

def evaluate(model_type):
    # Determine model endpoint & target output log path inside scratch directory
    root_dir = "c:\\Users\\19295\\PhantomGuard"
    
    if model_type == "base":
        model_endpoint = "accounts/nafizzl/deployments/keq4aznj"
        log_name = "base_gemma4_26b.log"
    else:
        model_endpoint = "accounts/nafizzl/models/ft-w4dd2z1a-xxn0j#accounts/nafizzl/deployments/o8i5az0k"
        log_name = "custom_gemma4_sft.log"
        
    config.USE_FINE_TUNED = True
    config.FINE_TUNED_MODEL = model_endpoint
    api_key = config.FIREWORKS_API_KEY
    
    val_path = "c:\\Users\\19295\\PhantomGuard\\demo_app\\data\\val.jsonl"
    url_fetch_examples = []

    # 1. Parse validation dataset
    with open(val_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            user_content = data["messages"][1]["content"]
            assistant_content = json.loads(data["messages"][2]["content"])
            
            if "action: url_fetch" in user_content:
                target_match = re.search(r"Target:\s*([^\s|]+)", user_content)
                context_match = re.search(r"Context:\s*(.*)", user_content)
                if target_match and context_match:
                    url_fetch_examples.append({
                        "target": target_match.group(1).strip(),
                        "context": context_match.group(1).strip(),
                        "expected": assistant_content["is_hallucination"]
                    })

    print(f"Evaluating {len(url_fetch_examples)} items on model {model_endpoint}...")
    results = [None] * len(url_fetch_examples)

    def eval_single(idx, item):
        target = item["target"]
        context = item["context"]
        expected = item["expected"]
        
        user_content = f"Evaluate action: url_fetch | Target: {target} | Context: {context}"
        payload = {
            "model": model_endpoint,
            "messages": [
                {"role": "system", "content": 'You are a security classifier. Output JSON: {"is_hallucination": true/false, "confidence": 0.0-1.0, "reason": "string"}'},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1,
            "max_tokens": 500,
            "response_format": {"type": "json_object"}
        }
        
        url = "https://api.fireworks.ai/inference/v1/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST"
        )
        
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=30.0) as response:
                    res_body = json.loads(response.read().decode("utf-8"))
                    content_str = res_body["choices"][0]["message"].get("content", "")
                    
                    # Robust extraction of the first JSON block
                    start_idx = content_str.find('{')
                    end_idx = content_str.find('}')
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        json_str = content_str[start_idx:end_idx+1]
                    else:
                        json_str = content_str
                        
                    result = json.loads(json_str)
                    actual = bool(result.get("is_hallucination", False))
                    is_correct = (expected == actual)
                    return idx, {
                        "target": target,
                        "expected": "Blocked" if expected else "Allowed",
                        "actual": "Blocked" if actual else "Allowed",
                        "status": "Correct" if is_correct else "Incorrect",
                        "is_correct": is_correct
                    }
            except Exception as e:
                if attempt == 0:
                    continue
                return idx, {
                    "target": target,
                    "expected": "Blocked" if expected else "Allowed",
                    "actual": f"Error: {e}",
                    "status": "Error",
                    "is_correct": False
                }

    correct_count = 0
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(eval_single, idx, item) for idx, item in enumerate(url_fetch_examples)]
        for future in as_completed(futures):
            idx, res = future.result()
            results[idx] = res
            if res and res["is_correct"]:
                correct_count += 1
            completed = sum(1 for r in results if r is not None)
            if completed % 25 == 0 or completed == len(url_fetch_examples):
                print(f"  Progress: {completed}/{len(url_fetch_examples)} completed.")

    # 2. Write Results to Log File in scratch directory
    log_path = os.path.join(root_dir, log_name)
    with open(log_path, "w", encoding="utf-8") as lf:
        lf.write(f"Loaded {len(url_fetch_examples)} url_fetch validation samples.\n")
        lf.write(f"Evaluating strictly on SFT model: {model_endpoint} in parallel...\n\n")
        lf.write("| Domain | Validation Result | Actual Result | Status |\n")
        lf.write("| :--- | :---: | :---: | :---: |\n")
        for res in results:
            if res:
                lf.write(f"| `{res['target']}` | {res['expected']} | {res['actual']} | {res['status']} |\n")
        accuracy_pct = (correct_count / len(url_fetch_examples)) * 100
        lf.write(f"\nFinal Score: {correct_count} / {len(url_fetch_examples)} correct\n")
        lf.write(f"Accuracy: {accuracy_pct:.2f}%\n")

    print(f"Saved evaluation results log to: {log_path}")

if __name__ == "__main__":
    import urllib.request
    parser = argparse.ArgumentParser(description="Evaluate validation dataset on model endpoints.")
    parser.add_argument("--model", required=True, choices=["base", "custom"], help="Which model to evaluate: 'base' or 'custom'")
    args = parser.parse_args()
    evaluate(args.model)
