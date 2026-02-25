import json
try:
    with open('translations/es.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    print("KEYS:", list(data.keys()))
except Exception as e:
    print("FAILED:", e)
