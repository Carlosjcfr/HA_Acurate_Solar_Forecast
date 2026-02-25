import json
import os

files = ['translations/en.json', 'translations/es.json']
for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    data["config_subentries"] = {
        "pv_model": {"title": "+ Añadir Módulo FV" if 'es' in file else "+ Add PV Module"},
        "roof": {"title": "+ Añadir Tejado" if 'es' in file else "+ Add Roof"},
        "sensor_group": {"title": "+ Añadir Grupo Sensores" if 'es' in file else "+ Add Sensor Group"},
        "string": {"title": "+ Añadir String Solar" if 'es' in file else "+ Add Solar String"},
        "management": {"title": "⚙️ Gestionar Existentes" if 'es' in file else "⚙️ Manage Existing"}
    }
    
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
