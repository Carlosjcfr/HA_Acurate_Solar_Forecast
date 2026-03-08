import voluptuous as vol
from homeassistant.helpers import selector
from ..variables.const import (
    CONF_TILT, CONF_AZIMUTH, CONF_ROOF_NAME,
    CONF_STRING_NAME, CONF_BRAND, CONF_PANEL_MODEL,
    CONF_NUM_PANELS, CONF_NUM_STRINGS
)

class RoofsFlowMixin:
    # =================================================================================
    # BRANCH: ROOFS (Create, Edit, Delete + String Management)
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

    # --- SELECT ROOF TO MANAGE ---
    async def async_step_roof_edit_select(self, user_input=None):
        if user_input is not None:
             self.selected_item_id = user_input["selected_roof"]
             # After selecting, show management menu instead of going straight to edit
             return await self.async_step_roof_management_menu()
             
        roofs = self._db.list_roofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(roofs.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="roof_edit_select", data_schema=schema)

    # --- ROOF MANAGEMENT MENU (3 options) ---
    async def async_step_roof_management_menu(self, user_input=None):
        """Intermediate menu after selecting a roof: Edit, Add String, Delete Strings."""
        # Store roof name in temp_data for string creation context
        roof_data = self._db.get_roof(self.selected_item_id)
        if roof_data:
            self.temp_data[CONF_ROOF_NAME] = roof_data.get("name", self.selected_item_id)
        
        menu_options = ["roof_edit_form", "roof_add_string"]
        
        # Only show delete strings if the roof has strings
        roof_strings = self._db.get_roof_strings(self.selected_item_id)
        if roof_strings:
            menu_options.append("roof_delete_string_select")
        
        return self.async_show_menu(
            step_id="roof_management_menu",
            menu_options=menu_options
        )

    # --- EDIT ROOF PARAMETERS ---
    async def async_step_roof_edit_form(self, user_input=None):
        if user_input is not None:
            await self._db.add_roof(
                user_input["name"],
                user_input[CONF_TILT],
                user_input[CONF_AZIMUTH]
            )
            return self.async_abort(reason="list_updated")

        # Load Data
        roof_data = self._db.get_roof(self.selected_item_id)
        schema = vol.Schema({
            vol.Required("name", default=roof_data.get("name")): str,
            vol.Required(CONF_TILT, default=roof_data.get("tilt")): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=roof_data.get("azimuth")): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })
        return self.async_show_form(step_id="roof_edit_form", data_schema=schema)

    # --- ADD STRING TO THIS ROOF ---
    async def async_step_roof_add_string(self, user_input=None):
        """Redirects to the string creation flow with the roof pre-selected."""
        # The roof name is already in temp_data from roof_management_menu
        # Flag: we are managing an existing roof, so don't create a new entry at the end
        self.temp_data["_managing_existing_roof"] = True
        return await self.async_step_string_create_select_relations()

    # --- DELETE STRING FROM THIS ROOF ---
    async def async_step_roof_delete_string_select(self, user_input=None):
        """Select a string to delete from the current roof."""
        if user_input is not None:
            string_id = user_input["selected_string"]
            await self._db.delete_string_from_roof(self.selected_item_id, string_id)
            return self.async_abort(reason="list_updated")
        
        roof_strings = self._db.get_roof_strings(self.selected_item_id)
        if not roof_strings:
            return self.async_abort(reason="no_strings_available")
        
        # Build options: {string_id: string_name}
        string_options = []
        for sid, sdata in roof_strings.items():
            label = sdata.get(CONF_STRING_NAME, sid) if isinstance(sdata, dict) else sid
            string_options.append({"value": sid, "label": label})
        
        schema = vol.Schema({
            vol.Required("selected_string"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=string_options, mode="dropdown")
            )
        })
        return self.async_show_form(step_id="roof_delete_string_select", data_schema=schema)

    # --- DELETE ROOF ---
    async def async_step_roof_delete_select(self, user_input=None):
        if user_input is not None:
             roof_id = user_input["selected_roof"]
             await self._db.delete_roof(roof_id)
             return self.async_abort(reason="list_updated")
             
        roofs = self._db.list_roofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(roofs.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="roof_delete_select", data_schema=schema)
