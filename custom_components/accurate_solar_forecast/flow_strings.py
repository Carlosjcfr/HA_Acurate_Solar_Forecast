import voluptuous as vol
from homeassistant.helpers import selector
from .const import CONF_TILT, CONF_AZIMUTH, CONF_ROOF_NAME, CONF_STRING_NAME

class StringsFlowMixin:
    # =================================================================================
    # BRANCH 3: STRINGS (Integraciones - Create Only)
    # =================================================================================

    # 3.1 CREATE STRING - Step A: Select Brand & Group
    async def async_step_string_create_select_relations(self, user_input=None):
         if user_input is not None:
            self.temp_data.update(user_input)
            
            # Check for "Nuevo tejado"
            if self.temp_data.get(CONF_ROOF_NAME) == "Nuevo tejado":
                return await self.async_step_roof_create()
                
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
            
            return await self.async_step_string_create_details()
            
        schema = self._get_roof_create_schema()
        return self.async_show_form(step_id="roof_create", data_schema=schema)

    # 3.1 CREATE STRING - Step B: Details
    async def async_step_string_create_details(self, user_input=None):
        if user_input is not None:
             final_data = {**self.temp_data, **user_input}
             if getattr(self, "reconfigure_entry", None):
                 self.hass.config_entries.async_update_entry(self.reconfigure_entry, data=final_data)
                 return self.async_update_reload_and_abort(self.reconfigure_entry)
             else:
                 title = final_data.get(CONF_ROOF_NAME) or final_data.get(CONF_STRING_NAME)
                 return self.async_create_entry(
                    title=title, 
                    data=final_data
                )
            
        schema = self._get_string_details_schema()
        return self.async_show_form(step_id="string_create_details", data_schema=schema)
