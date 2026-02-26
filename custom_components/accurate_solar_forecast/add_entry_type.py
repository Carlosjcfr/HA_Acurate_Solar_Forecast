import json
import traceback

files = ['strings.json', 'translations/en.json', 'translations/es.json']
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as file:
            d = json.load(file)
            
        if 'config_subentries' in d:
            for k, v in d['config_subentries'].items():
                name = v.get('name', '') or v.get('title', '')
                v['entry_type'] = name
        
        with open(f, 'w', encoding='utf-8') as file:
            json.dump(d, file, indent=4, ensure_ascii=False)
        print("Updated", f)
    except Exception as e:
        traceback.print_exc()
