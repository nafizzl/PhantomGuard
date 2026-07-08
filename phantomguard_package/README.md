# PhantomGuard: Agent Trust Firewall Client SDK

PhantomGuard is a lightweight agent firewall client package. It intercepts autonomous LLM agent actions (network requests, package installations, and shell command executions) at the socket/subprocess boundary to prevent supply-chain vulnerabilities such as **Phantom Squatting** and **Slopsquatting**.

---

## 🚀 Installation

Install the package directly from PyPI (or via local development install):
```bash
pip install phantomguard-firewall
```

---

## 🛠️ CLI Operations

### 1. Initialize a Workspace
To bootstrap a project folder with default security settings and environment configurations:
```bash
phantomguard init
```
This creates a local `.env` file template where you can configure your `FIREWORKS_API_KEY`.

### 2. Start the Background Services
Starts the local orchestrator daemon (port `8001`) and the network interceptor proxy (port `8000`) in detached background processes:
```bash
phantomguard start
```

To stop the services:
```bash
phantomguard stop
```

### 3. Run Secured Agent CLI (The Proxy Approach)
To run any external CLI agent (like Claude Code or Codex) securely, wrap it with `phantomguard run`:
```bash
phantomguard run "claude"
```
*Behind the scenes: This automatically sets `HTTP_PROXY` and `HTTPS_PROXY` environment variables in the agent process. Any outbound network requests to hallucinated domains are dynamically intercepted and blocked by the firewall proxy.*

### 4. Surgical CLI Integration (The Hook Approach)
For CLI tools that support pre-tool hooks (such as Claude Code's PreToolUse configuration), you can register the surgical hook client:
```bash
phantomguard hook --type [url_fetch|package_install|tool_execution] --target [value]
```
If the action is safe, the command prints `ALLOWED` and exits with status code `0`. If blocked (or timed out), it prints the reason to stderr and exits with status code `1`, halting the agent's execution loop.

---

## 🐍 Python API Usage

You can import the verifier modules directly into your own custom Python agent loops:

```python
from phantomguard.verifier.url_verifier import verify_url
from phantomguard.verifier.package_verifier import verify_package
from phantomguard.verifier.tool_verifier import verify_tool

# Evaluate a URL request before calling requests.get
res = verify_url("https://docs.matplotlib-extra-charts.org")
if res["is_hallucination"]:
    print(f"Danger! Blocked: {res['reason']}")
else:
    print("Safe to proceed.")
```
