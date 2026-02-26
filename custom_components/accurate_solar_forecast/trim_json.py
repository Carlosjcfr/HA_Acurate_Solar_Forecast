import json, os

paths = ['translations/en.json', 'translations/es.json']
for p in paths:
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Before {p}: options in data: {'options' in data}")
    
    if 'options' in data:
        del data['options']
        
    if 'config' in data and 'step' in data['config']:
        for k in ['user', 'flow_success', 'pv_model_success', 'string_add_another']:
            if k in data['config']['step']:
                del data['config']['step'][k]
                
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"Done {p}")
