import voluptuous as vol
import logging
from homeassistant.helpers import selector
from ..variables.const import (
    DOMAIN, CONF_TILT, CONF_AZIMUTH, CONF_ROOF_NAME, CONF_SENSOR_GROUP_NAME
)

_LOGGER = logging.getLogger(__name__)

class RoofsFlowMixin:
    # =================================================================================
    # BRANCH: ROOFS (Create, Edit, Delete)
    # =================================================================================
    def _getAllRoofs(self):
        """Helper to get all roof subentries from the current config entry."""
        configEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
        if not configEntryId:
            return {}
        entry = self.hass.config_entries.async_get_entry(configEntryId)
        if not entry:
            return {}
        
        return {
            sub.subentry_id: sub.data.get(CONF_ROOF_NAME, sub.title)
            for sub in entry.subentries
            if sub.data.get(CONF_ROOF_NAME)
        }

    async def async_step_menu_roofs(self, userInput=None):
        """Submenú para Tejados."""
        options = ["roof_create"]
        
        roofs = self._getAllRoofs()
        if roofs:
             options.append("roof_edit_select")
             options.append("roof_delete_select")
             
        return self.async_show_menu(
            step_id="menu_roofs",
            menu_options=options
        )

    async def async_step_roof_create(self, userInput=None):
        """Create a roof from the management menu (pill: Gestión → Tejados → Crear)."""
        if userInput is not None:
            name = userInput["name"]
            tilt = float(userInput[CONF_TILT])
            azimuth = float(userInput[CONF_AZIMUTH])
            
            # This is a basic creation without guided flow (no strings yet)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ROOF_NAME: name,
                    CONF_TILT: tilt,
                    CONF_AZIMUTH: azimuth,
                    "strings": {}
                }
            )

        schema = self._getRoofCreateSchema()
        return self.async_show_form(step_id="roof_create", data_schema=schema)

    async def async_step_roof_edit_select(self, userInput=None):
        if userInput is not None:
             self.selectedSubentryId = userInput["selected_roof"]
             return await self.async_step_roof_edit_form()
             
        roofs = self._getAllRoofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in roofs.items()], 
                    mode="dropdown"
                )
            )
        })
        return self.async_show_form(step_id="roof_edit_select", data_schema=schema)

    async def async_step_roof_edit_form(self, userInput=None):
        configEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(configEntryId)
        subentry = next((s for s in entry.subentries if s.subentry_id == self.selectedSubentryId), None)
        
        if not subentry:
            return self.async_abort(reason="not_found")

        if userInput is not None:
            newData = dict(subentry.data)
            newData.update({
                CONF_ROOF_NAME: userInput["name"],
                CONF_TILT: float(userInput[CONF_TILT]),
                CONF_AZIMUTH: float(userInput[CONF_AZIMUTH]),
                CONF_SENSOR_GROUP_NAME: userInput.get("selected_sensor_group", "")
            })
            
            self.hass.config_entries.async_update_subentry(entry, subentry.subentry_id, data=newData)
            await self.hass.config_entries.async_reload_subentry(subentry)
            
            return self.async_abort(reason="list_updated")

        # Load Data
        sensorGroups = self._db.listSensorGroups()
        schema = vol.Schema({
            vol.Required("name", default=subentry.data.get(CONF_ROOF_NAME)): str,
            vol.Required(CONF_TILT, default=subentry.data.get(CONF_TILT, 30.0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=subentry.data.get(CONF_AZIMUTH, 180.0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required("selected_sensor_group", default=subentry.data.get(CONF_SENSOR_GROUP_NAME) or vol.UNDEFINED): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in sensorGroups.items()], 
                    mode="dropdown"
                )
            ),
        })
        return self.async_show_form(step_id="roof_edit_form", data_schema=schema)

    async def async_step_roof_delete_select(self, userInput=None):
        if userInput is not None:
             configEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
             entry = self.hass.config_entries.async_get_entry(configEntryId)
             await self.hass.config_entries.async_remove_subentry(entry, userInput["selected_roof"])
             return self.async_abort(reason="list_updated")
             
        roofs = self._getAllRoofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in roofs.items()], 
                    mode="dropdown"
                )
            )
        })
        return self.async_show_form(step_id="roof_delete_select", data_schema=schema)
