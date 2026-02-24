import voluptuous as vol
from homeassistant.helpers import selector
from .const import CONF_BRAND, CONF_VOC, CONF_ISC, CONF_VMP, CONF_IMP

class PvModelsFlowMixin:
    async def async_step_menu_pv_models(self, user_input=None):
        """Submenú para Módulos FV."""
        options = ["pv_model_create"]
        
        models = self._db.list_models()
        if models and len(models) > 0:
             options.append("pv_model_edit_select")
             
             # Check if there are models other than default to allow delete
             # Assuming 'default_450w' is the key for the default model
             deletable_models = [k for k in models.keys() if k != "default_450w"]
             if len(deletable_models) > 0:
                options.append("pv_model_delete_select")
             
        return self.async_show_menu(
            step_id="menu_pv_models",
            menu_options=options
        )

    # 1.1 CREATE PV MODEL
    async def async_step_pv_model_create(self, user_input=None):
        """Crear un nuevo modelo."""
        errors = {}
        if user_input is not None:
             # Guardar en DB
            await self._db.add_model(
                user_input["name"],
                user_input[CONF_BRAND],
                user_input["p_stc"],
                user_input["gamma"],
                user_input["noct"],
                user_input[CONF_VOC],
                user_input[CONF_ISC],
                user_input[CONF_VMP],
                user_input[CONF_IMP]
            )
            return await self.async_step_pv_model_success()

        return self._show_pv_model_form("pv_model_create", errors)

    # 1.2 EDIT PV MODEL (Select -> Form)
    async def async_step_pv_model_edit_select(self, user_input=None):
        if user_input is not None:
             self.selected_item_id = user_input["selected_model"]
             return await self.async_step_pv_model_edit_form()
             
        return self._show_model_selector("pv_model_edit_select")

    async def async_step_pv_model_edit_form(self, user_input=None):
        if user_input is not None:
            await self._db.add_model(
                user_input["name"],
                user_input[CONF_BRAND],
                user_input["p_stc"],
                user_input["gamma"],
                user_input["noct"],
                user_input[CONF_VOC],
                user_input[CONF_ISC],
                user_input[CONF_VMP],
                user_input[CONF_IMP]
            )
            return await self.async_step_pv_model_success()

        # Load Data
        model_data = self._db.get_model(self.selected_item_id)
        return self._show_pv_model_form("pv_model_edit_form", {}, default_data=model_data)

    # 1.3 SUCCESS & LOOP (Menu intermedio)
    async def async_step_pv_model_success(self, user_input=None):
        """Menu intermedio tras crear/editar modelo."""
        return self.async_show_menu(
            step_id="pv_model_success",
            menu_options=["pv_model_create", "pv_model_finish"]
        )

    async def async_step_pv_model_finish(self, user_input=None):
        """Finalizar el flujo de modelos (sin crear entrada en HA, solo guardando DB)."""
        return self.async_abort(reason="list_updated")


    # Helper: Model Form
    def _show_pv_model_form(self, step_id, errors, default_data=None):
        if default_data is None: default_data = {}
        
        brands_list = self._db.list_brands()
        schema = vol.Schema({
            vol.Required("name", default=default_data.get("name", vol.UNDEFINED)): str,
            vol.Required(CONF_BRAND, default=default_data.get("brand", vol.UNDEFINED)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=brands_list, custom_value=True, mode="dropdown")
            ),
            vol.Required("p_stc", default=default_data.get("p_stc", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required("gamma", default=default_data.get("gamma", vol.UNDEFINED)): vol.Coerce(float),
            vol.Required("noct", default=default_data.get("noct", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Required(CONF_VOC, default=default_data.get("voc", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(CONF_ISC, default=default_data.get("isc", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(CONF_VMP, default=default_data.get("vmp", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(CONF_IMP, default=default_data.get("imp", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        })
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    # 1.4 DELETE PV MODEL
    async def async_step_pv_model_delete_select(self, user_input=None):
        if user_input is not None:
             model_id = user_input["selected_model"]
             if model_id == "default_450w":
                 return self.async_abort(reason="cannot_delete_default")
             
             await self._db.delete_model(model_id)
             return self.async_create_entry(title=f"Deleted Model: {model_id}", data={})
             
        models = self._db.list_models()
        if "default_450w" in models:
            del models["default_450w"]

        if not models:
             return self.async_abort(reason="no_models_available_to_delete")
        
        schema = vol.Schema({
            vol.Required("selected_model"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(models.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="pv_model_delete_select", data_schema=schema)

    # Helper: Model Selector
    def _show_model_selector(self, step_id):
        models = self._db.list_models() # {id: name}
        if not models:
             return self.async_abort(reason="no_models_available")
        
        schema = vol.Schema({
            vol.Required("selected_model"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(models.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id=step_id, data_schema=schema)
