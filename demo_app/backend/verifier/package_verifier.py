import urllib.request
import urllib.error
import re
from backend.verifier.llm_client import query_llm

def check_registry_exists(package_name: str) -> tuple[bool, str]:
    """
    Checks PyPI and npm registries to see if a package name exists.
    Returns (exists, registry_name)
    """
    # Clean package name of version specifiers (e.g. requests==2.31.0 -> requests, lodash@latest -> lodash)
    clean_name = re.split(r'==|>=|<=|>|<|@', package_name)[0].strip()
    
    # Try PyPI
    pypi_url = f"https://pypi.org/pypi/{clean_name}/json"
    try:
        req = urllib.request.Request(pypi_url, headers={'User-Agent': 'PhantomGuard/1.0'})
        with urllib.request.urlopen(req, timeout=3.0) as res:
            if res.status == 200:
                return True, "pypi"
    except urllib.error.HTTPError as e:
        if e.code != 404:
            # If rate limited or other error, assume it might exist to avoid false alerts
            return True, "pypi (check-failover)"
    except Exception:
        pass

    # Try npm
    npm_url = f"https://registry.npmjs.org/{clean_name}"
    try:
        req = urllib.request.Request(npm_url, headers={'User-Agent': 'PhantomGuard/1.0'})
        with urllib.request.urlopen(req, timeout=3.0) as res:
            if res.status == 200:
                return True, "npm"
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return True, "npm (check-failover)"
    except Exception:
        pass

    return False, "none"

def verify_package(package_name: str, context: str = "") -> dict:
    """
    Verifies if a package installation command represents a hallucination / slopsquatting risk.
    Uses registry checks + SFT LLM classification.
    """
    exists, registry = check_registry_exists(package_name)
    
    if exists:
        return {
            "is_hallucination": False,
            "confidence": 0.99,
            "category": "none",
            "reason": f"Package '{package_name}' verified in official {registry} registry index."
        }
        
    # If the package does not exist, query the LLM to classify if it's a hallucination (mimicked name)
    llm_res = query_llm(action_type="package_install", target=package_name, context=context)
    
    # If LLM flags it as hallucination, we output it as security slopsquatting risk
    if llm_res["is_hallucination"]:
        return {
            "is_hallucination": True,
            "confidence": llm_res["confidence"],
            "category": "security",
            "reason": f"[Registry: Not Found] {llm_res['reason']}"
        }
        
    # If the package does not exist in registries but the LLM thinks it's not a hallucination, 
    # we still issue a warning (since installing nonexistent packages fails or is risky)
    return {
        "is_hallucination": True,
        "confidence": 0.85,
        "category": "security",
        "reason": f"Package '{package_name}' does not exist in PyPI or npm registry. High risk of future slopsquatting takeover."
    }
