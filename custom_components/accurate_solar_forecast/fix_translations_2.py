import json
import traceback

def fix():
    files = ['translations/en.json', 'translations/es.json']
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config_steps = data.get("config", {}).get("step", {})
        
        def add_steps_to_subentry(subentry_key, step_keys):
            if "step" not in data["config_subentries"][subentry_key]:
                data["config_subentries"][subentry_key]["step"] = {}
            for k in step_keys:
                if k in config_steps:
                    data["config_subentries"][subentry_key]["step"][k] = config_steps[k]

        add_steps_to_subentry("pv_model", ["pv_model_create", "flow_success", "user", "pv_model_edit_select", "pv_model_edit_form", "pv_model_delete_select"])
        add_steps_to_subentry("roof", ["roof_create", "flow_success", "user", "roof_edit_select", "roof_edit_form", "roof_delete_select"])
        add_steps_to_subentry("sensor_group", ["sensor_group_create", "flow_success", "user", "sensor_group_edit_select", "sensor_group_edit_form", "sensor_group_delete_select"])
        add_steps_to_subentry("string", ["string_create_select_relations", "string_create_tilt_azimuth", "string_create_device_linking", "string_form", "flow_success", "user", "string_create_details", "string_add_another", "reconfigure_string"])
        add_steps_to_subentry("management", ["menu_management", "menu_pv_models", "pv_model_create", "pv_model_edit_select", "pv_model_edit_form", "pv_model_delete_select", "menu_roofs", "roof_create", "roof_edit_select", "roof_edit_form", "roof_delete_select", "menu_sensor_groups", "sensor_group_create", "sensor_group_edit_select", "sensor_group_edit_form", "sensor_group_delete_select", "flow_success", "user"])

        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Fixed {file} - step keys in pv_model: {list(data['config_subentries']['pv_model'].get('step', {}).keys())}")

try:
    fix()
except Exception as e:
    print("ERROR:")
    traceback.print_exc()
