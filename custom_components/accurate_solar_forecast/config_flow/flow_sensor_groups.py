import voluptuous as vol
from homeassistant.helpers import selector
from ..variables.const import CONF_SENSOR_GROUP_NAME, CONF_REF_SENSOR, CONF_REF_TILT, CONF_REF_ORIENTATION, CONF_TEMP_SENSOR, CONF_WIND_SENSOR, CONF_TEMP_PANEL_SENSOR, CONF_WEATHER_ENTITY, CONF_ILLUMINANCE_SENSOR

class SensorGroupsFlowMixin:
    # =================================================================================
    # BRANCH 2: SENSOR GROUPS (Integraciones - Create & Edit Only)
    # =================================================================================
    async def async_step_menu_sensor_groups(self, user_input=None):
        # Explicitly reload DB to ensure freshness just in case
        if self._db:
             await self._db.async_load()

        # Optimization: If no groups, go straight to creation
        # We check the length explicitly to be robust
        groups = self._db.list_sensor_groups()
        if not groups or len(groups) == 0:
             return await self.async_step_sensor_group_create()

        options = ["sensor_group_create", "sensor_group_edit_select"]
        return self.async_show_menu(
            step_id="menu_sensor_groups",
            menu_options=options
        )

    # 2.1 CREATE SENSOR GROUP
    async def async_step_sensor_group_create(self, user_input=None):
         errors = {}
         if user_input is not None:
            name = user_input[CONF_SENSOR_GROUP_NAME]
            # Save to DB
            await self._db.add_sensor_group(
                name,
                user_input[CONF_REF_SENSOR],
                user_input[CONF_TEMP_SENSOR],
                user_input.get(CONF_TEMP_PANEL_SENSOR),
                user_input.get(CONF_WIND_SENSOR),
                user_input[CONF_REF_TILT],
                user_input[CONF_REF_ORIENTATION],
                user_input.get(CONF_WEATHER_ENTITY),
                user_input.get(CONF_ILLUMINANCE_SENSOR)
            )
            # Regresar al panel principal
            return self.async_abort(reason="list_updated")
            
         return self._show_sensor_group_form("sensor_group_create", errors)

    # 2.2 EDIT SENSOR GROUP (Update DB only)
    async def async_step_sensor_group_edit_select(self, user_input=None):
        if user_input is not None:
             self.selected_item_id = user_input["selected_group"]
             return await self.async_step_sensor_group_edit_form()

        groups = self._db.list_sensor_groups()
        if not groups:
             return self.async_abort(reason="no_sensor_groups")

        schema = vol.Schema({
            vol.Required("selected_group"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(groups.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="sensor_group_edit_select", data_schema=schema)

    async def async_step_sensor_group_edit_form(self, user_input=None):
        if user_input is not None:
             name = user_input[CONF_SENSOR_GROUP_NAME]
             await self._db.add_sensor_group(
                name,
                user_input[CONF_REF_SENSOR],
                user_input[CONF_TEMP_SENSOR],
                user_input.get(CONF_TEMP_PANEL_SENSOR),
                user_input.get(CONF_WIND_SENSOR),
                user_input[CONF_REF_TILT],
                user_input[CONF_REF_ORIENTATION],
                user_input.get(CONF_WEATHER_ENTITY),
                user_input.get(CONF_ILLUMINANCE_SENSOR)
            )
             return self.async_abort(reason="list_updated")

        group_data = self._db.get_sensor_group(self.selected_item_id)
        return self._show_sensor_group_form("sensor_group_edit_form", {}, default_data=group_data)

    # Helper: Sensor Group Form
    def _show_sensor_group_form(self, step_id, errors, default_data=None):
        if default_data is None: default_data = {}
        schema = self._get_sensor_group_schema(default_data)
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)
