import urllib.request
import urllib.error
import json

url = "https://api.fireworks.ai/inference/v1/chat/completions"
payload = {
    "model": "accounts/fireworks/models/gemma2-9b-it",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.1,
    "max_tokens": 10
}
req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": "Bearer fw_ABpabjvxvZ128BQoVh1jd8",
        "Content-Type": "application/json"
    },
    method="POST"
)
try:
    with urllib.request.urlopen(req) as res:
        print("Success:", res.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP Error Code:", e.code)
    print("HTTP Error Body:", e.read().decode())
except Exception as e:
    print("General Error:", e)
