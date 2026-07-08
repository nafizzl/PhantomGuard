import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sys

# Define a static corpus of known safe developer brands and popular package names
SAFE_CORPUS = {
    "url": [
        "usps.com", "github.com", "python.org", "npmjs.com", "stripe.com", 
        "amazon.com", "openai.com", "microsoft.com", "cloudflare.com", 
        "google.com", "apple.com", "facebook.com", "netlify.com", "vercel.com", 
        "heroku.com", "digitalocean.com", "docker.com", "gitlab.com", "slack.com", 
        "zoom.us", "salesforce.com", "adobe.com", "spotify.com", "netflix.com", 
        "airbnb.com", "uber.com", "twitter.com", "reddit.com", "linkedin.com", 
        "discord.com", "kubernetes.io", "terraform.io", "ansible.com", "redhat.com", 
        "ubuntu.com", "alpinelinux.org", "sentry.io", "atlassian.com", "datadoghq.com", 
        "elastic.co", "postgresql.org"
    ],
    "package": [
        "requests", "numpy", "pandas", "scipy", "matplotlib", "scikit-learn", 
        "urllib3", "cryptography", "jinja2", "markupsafe", "certifi", "click",
        "express", "lodash", "react", "vue", "angular", "next", "tailwindcss",
        "jscodeshift", "react-codemod", "chalk", "commander", "fs-extra", "axios"
    ]
}

# Attempt to load PyTorch & SentenceTransformers for AMD ROCm GPU acceleration
DEVICE = "cpu"
model = None

try:
    import torch
    from sentence_transformers import SentenceTransformer, util
    
    # Check if ROCm GPU is available (natively mapped to torch.cuda in PyTorch ROCm builds)
    if torch.cuda.is_available():
        DEVICE = "cuda"
        print("[AMD ROCm] ROCm GPU detected! Initializing model on GPU device.")
    else:
        print("[AMD ROCm] ROCm GPU not detected. Defaulting to CPU device.")
        
    # Load lightweight pre-trained embedding model
    model = SentenceTransformer("all-MiniLM-L6-v2", device=DEVICE)
    print("[AMD ROCm] SentenceTransformer model loaded successfully.")
except Exception as e:
    print(f"[Warning] Failed to initialize SentenceTransformers on ROCm: {e}")
    print("[Fallback] Running in string-distance fallback mode (Levenshtein & Jaccard).")

def calculate_string_similarity(s1: str, s2: str) -> float:
    """
    Standard Levenshtein/Jaccard string similarity ratio as a fallback.
    """
    s1_clean = s1.lower().strip()
    s2_clean = s2.lower().strip()
    
    # Simple Jaccard similarity of character n-grams (3-grams)
    def get_ngrams(s, n=3):
        return set(s[i:i+n] for i in range(len(s)-n+1))
        
    g1 = get_ngrams(s1_clean)
    g2 = get_ngrams(s2_clean)
    if not g1 or not g2:
        return 0.0
    intersection = len(g1.intersection(g2))
    union = len(g1.union(g2))
    return intersection / union

def get_similarity(target: str, corpus_type: str) -> tuple[str, float]:
    """
    Calculates semantic embedding similarity (using AMD ROCm GPU if available)
    or falls back to string edit distance metrics.
    """
    corpus = SAFE_CORPUS.get(corpus_type, SAFE_CORPUS["url"])
    target_clean = target.lower().strip()
    
    # 1. Exact match bypass
    if target_clean in corpus:
        return target_clean, 1.0

    # 2. Embedding similarity on ROCm
    if model is not None:
        try:
            # Encode target and safe corpus
            target_emb = model.encode(target_clean, convert_to_tensor=True, device=DEVICE)
            corpus_embs = model.encode(corpus, convert_to_tensor=True, device=DEVICE)
            
            # Compute Cosine Similarity
            cos_scores = util.cos_sim(target_emb, corpus_embs)[0]
            max_idx = int(torch.argmax(cos_scores).item())
            max_score = float(cos_scores[max_idx].item())
            return corpus[max_idx], max_score
        except Exception as e:
            print(f"[Error] Embedding calculation error: {e}. Falling back to string-similarity.")

    # 3. String-distance fallback
    max_score = 0.0
    best_match = corpus[0]
    for item in corpus:
        score = calculate_string_similarity(target_clean, item)
        if score > max_score:
            max_score = score
            best_match = item
    return best_match, max_score

class ROCmServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence standard HTTP access logging in Jupyter logs
        return

    def do_POST(self):
        if self.path == "/similarity":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            
            try:
                payload = json.loads(post_data.decode("utf-8"))
                target = payload.get("target", "")
                corpus_type = payload.get("type", "url") # "url" or "package"
                
                # Extract clean hostname if it's a URL
                if corpus_type == "url":
                    parsed = urllib.parse.urlparse(target)
                    target_domain = parsed.netloc or parsed.path.split("/")[0]
                    # Strip subdomains (e.g. docs.github.com -> github.com)
                    parts = target_domain.split(".")
                    if len(parts) >= 2:
                        target = ".".join(parts[-2:])
                    else:
                        target = target_domain

                # Calculate similarity
                best_match, score = get_similarity(target, corpus_type)
                
                # Evaluation logic: If the target is highly similar but not an exact match,
                # it represents a typosquatted or brand-conflated name!
                is_exact = target.lower().strip() == best_match.lower().strip()
                is_suspicious = (score > 0.82) and not is_exact
                
                response = {
                    "target": target,
                    "best_match": best_match,
                    "similarity_score": round(score, 4),
                    "is_exact_match": is_exact,
                    "is_suspicious_conflation": is_suspicious,
                    "device_used": DEVICE
                }
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode("utf-8"))
                return
                
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode("utf-8"))
                return

        self.send_response(404)
        self.end_headers()

def run(port=5000):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, ROCmServerHandler)
    print(f"\n=======================================================")
    print(f"  PHANTOMGUARD AMD ROCm SIMILARITY SERVER ACTIVE")
    print(f"=======================================================")
    print(f"Listening on port {port} (all interfaces)...")
    print(f"Running on device: {DEVICE.upper()}")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ROCm server.")

if __name__ == "__main__":
    port_arg = 5000
    # Filter out Jupyter connection flags (e.g. '-f')
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        try:
            port_arg = int(sys.argv[1])
        except ValueError:
            pass
    run(port=port_arg)
