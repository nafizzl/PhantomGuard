import json

val_path = "c:\\Users\\19295\\PhantomGuard\\demo_app\\data\\val.jsonl"
url_count = 0
with open(val_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        user_msg = data["messages"][1]["content"]
        if "action: url_fetch" in user_msg:
            url_count += 1

print("Total url_fetch examples in val.jsonl:", url_count)
