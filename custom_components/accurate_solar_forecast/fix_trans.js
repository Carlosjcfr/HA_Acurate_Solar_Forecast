const fs = require('fs');

const files = ['translations/en.json', 'translations/es.json'];

files.forEach(file => {
    let data = JSON.parse(fs.readFileSync(file, 'utf8'));
    let config_steps = data.config && data.config.step ? data.config.step : {};

    function add_steps(subentry_key, step_keys) {
        if (!data.config_subentries[subentry_key]) return;
        if (!data.config_subentries[subentry_key].step) {
            data.config_subentries[subentry_key].step = {};
        }
        step_keys.forEach(k => {
            if (config_steps[k]) {
                data.config_subentries[subentry_key].step[k] = config_steps[k];
            }
        });
    }

    add_steps("pv_model", ["pv_model_create", "flow_success", "user", "pv_model_edit_select", "pv_model_edit_form", "pv_model_delete_select"]);
    add_steps("roof", ["roof_create", "flow_success", "user", "roof_edit_select", "roof_edit_form", "roof_delete_select"]);
    add_steps("sensor_group", ["sensor_group_create", "flow_success", "user", "sensor_group_edit_select", "sensor_group_edit_form", "sensor_group_delete_select"]);
    add_steps("string", ["string_create_select_relations", "string_create_tilt_azimuth", "string_create_device_linking", "string_form", "flow_success", "user", "string_create_details", "string_add_another", "reconfigure_string"]);
    add_steps("management", ["menu_management", "menu_pv_models", "pv_model_create", "pv_model_edit_select", "pv_model_edit_form", "pv_model_delete_select", "menu_roofs", "roof_create", "roof_edit_select", "roof_edit_form", "roof_delete_select", "menu_sensor_groups", "sensor_group_create", "sensor_group_edit_select", "sensor_group_edit_form", "sensor_group_delete_select", "flow_success", "user"]);

    fs.writeFileSync(file, JSON.stringify(data, null, 4), 'utf8');
});
console.log("Translations fixed with node!");
