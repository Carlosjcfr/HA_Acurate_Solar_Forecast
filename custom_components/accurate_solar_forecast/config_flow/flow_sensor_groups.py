import voluptuous as vol
import logging
from homeassistant.helpers import selector
from ..variables.const import (
    CONF_SENSOR_GROUP_NAME, CONF_REF_SENSOR, CONF_REF_TILT, 
    CONF_REF_ORIENTATION, CONF_TEMP_SENSOR, CONF_WIND_SENSOR, 
    CONF_TEMP_PANEL_SENSOR, CONF_WEATHER_ENTITY, CONF_ILLUMINANCE_SENSOR,
    CONF_ROOF_NAME
)
from ..core import slugify

_LOGGER = logging.getLogger(__name__)

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
            try:
                name = userInput.get(CONF_SENSOR_GROUP_NAME)
                if not name:
                    errors[CONF_SENSOR_GROUP_NAME] = "required"
                    return self._showSensorGroupForm("sensor_group_create", errors)

                # Save to DB - Using keyword arguments for safety
                groupId = await self._db.addSensorGroup(
                    name=name,
                    irradianceSensor=userInput.get(CONF_REF_SENSOR, ""),
                    tempSensor=userInput.get(CONF_TEMP_SENSOR, ""),
                    tempPanelSensor=userInput.get(CONF_TEMP_PANEL_SENSOR),
                    windSensor=userInput.get(CONF_WIND_SENSOR),
                    refTilt=float(userInput.get(CONF_REF_TILT, 0)),
                    refOrientation=float(userInput.get(CONF_REF_ORIENTATION, 180)),
                    weatherEntity=userInput.get(CONF_WEATHER_ENTITY),
                    illuminanceSensor=userInput.get(CONF_ILLUMINANCE_SENSOR)
                )
                
                # BRANCH A: If in guided flow (Roof -> SG), link them and continue
                if getattr(self, '_guidedFlow', False):
                    roofName = self.tempData.get(CONF_ROOF_NAME)
                    if roofName:
                        roofId = slugify(roofName)
                        roofObj = self._db.getRoof(roofId)
                        if roofObj:
                             # Re-save roof with the new linked group ID
                             await self._db.addRoof(
                                name=roofObj.name,
                                tilt=roofObj.tilt,
                                azimuth=roofObj.azimuth,
                                sensorGroupId=groupId,
                                strings=roofObj.strings
                             )
                    
                    # Ensure the next step exists in the current class (Mixins safety)
                    if hasattr(self, 'async_step_string_create_select_relations'):
                        return await self.async_step_string_create_select_relations()
                
                # BRANCH B: If it's a subentry flow (Pill)
                if getattr(self, "_isSubentry", False) or "Subentry" in self.__class__.__name__:
                     return self.async_create_entry(
                         title=name,
                         data={CONF_SENSOR_GROUP_NAME: name}
                     )
                
                return self.async_abort(reason="list_updated")

            except Exception as e:
                _LOGGER.exception(f"Critical error in sensor group creation flow: {e}")
                errors["base"] = "unknown"
            
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
