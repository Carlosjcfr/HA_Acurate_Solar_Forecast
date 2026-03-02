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
             
             # Case 1: Guided Flow - store in tempData for final creation
             if self._guidedFlow:
                 data = dict(self.tempData)
                 data.setdefault("strings", {})[stringId] = stringData
                 self.tempData = data
             
             # Case 2: Standalone creation (Pill) - update existing subentry
             else:
                 parentEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
                 targetSubId = self.context.get("selected_roof_id") or self.context.get("subentry_id")
                 
                 if parentEntryId and targetSubId:
                     parentEntry = self.hass.config_entries.async_get_entry(parentEntryId)
                     if parentEntry:
                        sub = next((s for s in parentEntry.subentries if s.subentry_id == targetSubId), None)
                        if sub:
                             # Create new data dict with updated strings
                             newSubData = dict(sub.data)
                             allStrings = dict(newSubData.get("strings", {}))
                             allStrings[stringId] = stringData
                             newSubData["strings"] = allStrings
                             
                             _LOGGER.info(f"Updating subentry '{sub.title}' ({sub.subentry_id}) with new string '{stringName}'")
                             self.hass.config_entries.async_update_subentry(parentEntry, sub.subentry_id, data=newSubData)
                             
                             # Reload to reflect changes
                             await self.hass.config_entries.async_reload_subentry(sub)
             
             # Clear string-specific data for the next iteration (important for the loop)
             for key in [CONF_STRING_NAME, CONF_REAL_PRODUCTION_SENSOR, CONF_PANEL_MODEL, CONF_NUM_PANELS, CONF_NUM_STRINGS, CONF_TILT, CONF_AZIMUTH]:
                 self.tempData.pop(key, None)
             
             # In guided flow: show loop menu
             if self._guidedFlow:
                 return await self.async_step_string_loop()
                 
             return self.async_abort(reason="list_updated")
            
        schema = self._getStringDetailsSchema()
        return self.async_show_form(step_id="string_create_details", data_schema=schema)
