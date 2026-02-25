import json
import os

for filename in ["translations/en.json", "translations/es.json"]:
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Create options block duplicating config block
    if "config" in data:
        data["options"] = json.loads(json.dumps(data["config"]))
    
    # In options block, rename 'user' to 'init'
    if "options" in data and "step" in data["options"]:
        if "user" in data["options"]["step"]:
            data["options"]["step"]["init"] = data["options"]["step"].pop("user")
            
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Modified {filename}")
