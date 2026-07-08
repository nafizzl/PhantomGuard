import re
from backend.verifier.llm_client import query_llm

# Whitelist of simple safe base commands
SAFE_COMMAND_WHITELIST = {
    "ls", "pwd", "git", "echo", "cd", "pytest", "python", "pip list", "npm run", 
    "whoami", "hostname", "date", "clear", "make build", "make test"
}

def verify_tool(command: str, context: str = "") -> dict:
    """
    Verifies shell commands (tool execution) for malicious structures or command injection.
    Uses safe whitelist checks + SFT LLM classification.
    """
    cmd_clean = command.strip()
    
    # 1. Check Whitelist for trivial safe commands (e.g. "git status", "ls -la")
    base_cmd = cmd_clean.split()[0] if cmd_clean else ""
    if base_cmd in SAFE_COMMAND_WHITELIST and len(cmd_clean) < 50:
        # Check for dangerous punctuation even in whitelist base commands (like semicolons or pipes)
        if not re.search(r'[|&;<>]', cmd_clean):
            return {
                "is_hallucination": False,
                "confidence": 0.99,
                "category": "none",
                "reason": f"Command matches safe developer whitelist pattern: {base_cmd}"
            }

    # 2. Query SFT LLM for security classification
    llm_res = query_llm(action_type="tool_execution", target=command, context=context)
    
    return {
        "is_hallucination": llm_res["is_hallucination"],
        "confidence": llm_res["confidence"],
        "category": "security" if llm_res["is_hallucination"] else "none",
        "reason": llm_res["reason"]
    }
