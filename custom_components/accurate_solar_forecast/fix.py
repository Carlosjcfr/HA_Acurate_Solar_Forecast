import json
import traceback

def fix_file(f):
    try:
        with open(f, 'r', encoding='utf-8') as file:
            d = json.load(file)
        modified = False
        if 'config_subentries' in d:
            for k, v in d['config_subentries'].items():
                name = v.get('name', '') or v.get('title', '') or k
                v['initiate_flow'] = {'user': name}
                v['flow_title'] = name
                v['title'] = name
                modified = True
                
        if modified:
            with open(f, 'w', encoding='utf-8') as file:
                json.dump(d, file, indent=4, ensure_ascii=False)
            print("Fixed", f)
        else:
            print("No config_subentries in", f)
    except Exception as e:
        print("Error in", f)
        traceback.print_exc()

files = ['strings.json', 'translations/en.json', 'translations/es.json']
for f in files:
    fix_file(f)
