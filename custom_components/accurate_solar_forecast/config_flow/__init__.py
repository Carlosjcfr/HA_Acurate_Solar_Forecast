"""Configuration flow for Accurate Solar Forecast."""
import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from ..variables import *
from ..databases import AccurateSolarSensorDB
from .flow_pv_models import PvModelsFlowMixin
from .flow_roofs import RoofsFlowMixin
from .flow_sensor_groups import SensorGroupsFlowMixin
from .flow_strings import StringsFlowMixin
from ..core import getSubentryMenuState

try:
    from homeassistant.config_entries import ConfigSubentryFlow
except ImportError:
    class ConfigSubentryFlow:
        pass

_LOGGER = logging.getLogger(__name__)

class AccurateForecastCommonFlow:
    """Common methods for both ConfigFlow, OptionsFlow and SubentryFlow."""
    
    async def _asyncInitRequirements(self):
        self.hass.data.setdefault(DOMAIN, {})
        if not hasattr(self, "tempData"):
            self.tempData = {}
        
        # Always get or create DB and ensure it is loaded from disk to prevent stale flows
        if "db" not in self.hass.data[DOMAIN]:
            self._db = AccurateSolarSensorDB(self.hass)
            self.hass.data[DOMAIN]["db"] = self._db
        else:
            self._db = self.hass.data[DOMAIN]["db"]
        
        await self._db.async_load()

    def _getDefault(self, key, sourceData=None, fallback=vol.UNDEFINED):
        """Helper to get default value for schemas."""
        data = sourceData if sourceData is not None else self.tempData
        val = data.get(key)
        return val if val is not None else fallback

    def _getSensorGroupSchema(self, defaultData):
        validIrradianceSensors = []
        validWindSensors = []
        validIlluminanceSensors = []
        validTemperatureSensors = []
        for state in self.hass.states.async_all("sensor"):
            attributes = state.attributes
            uomLower = (attributes.get("unit_of_measurement") or "").lower()
            deviceClass = attributes.get("device_class")

            if (deviceClass == "irradiance" or 
                uomLower in ["w/m²", "w/m2"]):
                validIrradianceSensors.append(state.entity_id)
                
            if (deviceClass == "wind_speed" or 
                uomLower in ["m/s", "km/h", "mph", "kn", "ft/s", "bft"]):
                validWindSensors.append(state.entity_id)

            if (deviceClass == "illuminance" or 
                uomLower in ["lx", "lux"]):
                validIlluminanceSensors.append(state.entity_id)

            if (deviceClass == "temperature" or 
                uomLower in ["°c", "°f", "k"]):
                validTemperatureSensors.append(state.entity_id)
                
        validIrradianceSensors.sort()
        validWindSensors.sort()
        validIlluminanceSensors.sort()
        validTemperatureSensors.sort()

        refDefault = self._getDefault(CONF_REF_SENSOR, defaultData)
        if refDefault is not vol.UNDEFINED and refDefault not in validIrradianceSensors:
             validIrradianceSensors.append(refDefault)
             
        windDefault = self._getDefault(CONF_WIND_SENSOR, defaultData)
        if windDefault is not vol.UNDEFINED and windDefault not in validWindSensors:
             validWindSensors.append(windDefault)

        illuDefault = self._getDefault(CONF_ILLUMINANCE_SENSOR, defaultData)
        if illuDefault is not vol.UNDEFINED and illuDefault not in validIlluminanceSensors:
             validIlluminanceSensors.append(illuDefault)

        tempDefault = self._getDefault(CONF_TEMP_SENSOR, defaultData)
        if tempDefault is not vol.UNDEFINED and tempDefault not in validTemperatureSensors:
             validTemperatureSensors.append(tempDefault)

        tempPanelDefault = self._getDefault(CONF_TEMP_PANEL_SENSOR, defaultData)
        if tempPanelDefault is not vol.UNDEFINED and tempPanelDefault not in validTemperatureSensors:
             validTemperatureSensors.append(tempPanelDefault)

        # Safety guard: if no sensors of a type found, fall back to unfiltered selector
        def _entitySel(entityList):
            if entityList:
                return selector.EntitySelector(
                    selector.EntitySelectorConfig(include_entities=entityList)
                )
            return selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        return vol.Schema({
            vol.Required(CONF_SENSOR_GROUP_NAME, default=self._getDefault(CONF_SENSOR_GROUP_NAME, defaultData, "")): str,
            vol.Optional(CONF_WEATHER_ENTITY, default=self._getDefault(CONF_WEATHER_ENTITY, defaultData)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_ILLUMINANCE_SENSOR, default=illuDefault): _entitySel(validIlluminanceSensors),
            vol.Required(CONF_REF_SENSOR, default=refDefault): _entitySel(validIrradianceSensors),
            vol.Required(CONF_REF_TILT, default=self._getDefault(CONF_REF_TILT, defaultData, 0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_REF_ORIENTATION, default=self._getDefault(CONF_REF_ORIENTATION, defaultData, 180)): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required(CONF_TEMP_SENSOR, default=tempDefault): _entitySel(validTemperatureSensors),
            vol.Optional(CONF_TEMP_PANEL_SENSOR, default=tempPanelDefault): _entitySel(validTemperatureSensors),
            vol.Optional(CONF_WIND_SENSOR, default=windDefault): _entitySel(validWindSensors),
        })

    def _getStringSelectRelationsSchema(self):
         brandsList = self._db.listBrands()

         validPowerSensors = []
         for state in self.hass.states.async_all("sensor"):
             attributes = state.attributes
             if (attributes.get("device_class") == "power" or 
                 (attributes.get("unit_of_measurement") and attributes.get("unit_of_measurement") in ["W", "kW"])):
                 validPowerSensors.append(state.entity_id)
         validPowerSensors.sort()
             
         brandDefault = self.tempData.get(CONF_BRAND, "Generic")
         if brandDefault not in brandsList:
             brandDefault = vol.UNDEFINED
             
         schemaDict = {
            vol.Required(CONF_STRING_NAME, default=self._getDefault(CONF_STRING_NAME)): str,
            vol.Required(CONF_BRAND, default=brandDefault): selector.SelectSelector(
                selector.SelectSelectorConfig(options=brandsList, mode="dropdown")
            ),
         }
         
         realProdDefault = self.tempData.get(CONF_REAL_PRODUCTION_SENSOR)
         if realProdDefault and realProdDefault not in validPowerSensors:
             validPowerSensors.append(realProdDefault)

         schemaDict[vol.Optional(CONF_REAL_PRODUCTION_SENSOR, default=realProdDefault or vol.UNDEFINED)] = selector.EntitySelector(
             selector.EntitySelectorConfig(include_entities=validPowerSensors)
         )
         return vol.Schema(schemaDict)

    def _getRoofCreateSchema(self):
        """Roof create schema — clean form with just geometry. Sensor group assigned automatically."""
        return vol.Schema({
            vol.Required("name"): str,
            vol.Required(CONF_TILT, default=30): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=180): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })

    def _getStringDetailsSchema(self):
        selectedBrand = self.tempData.get(CONF_BRAND, "Generic")
        modelsFiltered = self._db.listModelsByBrand(selectedBrand)
        
        defaultTilt = self.tempData.get(CONF_TILT, 30)
        defaultAzimuth = self.tempData.get(CONF_AZIMUTH, 180)
        
        # Try to pre-fill tilt/azimuth from the associated roof
        roofName = self.tempData.get(CONF_ROOF_NAME)
        if roofName:
            from ..core import slugify as _slugify
            roofId = _slugify(roofName)
            roofObj = self._db.getRoof(roofId)
            if roofObj:
                if CONF_TILT not in self.tempData:
                    defaultTilt = roofObj.tilt or 30
                if CONF_AZIMUTH not in self.tempData:
                    defaultAzimuth = roofObj.azimuth or 180

        modelDefault = self.tempData.get(CONF_PANEL_MODEL)
        modelOptions = list(modelsFiltered.values())
        if modelDefault not in modelOptions:
            modelDefault = vol.UNDEFINED
            
        return vol.Schema({
            vol.Required(CONF_PANEL_MODEL, default=modelDefault): selector.SelectSelector(
                selector.SelectSelectorConfig(options=modelOptions, mode="dropdown")
            ),
            vol.Required(CONF_NUM_PANELS, default=self._getDefault(CONF_NUM_PANELS, fallback=1)): vol.All(int, vol.Range(min=1)),
            vol.Required(CONF_NUM_STRINGS, default=self._getDefault(CONF_NUM_STRINGS, fallback=1)): vol.All(int, vol.Range(min=1)),
            vol.Required(CONF_TILT, default=defaultTilt): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=defaultAzimuth): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })

    # MENU STEPS
    async def async_step_menu_management(self, userInput=None):
        """Submenú para gestionar (editar/borrar) elementos existentes."""
        return self.async_show_menu(step_id="menu_management", menu_options=["menu_pv_models", "menu_roofs", "menu_sensor_groups"])

class PvModelSubentryFlowHandler(AccurateForecastCommonFlow, PvModelsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        return await super().async_step_pv_model_create(userInput)

class RoofSubentryFlowHandler(AccurateForecastCommonFlow, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, ConfigSubentryFlow):
    """Guided flow: Roof -> (Sensor Group if missing) -> String creation."""
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        self._guidedFlow = True
        return await self.async_step_roof_create(userInput)

    async def async_step_roof_create(self, userInput=None):
        """Override StringsFlowMixin.async_step_roof_create for the guided flow.
        HA maps step_id='roof_create' to this method via MRO, so this class's
        version takes priority over the mixin's version.
        """
        if userInput is not None:
            name = userInput["name"]
            tilt = userInput[CONF_TILT]
            azimuth = userInput[CONF_AZIMUTH]

            # Save roof without sensor group for now
            await self._db.addRoof(name, tilt, azimuth, sensorGroupId="")
            self.tempData[CONF_ROOF_NAME] = name
            self.tempData[CONF_TILT] = tilt
            self.tempData[CONF_AZIMUTH] = azimuth

            groups = self._db.listSensorGroups()
            if not groups:
                # No sensor groups yet — create one first
                return await self.async_step_sensor_group_create()
            else:
                # Sensor groups exist — let user choose which to assign
                return await self.async_step_roof_select_sensor_group()

        schema = self._getRoofCreateSchema()
        return self.async_show_form(step_id="roof_create", data_schema=schema)

    async def async_step_roof_select_sensor_group(self, userInput=None):
        """Step 2 (when groups exist): choose which sensor group to assign to the new roof."""
        if userInput is not None:
            selectedGroupId = userInput["selected_sensor_group"]
            roofName = self.tempData.get(CONF_ROOF_NAME)
            if roofName:
                from ..core import slugify as _slugify
                roofId = _slugify(roofName)
                roof = self._db.getRoof(roofId)
                if roof:
                    await self._db.addRoof(
                        roof.name, roof.tilt, roof.azimuth,
                        sensorGroupId=selectedGroupId
                    )
            return await self.async_step_string_create_select_relations()

        groups = self._db.listSensorGroups()
        schema = vol.Schema({
            vol.Required("selected_sensor_group"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(groups.keys()),
                    mode="dropdown"
                )
            )
        })
        return self.async_show_form(step_id="roof_select_sensor_group", data_schema=schema)

    async def async_step_string_loop(self, userInput=None):
        """After each string: offer to add another or finish and create the hub."""
        roofName = self.tempData.get(CONF_ROOF_NAME, "Roof")
        return self.async_show_menu(
            step_id="string_loop",
            menu_options=["string_add_another", "string_finish"]
        )

    async def async_step_string_add_another(self, userInput=None):
        """Loop back to add another string to the same roof."""
        return await self.async_step_string_create_select_relations()

    async def async_step_string_finish(self, userInput=None):
        """Finalize the flow: create the HA subentry (hub) for this roof."""
        roofName = self.tempData.get(CONF_ROOF_NAME, "Roof")
        return self.async_create_entry(
            title=roofName,
            data={CONF_ROOF_NAME: roofName}
        )

class SensorGroupSubentryFlowHandler(AccurateForecastCommonFlow, SensorGroupsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        self._isSubentry = True
        return await super().async_step_sensor_group_create(userInput)

class StringSubentryFlowHandler(AccurateForecastCommonFlow, StringsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        return await super().async_step_string_create_select_relations(userInput)

class MenuSubentryFlowHandler(AccurateForecastCommonFlow, PvModelsFlowMixin, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        return await super().async_step_menu_management(userInput)

class AccurateForecastFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Accurate Solar Forecast."""
    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, configEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry flow types based on current DB state."""
        try:
            state = getSubentryMenuState(configEntry.hass)
        except Exception:
            state = {"hasModels": False, "hasRoofs": False, "hasSensors": False, "canAddString": False}

        # PV Module, Roof, Sensor Group and Management are always available
        supported = {
            "pv_model": PvModelSubentryFlowHandler,
            "roof": RoofSubentryFlowHandler,
            "sensor_group": SensorGroupSubentryFlowHandler,
            "management": MenuSubentryFlowHandler,
        }

        # String pill requires roof + sensor group + models
        if state["hasRoofs"] and state["hasSensors"] and state["hasModels"]:
            supported["string"] = StringSubentryFlowHandler

        return supported

    async def async_step_user(self, userInput=None):
        """Handle the initial step. Create the main hub entry immediately."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
            
        return self.async_create_entry(title="Accurate Solar Forecast", data={})

