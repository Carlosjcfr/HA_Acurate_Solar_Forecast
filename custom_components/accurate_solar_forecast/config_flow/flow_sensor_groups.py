import voluptuous as vol
from homeassistant.helpers import selector
from ..variables.const import CONF_SENSOR_GROUP_NAME, CONF_REF_SENSOR, CONF_REF_TILT, CONF_REF_ORIENTATION, CONF_TEMP_SENSOR, CONF_WIND_SENSOR, CONF_TEMP_PANEL_SENSOR, CONF_WEATHER_ENTITY, CONF_ILLUMINANCE_SENSOR

class SensorGroupsFlowMixin:
    # =================================================================================
    # BRANCH 2: SENSOR GROUPS (Integraciones - Create & Edit Only)
    # =================================================================================
    async def async_step_menu_sensor_groups(self, userInput=None):
        # Explicitly reload DB to ensure freshness just in case
        if self._db:
             await self._db.async_load()

        # Optimization: If no groups, go straight to creation
        # We check the length explicitly to be robust
        groups = self._db.listSensorGroups()
        if not groups or len(groups) == 0:
             return await self.async_step_sensor_group_create()

        options = ["sensor_group_create", "sensor_group_edit_select"]
        return self.async_show_menu(
            step_id="menu_sensor_groups",
            menu_options=options
        )

    # 2.1 CREATE SENSOR GROUP
    async def async_step_sensor_group_create(self, userInput=None):
         errors = {}
         if userInput is not None:
            name = userInput[CONF_SENSOR_GROUP_NAME]
            
            if not errors:
                # Save to DB
                groupId = await self._db.addSensorGroup(
                    name,
                    userInput[CONF_REF_SENSOR],
                    userInput[CONF_TEMP_SENSOR],
                    userInput.get(CONF_TEMP_PANEL_SENSOR),
                    userInput.get(CONF_WIND_SENSOR),
                    userInput[CONF_REF_TILT],
                    userInput[CONF_REF_ORIENTATION],
                    userInput.get(CONF_WEATHER_ENTITY),
                    userInput.get(CONF_ILLUMINANCE_SENSOR)
                )
                
                # BRANCH A: If in guided flow (Roof -> SG), we continue to string creation
                if getattr(self, '_guidedFlow', False):
                    roofName = self.tempData.get(CONF_ROOF_NAME)
                    if roofName:
                        from ..core import slugify as _slugify
                        roofId = _slugify(roofName)
                        roof = self._db.getRoof(roofId)
                        if roof:
                             await self._db.addRoof(
                                roof.name, roof.tilt, roof.azimuth,
                                sensorGroupId=groupId
                             )
                    return await self.async_step_string_create_select_relations()
                
                # BRANCH B: If it's a subentry flow (Pill), we MUST return async_create_entry
                # We check for our custom flag or if the handler name contains Subentry
                if getattr(self, "_isSubentry", False) or "Subentry" in self.__class__.__name__:
                     return self.async_create_entry(
                         title=name,
                         data={CONF_SENSOR_GROUP_NAME: name}
                     )
                
                # Fallback
                return self.async_abort(reason="list_updated")
            
         return self._showSensorGroupForm("sensor_group_create", errors)

    # 2.2 EDIT SENSOR GROUP (Update DB only)
    async def async_step_sensor_group_edit_select(self, userInput=None):
        if userInput is not None:
             self.selectedItemId = userInput["selected_group"]
             return await self.async_step_sensor_group_edit_form()

        groups = self._db.listSensorGroups()
        if not groups:
             return self.async_abort(reason="no_sensor_groups")

        schema = vol.Schema({
            vol.Required("selected_group"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(groups.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="sensor_group_edit_select", data_schema=schema)

    async def async_step_sensor_group_edit_form(self, userInput=None):
        errors = {}
        if userInput is not None:
             if not errors:
                 name = userInput[CONF_SENSOR_GROUP_NAME]
                 await self._db.addSensorGroup(
                    name,
                    userInput[CONF_REF_SENSOR],
                    userInput[CONF_TEMP_SENSOR],
                    userInput.get(CONF_TEMP_PANEL_SENSOR),
                    userInput.get(CONF_WIND_SENSOR),
                    userInput[CONF_REF_TILT],
                    userInput[CONF_REF_ORIENTATION],
                    userInput.get(CONF_WEATHER_ENTITY),
                    userInput.get(CONF_ILLUMINANCE_SENSOR)
                 )
                 return self.async_abort(reason="list_updated")

        groupData = self._db.getSensorGroup(self.selectedItemId)
        return self._showSensorGroupForm("sensor_group_edit_form", {}, defaultData=groupData)

    # Helper: Sensor Group Form
    def _showSensorGroupForm(self, stepId, errors, defaultData=None):
        if defaultData is None: defaultData = {}
        schema = self._getSensorGroupSchema(defaultData)
        return self.async_show_form(step_id=stepId, data_schema=schema, errors=errors)
