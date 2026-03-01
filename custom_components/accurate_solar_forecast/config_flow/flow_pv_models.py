import voluptuous as vol
from homeassistant.helpers import selector
from ..variables.const import CONF_BRAND, CONF_VOC, CONF_ISC, CONF_VMP, CONF_IMP
from ..core import slugify

class PvModelsFlowMixin:
    async def async_step_menu_pv_models(self, userInput=None):
        """Submenú para Módulos FV."""
        options = ["pv_model_create"]
        
        models = self._db.listModels()
        if models:
             options.append("pv_model_edit_select")
             
             # Check if there are models other than default to allow delete
             protectedId = slugify("Generico 450W")
             deletableModels = [k for k in models.keys() if k != protectedId]
             if len(deletableModels) > 0:
                options.append("pv_model_delete_select")
             
        return self.async_show_menu(
            step_id="menu_pv_models",
            menu_options=options
        )

    # 1.1 CREATE PV MODEL
    async def async_step_pv_model_create(self, userInput=None):
        """Crear un nuevo modelo."""
        errors = {}
        if userInput is not None:
             # Guardar en DB
            await self._db.addModel(
                userInput["name"],
                userInput[CONF_BRAND],
                userInput["p_stc"],
                userInput["gamma"],
                userInput["noct"],
                userInput[CONF_VOC],
                userInput[CONF_ISC],
                userInput[CONF_VMP],
                userInput[CONF_IMP]
            )
            return self.async_abort(reason="list_updated")

        return self._showPvModelForm("pv_model_create", errors)

    # 1.2 EDIT PV MODEL (Select -> Form)
    async def async_step_pv_model_edit_select(self, userInput=None):
        if userInput is not None:
             self.selectedItemId = userInput["selected_model"]
             return await self.async_step_pv_model_edit_form()
             
        return self._showModelSelector("pv_model_edit_select")

    async def async_step_pv_model_edit_form(self, userInput=None):
        if userInput is not None:
            await self._db.addModel(
                userInput["name"],
                userInput[CONF_BRAND],
                userInput["p_stc"],
                userInput["gamma"],
                userInput["noct"],
                userInput[CONF_VOC],
                userInput[CONF_ISC],
                userInput[CONF_VMP],
                userInput[CONF_IMP]
            )
            return self.async_abort(reason="list_updated")

        # Load Data
        modelData = self._db.getModel(self.selectedItemId)
        return self._showPvModelForm("pv_model_edit_form", {}, defaultData=modelData)


    # Helper: Model Form
    def _showPvModelForm(self, stepId, errors, defaultData=None):
        if defaultData is None: defaultData = {}
        
        brandsList = self._db.listBrands()
        schema = vol.Schema({
            vol.Required("name", default=defaultData.get("name", vol.UNDEFINED)): str,
            vol.Required(CONF_BRAND, default=defaultData.get("brand", vol.UNDEFINED)): selector.SelectSelector(
                selector.SelectSelectorConfig(options=brandsList, custom_value=True, mode="dropdown")
            ),
            vol.Required("p_stc", default=defaultData.get("p_stc", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required("gamma", default=defaultData.get("gamma", vol.UNDEFINED)): vol.Coerce(float),
            vol.Required("noct", default=defaultData.get("noct", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.Required(CONF_VOC, default=defaultData.get("voc", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(CONF_ISC, default=defaultData.get("isc", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(CONF_VMP, default=defaultData.get("vmp", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            vol.Required(CONF_IMP, default=defaultData.get("imp", vol.UNDEFINED)): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
        })
        return self.async_show_form(step_id=stepId, data_schema=schema, errors=errors)

    # 1.4 DELETE PV MODEL
    async def async_step_pv_model_delete_select(self, userInput=None):
        if userInput is not None:
             modelId = userInput["selected_model"]
             if modelId == slugify("Generico 450W"):
                 return self.async_abort(reason="cannot_delete_default")
             
             await self._db.deleteModel(modelId)
             return self.async_abort(reason="list_updated")
             
        models = self._db.listModels()
        protectedId = slugify("Generico 450W")
        if protectedId in models:
            del models[protectedId]

        if not models:
             return self.async_abort(reason="no_models_available_to_delete")
        
        schema = vol.Schema({
            vol.Required("selected_model"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(models.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="pv_model_delete_select", data_schema=schema)

    # Helper: Model Selector
    def _showModelSelector(self, stepId):
        models = self._db.listModels() # {id: name}
        if not models:
             return self.async_abort(reason="no_models_available")
        
        schema = vol.Schema({
            vol.Required("selected_model"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(models.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id=stepId, data_schema=schema)
