import json

paths = ['translations/en.json', 'translations/es.json']
for p in paths:
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"{p} config steps: {list(data.get('config', {}).get('step', {}).keys())}")
