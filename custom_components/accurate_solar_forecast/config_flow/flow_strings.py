import voluptuous as vol
from homeassistant.helpers import selector
from ..variables.const import (
    CONF_STRING_NAME, 
    CONF_REAL_PRODUCTION_SENSOR, 
    CONF_TILT, 
    CONF_AZIMUTH, 
    CONF_ROOF_NAME, 
    CONF_BRAND,
    CONF_PANEL_MODEL,
    CONF_NUM_PANELS,
    CONF_NUM_STRINGS
)
from ..core import slugify

class StringsFlowMixin:
    # =================================================================================
    # BRANCH 3: STRINGS (Integraciones - Create Only)
    # =================================================================================

    # 3.1 CREATE STRING - Step A: Select Brand & Group
    async def async_step_string_create_select_relations(self, user_input=None):
         if user_input is not None:
            self.temp_data.update(user_input)
            
            # If the optional field is cleared by the user, remove it from temp_data
            if CONF_REAL_PRODUCTION_SENSOR not in user_input:
                self.temp_data.pop(CONF_REAL_PRODUCTION_SENSOR, None)
                
            return await self.async_step_string_create_details()

         schema = self._get_string_select_relations_schema()
         if schema is None:
             return self.async_abort(reason="no_sensor_groups_available")
             
         return self.async_show_form(step_id="string_create_select_relations", data_schema=schema)

    # 3.1.1 CREATE ROOF (Intermediate Step)
    async def async_step_roof_create(self, user_input=None):
        if user_input is not None:
            name = user_input["name"]
            tilt = user_input[CONF_TILT]
            azimuth = user_input[CONF_AZIMUTH]
            
            # Save Roof
            await self._db.add_roof(name, tilt, azimuth)
            
            # Update temp_data specific roof name (replace "Nuevo tejado")
            self.temp_data[CONF_ROOF_NAME] = name
            
            return await self.async_step_string_create_select_relations()
            
        schema = self._get_roof_create_schema()
        return self.async_show_form(step_id="roof_create", data_schema=schema)

    # 3.1 CREATE STRING - Step B: Details
    async def async_step_string_create_details(self, user_input=None):
        if user_input is not None:
             final_data = {**self.temp_data, **user_input}
             
             # Always save string to DB under the current Roof
             roof_name = final_data.get(CONF_ROOF_NAME)
             roof_id = slugify(roof_name) if roof_name else "default"
             string_name = final_data[CONF_STRING_NAME]
             string_id = slugify(string_name)
             
             string_data = {
                 CONF_STRING_NAME: string_name,
                 "selected_sensor_group": final_data.get("selected_sensor_group"),
                 CONF_BRAND: final_data.get(CONF_BRAND),
                 CONF_REAL_PRODUCTION_SENSOR: final_data.get(CONF_REAL_PRODUCTION_SENSOR),
                 CONF_PANEL_MODEL: final_data.get(CONF_PANEL_MODEL),
                 CONF_NUM_PANELS: final_data.get(CONF_NUM_PANELS),
                 CONF_NUM_STRINGS: final_data.get(CONF_NUM_STRINGS),
                 CONF_TILT: final_data.get(CONF_TILT),
                 CONF_AZIMUTH: final_data.get(CONF_AZIMUTH)
             }
             
             await self._db.add_string_to_roof(roof_id, string_id, string_data)
             
             # Clear string specifics for the next potential string iteration
             self.temp_data.pop(CONF_STRING_NAME, None)
             self.temp_data.pop(CONF_REAL_PRODUCTION_SENSOR, None)
             
             if getattr(self, "reconfigure_entry", None):
                 return self.async_update_reload_and_abort(self.reconfigure_entry)
                 
             return self.async_abort(reason="list_updated")
            
        schema = self._get_string_details_schema()
        return self.async_show_form(step_id="string_create_details", data_schema=schema)
