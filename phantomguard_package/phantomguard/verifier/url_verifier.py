import socket
import urllib.request
import urllib.parse
from phantomguard.verifier.llm_client import query_llm

def verify_url(url: str, context: str = "") -> dict:
    """
    Verifies if a URL action represents a security hallucination (Phantom Squatting)
    or a usability issue (broken 404).
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme:
            parsed = urllib.parse.urlparse("http://" + url)
        domain = parsed.netloc or parsed.path.split("/")[0]
    except Exception as e:
        return {
            "is_hallucination": True,
            "confidence": 0.99,
            "category": "security",
            "reason": f"Malformed URL parsing failed: {e}"
        }

    # Whitelist check to avoid self-intercept deadlocks
    whitelisted_domains = [
        "api.fireworks.ai", 
        "api.anthropic.com", 
        "api.openai.com", 
        "generativelanguage.googleapis.com", 
        "localhost", 
        "127.0.0.1"
    ]
    if any(domain == w or domain.endswith("." + w) for w in whitelisted_domains):
        return {
            "is_hallucination": False,
            "confidence": 1.0,
            "category": "none",
            "reason": "Whitelisted infrastructure domain."
        }

    # 1. Active DNS Verification
    dns_resolved = True
    try:
        socket.gethostbyname(domain)
    except socket.gaierror:
        dns_resolved = False

    # 2. Real-time Usability Check (Broken Link Check via HEAD request)
    http_status_ok = True
    http_error_msg = ""
    if dns_resolved:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PhantomGuard/1.0"},
                method="HEAD"
            )
            with urllib.request.urlopen(req, timeout=2.5) as response:
                if response.status >= 400:
                    http_status_ok = False
                    http_error_msg = f"HTTP status code {response.status}"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                http_status_ok = False
                http_error_msg = "HTTP 404 Not Found"
        except Exception:
            pass

    # 3. LLM Threat Classification
    llm_res = query_llm(action_type="url_fetch", target=url, context=context)
    is_hallucination = llm_res["is_hallucination"]
    confidence = llm_res["confidence"]
    reason = llm_res["reason"]

    # Combine signals
    if not dns_resolved:
        if is_hallucination:
            confidence = max(confidence, 0.98)
            reason = f"[DNS: Unregistered Domain] {reason}"
        else:
            is_hallucination = True
            confidence = 0.90
            reason = f"Domain '{domain}' does not resolve via DNS. Highly susceptible to Phantom Squatting domain hijack."

    if dns_resolved and not http_status_ok:
        return {
            "is_hallucination": True,
            "confidence": 0.95,
            "category": "usability",
            "reason": f"Usability Link Broken: The domain is registered but fetching returns {http_error_msg}."
        }

    return {
        "is_hallucination": is_hallucination,
        "confidence": confidence,
        "category": "security" if is_hallucination else "none",
        "reason": reason
    }
