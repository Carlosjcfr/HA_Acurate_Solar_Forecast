import voluptuous as vol
import logging
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

_LOGGER = logging.getLogger(__name__)

class StringsFlowMixin:
    # =================================================================================
    # BRANCH 3: STRINGS (Integraciones - Create Only)
    # =================================================================================

    # 3.1 CREATE STRING - Step A: Select Brand & Group
    async def async_step_string_create_select_relations(self, userInput=None):
         if userInput is not None:
            self.tempData.update(userInput)
            
            # If the optional field is cleared by the user, remove it from tempData
            if CONF_REAL_PRODUCTION_SENSOR not in userInput:
                self.tempData.pop(CONF_REAL_PRODUCTION_SENSOR, None)
                
            return await self.async_step_string_create_details()

         schema = self._getStringSelectRelationsSchema()
         if schema is None:
             return self.async_abort(reason="no_sensor_groups_available")
             
         return self.async_show_form(step_id="string_create_select_relations", data_schema=schema)


    # 3.1 CREATE STRING - Step B: Details
    async def async_step_string_create_details(self, userInput=None):
        if userInput is not None:
             finalData = {**self.tempData, **userInput}
             
             # Always save string to DB under the current Roof
             roofName = finalData.get(CONF_ROOF_NAME)
             roofId = slugify(roofName) if roofName else "default"
             stringName = finalData[CONF_STRING_NAME]
             stringId = slugify(stringName)
             
             # sensor group is now owned by the roof, not the string
             stringData = {
                 CONF_STRING_NAME: stringName,
                 CONF_BRAND: finalData.get(CONF_BRAND),
                 CONF_REAL_PRODUCTION_SENSOR: finalData.get(CONF_REAL_PRODUCTION_SENSOR),
                 CONF_PANEL_MODEL: finalData.get(CONF_PANEL_MODEL),
                 CONF_NUM_PANELS: finalData.get(CONF_NUM_PANELS),
                 CONF_NUM_STRINGS: finalData.get(CONF_NUM_STRINGS),
                 CONF_TILT: finalData.get(CONF_TILT),
                 CONF_AZIMUTH: finalData.get(CONF_AZIMUTH)
             }
             
             await self._db.addStringToRoof(roofId, stringId, stringData)

             # RELOAD UI: Find the subentry for this roof and reload it so the new string appears
             parentEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
             if parentEntryId:
                 parentEntry = self.hass.config_entries.async_get_entry(parentEntryId)
                 if parentEntry:
                     for sub in parentEntry.subentries:
                         if sub.data.get(CONF_ROOF_NAME) == roofName:
                             _LOGGER.info(f"Reloading subentry '{sub.title}' ({sub.subentry_id}) to show new string")
                             await self.hass.config_entries.async_reload_subentry(sub)
                             break
             
             # Clear string-specific data for the next iteration
             self.tempData.pop(CONF_STRING_NAME, None)
             self.tempData.pop(CONF_REAL_PRODUCTION_SENSOR, None)
             self.tempData.pop(CONF_PANEL_MODEL, None)
             self.tempData.pop(CONF_NUM_PANELS, None)
             self.tempData.pop(CONF_NUM_STRINGS, None)
             
             # In guided flow (RoofSubentryFlowHandler): show loop menu
             if getattr(self, "_guidedFlow", False):
                 return await self.async_step_string_loop()
                 
             return self.async_abort(reason="list_updated")
            
        schema = self._getStringDetailsSchema()
        return self.async_show_form(step_id="string_create_details", data_schema=schema)
