import json
import os
import sys
import time
import socket
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from phantomguard import config
from phantomguard.verifier.url_verifier import verify_url
from phantomguard.verifier.package_verifier import verify_package
from phantomguard.verifier.tool_verifier import verify_tool
from phantomguard.verifier.llm_client import query_llm

# Global state
TRUST_TRACE_LOGS = []
PENDING_REVIEWS = {}

class DaemonHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence access logs in terminal unless verbose
        return

    def do_GET(self):
        if self.path == "/":
            self.send_json_response({
                "status": "online",
                "service": "PhantomGuard Local Daemon",
                "fine_tuned_enabled": config.USE_FINE_TUNED,
                "model": config.FINE_TUNED_MODEL if config.USE_FINE_TUNED else config.BASE_MODEL
            })
        elif self.path == "/logs":
            self.send_json_response(TRUST_TRACE_LOGS)
        elif self.path == "/pending":
            serializable_pending = [
                {
                    "action_id": v["action_id"],
                    "timestamp": v["timestamp"],
                    "action_type": v["action_type"],
                    "target": v["target"],
                    "context": v["context"],
                    "category": v["category"],
                    "reason": v["reason"],
                    "confidence": v["confidence"]
                } for v in PENDING_REVIEWS.values()
            ]
            self.send_json_response(serializable_pending)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception:
            self.send_error(400, "Bad Request: Invalid JSON")
            return

        if self.path == "/verify":
            action_type = payload.get("action_type")
            target = payload.get("target")
            context = payload.get("context", "")
            
            if not action_type or not target:
                self.send_error(400, "Missing action_type or target")
                return
                
            res = self.evaluate_pipeline(action_type, target, context)
            self.send_json_response(res)
            
        elif self.path == "/decide":
            action_id = payload.get("action_id")
            approved = payload.get("approved")
            
            if not action_id or approved is None:
                self.send_error(400, "Missing action_id or approved")
                return
                
            if action_id not in PENDING_REVIEWS:
                self.send_error(404, "Pending review not found")
                return
                
            pending = PENDING_REVIEWS[action_id]
            pending["approved"] = approved
            pending["event"].set()  # Release the blocking thread
            
            self.send_json_response({"status": "success", "action_id": action_id, "approved": approved})
        else:
            self.send_error(404, "Not Found")

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        # Support CORS preflight
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def evaluate_pipeline(self, action_type: str, target: str, context: str) -> dict:
        """
        Executes the compliance-upgraded hybrid decision pipeline.
        """
        action_id = str(time.time())
        timestamp = time.strftime("%H:%M:%S")
        
        # Default fallback values
        is_hallucination = False
        confidence = 0.99
        category = "none"
        reason = "Clean execution"
        backend_used = "local"
        
        # ----------------------------------------------------
        # STAGE 1: Local Network Heuristics (DNS/HEAD checks)
        # ----------------------------------------------------
        # For URL checks, run DNS & http check first
        local_check_fail = False
        if action_type == "url_fetch":
            local_res = verify_url(target, context)
            if local_res["is_hallucination"] and local_res["category"] == "usability":
                # Instant usability block
                is_hallucination = True
                confidence = local_res["confidence"]
                category = "usability"
                reason = local_res["reason"]
                local_check_fail = True
            elif not local_res["is_hallucination"]:
                # If local resolved and exact clean domain match, skip SFT
                reason = local_res["reason"]
                local_check_fail = False

        # ----------------------------------------------------
        # STAGE 2: AMD ROCm Embedding Similarity Check
        # ----------------------------------------------------
        similarity_flagged = False
        exact_bypass = False
        
        if not local_check_fail and config.AMD_NOTEBOOK_URL and action_type in ["url_fetch", "package_install"]:
            try:
                type_map = "url" if action_type == "url_fetch" else "package"
                sim_payload = {"target": target, "type": type_map}
                
                req = urllib.request.Request(
                    f"{config.AMD_NOTEBOOK_URL}/similarity",
                    data=json.dumps(sim_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                
                # Hard 2.0s timeout limit to prevent flakiness from blocking workflow
                with urllib.request.urlopen(req, timeout=2.0) as res:
                    sim_res = json.loads(res.read().decode("utf-8"))
                    
                    if sim_res.get("is_exact_match"):
                        exact_bypass = True
                        backend_used = "amd_notebook_rocm"
                        reason = f"Exact match bypass: verified safe brand/package: {sim_res.get('best_match')}"
                    elif sim_res.get("is_suspicious_conflation"):
                        similarity_flagged = True
                        backend_used = "amd_notebook_rocm"
                        is_hallucination = True
                        confidence = sim_res.get("similarity_score", 0.9)
                        category = "security"
                        reason = f"[AMD Similarity Flag] Requested '{target}' semantically resembles verified brand '{sim_res.get('best_match')}' ({int(confidence*100)}% match). High typosquatting risk."
                        
            except Exception as e:
                print(f"[Daemon Stage 2 Warning] AMD ROCm Notebook check timed out or failed: {e}. Falling back to Stage 3.")

        # ----------------------------------------------------
        # STAGE 3: Fireworks SFT LoRA / Few-Shot LLM
        # ----------------------------------------------------
        if not local_check_fail and not exact_bypass and not similarity_flagged:
            # Query SFT classifier (or fallback few-shot)
            if action_type == "url_fetch":
                res = verify_url(target, context)
            elif action_type == "package_install":
                res = verify_package(target, context)
            elif action_type == "tool_execution":
                res = verify_tool(target, context)
            else:
                res = {"is_hallucination": False, "confidence": 0.5, "reason": "Unsupported type", "category": "none"}
                
            is_hallucination = res["is_hallucination"]
            confidence = res["confidence"]
            category = res.get("category", "none")
            reason = res["reason"]
            backend_used = "fireworks_lora" if config.USE_FINE_TUNED else "gemma4_fewshot"

        # ----------------------------------------------------
        # STAGE 4: Human-in-the-Loop Escalation
        # ----------------------------------------------------
        log_entry = {
            "action_id": action_id,
            "timestamp": timestamp,
            "action_type": action_type,
            "target": target,
            "context": context,
            "is_hallucination": is_hallucination,
            "confidence": confidence,
            "category": category,
            "reason": reason,
            "compute_backend": backend_used,
            "allowed": not is_hallucination,
            "decision_source": "automatic"
        }

        if is_hallucination:
            # Set up human block event
            event = threading.Event()
            PENDING_REVIEWS[action_id] = {
                "action_id": action_id,
                "timestamp": timestamp,
                "action_type": action_type,
                "target": target,
                "context": context,
                "category": category,
                "reason": reason,
                "confidence": confidence,
                "event": event,
                "approved": None
            }
            
            print(f"\n[FIREWALL BLOCKED] Intervention active on action: {target}")
            print(f"  Reason: {reason}")
            print(f"  Awaiting human verification in dashboard/CLI...")
            
            # Wait for human input (or timeout after 60 seconds)
            success = event.wait(timeout=60.0)
            
            if success:
                approved = PENDING_REVIEWS[action_id]["approved"]
                decision_source = "human"
            else:
                # Fail-secure default
                approved = False
                decision_source = "timeout"
                print(f"  [Timeout] Human review timed out. Defaulting to BLOCK.")
                
            PENDING_REVIEWS.pop(action_id, None)
            
            log_entry["allowed"] = approved
            log_entry["decision_source"] = decision_source
            if not approved:
                log_entry["reason"] = f"[Blocked by {decision_source.upper()}] {reason}"
                log_entry["compute_backend"] = "human_in_the_loop"

        # Save trace
        TRUST_TRACE_LOGS.append(log_entry)
        return log_entry

def run_daemon():
    # PID Lockfile management
    pid = str(os.getpid())
    try:
        with open(config.PID_FILE, "w") as f:
            f.write(pid)
    except Exception as e:
        print(f"Warning: Could not create PID file: {e}")

    server_address = (config.DAEMON_HOST, config.DAEMON_PORT)
    httpd = HTTPServer(server_address, DaemonHTTPHandler)
    
    print(f"\n=======================================================")
    print(f"  PHANTOMGUARD SECURE DAEMON ACTIVE")
    print(f"=======================================================")
    print(f"Port:             {config.DAEMON_PORT}")
    print(f"Default Adapter:  {config.FINE_TUNED_MODEL}")
    print(f"Notebook Sync:    {config.AMD_NOTEBOOK_URL or 'OFFLINE'}")
    print(f"PID File:         {config.PID_FILE} (PID {pid})")
    print(f"=======================================================\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup
        if os.path.exists(config.PID_FILE):
            os.remove(config.PID_FILE)
        print("Daemon stopped.")

if __name__ == "__main__":
    run_daemon()
