import voluptuous as vol
from homeassistant.helpers import selector
from .const import CONF_TILT, CONF_AZIMUTH

class RoofsFlowMixin:
    # =================================================================================
    # BRANCH: ROOFS (Create, Edit, Delete)
    # =================================================================================
    async def async_step_menu_roofs(self, user_input=None):
        """Submenú para Tejados."""
        options = ["roof_create"]
        
        roofs = self._db.list_roofs()
        if roofs and len(roofs) > 0:
             options.append("roof_edit_select")
             options.append("roof_delete_select")
             
        return self.async_show_menu(
            step_id="menu_roofs",
            menu_options=options
        )

    async def async_step_roof_edit_select(self, user_input=None):
        if user_input is not None:
             self.selected_item_id = user_input["selected_roof"]
             return await self.async_step_roof_edit_form()
             
        roofs = self._db.list_roofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(roofs.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="roof_edit_select", data_schema=schema)

    async def async_step_roof_edit_form(self, user_input=None):
        if user_input is not None:
            await self._db.add_roof(
                user_input["name"],
                user_input[CONF_TILT],
                user_input[CONF_AZIMUTH]
            )
            return self.async_abort(reason="pv_models_saved") # Reuse similar success msg or add new

        # Load Data
        roof_data = self._db.get_roof(self.selected_item_id)
        schema = vol.Schema({
            vol.Required("name", default=roof_data.get("name")): str,
            vol.Required(CONF_TILT, default=roof_data.get("tilt")): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=roof_data.get("azimuth")): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })
        return self.async_show_form(step_id="roof_edit_form", data_schema=schema)

    async def async_step_roof_delete_select(self, user_input=None):
        if user_input is not None:
             roof_id = user_input["selected_roof"]
             await self._db.delete_roof(roof_id)
             return self.async_abort(reason="pv_models_saved")
             
        roofs = self._db.list_roofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(roofs.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="roof_delete_select", data_schema=schema)
