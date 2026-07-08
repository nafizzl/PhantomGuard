import os
import sys
import subprocess
import argparse
import urllib.request
import json
import signal
import time

from phantomguard import config

def cmd_init():
    print("[PhantomGuard] Initializing Workspace...")
    
    # 1. Write local .env template if not exists
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# PhantomGuard Credentials and Config\n")
            f.write("FIREWORKS_API_KEY=\"\"\n")
            f.write("AMD_NOTEBOOK_URL=\"\"\n")
            f.write("# Optional custom SFT adapter path override\n")
            f.write("# PHANTOMGUARD_MODEL=\"\"\n")
        print("  [+] Created `.env` configuration template.")
    else:
        print("  [.] `.env` already exists in this folder.")

    # 2. Write client hook integration helper
    hook_helper_path = "phantomguard_hook.bat"
    if not os.path.exists(hook_helper_path):
        with open(hook_helper_path, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("phantomguard hook %*\n")
        print("  [+] Created `phantomguard_hook.bat` helper command.")
        
    print("\nInitialization Complete! Setup Instructions:")
    print("1. Open `.env` and fill in your `FIREWORKS_API_KEY`.")
    print("2. Start the daemon in the background using: `phantomguard start`")
    print("3. Execute any agent CLI command securely: `phantomguard run \"claude\"`")
    print("   Or register `phantomguard_hook.bat` as a PreToolUse hook in your agent config.")

def cmd_start():
    print("[PhantomGuard] Starting Background Daemon & Proxy...")
    
    # Check if daemon is already running via PID file
    if os.path.exists(config.PID_FILE):
        try:
            with open(config.PID_FILE, "r") as f:
                pid = int(f.read().strip())
            # Check if process is still active on Windows
            if sys.platform == "win32":
                # Using tasklist to check if process exists
                out = subprocess.check_output(f'tasklist /FI "PID eq {pid}"', shell=True).decode()
                if str(pid) in out:
                    print(f"  [!] Daemon is already running (PID {pid}).")
                    return
            else:
                os.kill(pid, 0)
                print(f"  [!] Daemon is already running (PID {pid}).")
                return
        except Exception:
            # PID file is stale, remove it
            try: os.remove(config.PID_FILE)
            except: pass

    # Launch daemon process in the background (detached console on Windows)
    try:
        creation_flags = 0
        if sys.platform == "win32":
            # Creation flag to start process in a new hidden/separate console
            creation_flags = subprocess.CREATE_NEW_CONSOLE
            
        # 1. Start daemon server (orchestrator on port 8001)
        daemon_proc = subprocess.Popen(
            [sys.executable, "-m", "phantomguard.daemon"],
            creationflags=creation_flags,
            close_fds=True
        )
        
        # 2. Start proxy server (port 8000)
        proxy_proc = subprocess.Popen(
            [sys.executable, "-m", "phantomguard.proxy"],
            creationflags=creation_flags,
            close_fds=True
        )
        
        time.sleep(1.5)  # Wait for startup binding
        print(f"  [+] Launched daemon (PID {daemon_proc.pid}) and proxy (PID {proxy_proc.pid}).")
        print(f"  [+] Local verifier daemon port: {config.DAEMON_PORT}")
        print(f"  [+] Network proxy interceptor port: {config.PROXY_PORT}")
        print("  [Success] Daemon and Proxy running in background.")
    except Exception as e:
        print(f"  [Error] Failed to launch background services: {e}")

def cmd_stop():
    print("[PhantomGuard] Stopping Background Daemon...")
    if not os.path.exists(config.PID_FILE):
        print("  [!] No daemon PID lockfile found. Daemon is likely stopped.")
        return

    try:
        with open(config.PID_FILE, "r") as f:
            pid = int(f.read().strip())
        
        # Terminate process
        if sys.platform == "win32":
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
            
        print(f"  [+] Terminated daemon process (PID {pid}).")
    except Exception as e:
        print(f"  [Error] Failed to terminate daemon process: {e}")
    finally:
        if os.path.exists(config.PID_FILE):
            try: os.remove(config.PID_FILE)
            except: pass
        print("  [Success] Daemon services stopped.")

def cmd_run(command_str):
    """
    Spawns a child process with local HTTP proxy variables configured.
    """
    print(f"[PhantomGuard] Launching command in secured environment: {command_str}")
    
    # Check if daemon is active
    try:
        urllib.request.urlopen(f"http://{config.DAEMON_HOST}:{config.DAEMON_PORT}/", timeout=1.0)
    except Exception:
        print("  [!] Warning: Local daemon does not appear to be running.")
        print("      Please run `phantomguard start` first, or actions will default to BLOCKED.")
        
    env = os.environ.copy()
    # Inject standard environment variables pointing to the local proxy port
    env["HTTP_PROXY"] = f"http://127.0.0.1:{config.PROXY_PORT}"
    env["HTTPS_PROXY"] = f"http://127.0.0.1:{config.PROXY_PORT}"
    
    try:
        # Run command inheriting system stdin/stdout/stderr
        subprocess.run(command_str, shell=True, env=env)
    except KeyboardInterrupt:
        pass
    print("[PhantomGuard] Secured environment exited.")

def cmd_hook(action_type, target, context):
    """
    Surgical hook client that queries daemon and exits with status codes.
    """
    payload = {
        "action_type": action_type,
        "target": target,
        "context": context or "Surgical hook evaluation"
    }
    
    url = f"http://{config.DAEMON_HOST}:{config.DAEMON_PORT}/verify"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            res_body = json.loads(res.read().decode("utf-8"))
            allowed = res_body.get("allowed", True)
            reason = res_body.get("reason", "No evaluation reason provided.")
            
            if allowed:
                print(f"[PhantomGuard] ALLOWED: {target}")
                sys.exit(0)
            else:
                print(f"[PhantomGuard] BLOCKED: {target}")
                print(f"  Reason: {reason}", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        # Fail-secure default if daemon is down
        print(f"[PhantomGuard Error] Hook check failed: {e}. Action BLOCKED by default.", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="PhantomGuard Agent Trust Firewall CLI Utility")
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")
    
    # init
    subparsers.add_parser("init", help="Initialize a secured project workspace folder")
    
    # start
    subparsers.add_parser("start", help="Start background daemon and proxy services")
    
    # stop
    subparsers.add_parser("stop", help="Stop background daemon and proxy services")
    
    # run
    run_parser = subparsers.add_parser("run", help="Run an agent command inside the secured proxy environment")
    run_parser.add_argument("agent_command", type=str, help="CLI command to execute (e.g. 'claude' or 'npm run dev')")
    
    # hook
    hook_parser = subparsers.add_parser("hook", help="Surgical CLI verification hook for tool configs")
    hook_parser.add_argument("--type", required=True, choices=["url_fetch", "package_install", "tool_execution"], help="Action type to verify")
    hook_parser.add_argument("--target", required=True, help="Target value (URL, package name, or command string)")
    hook_parser.add_argument("--context", default="", help="Context description")
    
    args = parser.parse_args()
    
    if args.command == "init":
        cmd_init()
    elif args.command == "start":
        cmd_start()
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "run":
        cmd_run(args.agent_command)
    elif args.command == "hook":
        cmd_hook(args.type, args.target, args.context)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
