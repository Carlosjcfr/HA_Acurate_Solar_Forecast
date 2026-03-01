import voluptuous as vol
import logging
from homeassistant.helpers import selector
from ..variables.const import CONF_TILT, CONF_AZIMUTH

_LOGGER = logging.getLogger(__name__)

class RoofsFlowMixin:
    # =================================================================================
    # BRANCH: ROOFS (Create, Edit, Delete)
    # =================================================================================
    async def async_step_menu_roofs(self, userInput=None):
        """Submenú para Tejados."""
        options = ["roof_create"]
        
        roofs = self._db.listRoofs()
        if roofs:
             options.append("roof_edit_select")
             options.append("roof_delete_select")
             
        return self.async_show_menu(
            step_id="menu_roofs",
            menu_options=options
        )

    async def async_step_roof_create(self, userInput=None):
        """Create a roof from the management menu (pill: Gestión → Tejados → Crear).

        After creation, abort back to the integration page.
        NOTE: RoofSubentryFlowHandler overrides this for the full guided flow
        (Roof → SensorGroup → Strings workflow).
        """
        if userInput is not None:
            name = userInput["name"]
            tilt = userInput[CONF_TILT]
            azimuth = userInput[CONF_AZIMUTH]
            await self._db.addRoof(name, tilt, azimuth)
            return self.async_abort(reason="list_updated")

        schema = self._getRoofCreateSchema()
        return self.async_show_form(step_id="roof_create", data_schema=schema)

    async def async_step_roof_edit_select(self, userInput=None):
        if userInput is not None:
             self.selectedItemId = userInput["selected_roof"]
             return await self.async_step_roof_edit_form()
             
        roofs = self._db.listRoofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(roofs.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="roof_edit_select", data_schema=schema)

    async def async_step_roof_edit_form(self, userInput=None):
        if userInput is not None:
            sensorGroupId = userInput.get("selected_sensor_group", "")
            await self._db.addRoof(
                userInput["name"],
                userInput[CONF_TILT],
                userInput[CONF_AZIMUTH],
                sensorGroupId=sensorGroupId
            )
            return self.async_abort(reason="list_updated")

        # Load Data
        roofData = self._db.getRoof(self.selectedItemId)
        sensorGroups = self._db.listSensorGroups()
        schema = vol.Schema({
            vol.Required("name", default=roofData.name): str,
            vol.Required(CONF_TILT, default=roofData.tilt): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=roofData.azimuth): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required("selected_sensor_group", default=roofData.sensorGroupId or vol.UNDEFINED): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(sensorGroups.keys()), mode="dropdown")
            ),
        })
        return self.async_show_form(step_id="roof_edit_form", data_schema=schema)

    async def async_step_roof_delete_select(self, userInput=None):
        if userInput is not None:
             roofId = userInput["selected_roof"]
             await self._db.deleteRoof(roofId)
             return self.async_abort(reason="list_updated")
             
        roofs = self._db.listRoofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(roofs.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="roof_delete_select", data_schema=schema)
