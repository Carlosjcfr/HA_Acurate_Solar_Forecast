"""Configuration flow for Accurate Solar Forecast."""
import voluptuous as vol
import logging
from typing import Any, Dict, Optional, List

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import *
from .db import AccurateSolarSensorDB
from .helpers import getSubentryMenuState, slugify
from .models import PvModel, SolarString, Roof, SensorGroup

try:
    from homeassistant.config_entries import ConfigSubentryFlow
except ImportError:
    class ConfigSubentryFlow:
        pass

_LOGGER = logging.getLogger(__name__)

class AccurateForecastCommonFlow:
    """Common methods for both ConfigFlow, OptionsFlow and SubentryFlow."""

    @property
    def tempData(self):
        """Persistent state storage across flow steps (using HA context)."""
        if "temp_data" not in self.context:
            self.context["temp_data"] = {}
        return self.context["temp_data"]

    @tempData.setter
    def tempData(self, value):
        self.context["temp_data"] = value

    @property
    def _guidedFlow(self):
        """Flag to indicate if we are in the Roof -> Strings guided workflow."""
        return self.context.get("guided_flow", False)

    @_guidedFlow.setter
    def _guidedFlow(self, value):
        self.context["guided_flow"] = value

    @property
    def _isSubentry(self):
        """Flag for direct subentry creation flows (pills)."""
        return self.context.get("is_subentry", False)

    @_isSubentry.setter
    def _isSubentry(self, value):
        self.context["is_subentry"] = value

    async def _asyncInitRequirements(self):
        """Initialize database and ensure it's loaded."""
        self.hass.data.setdefault(DOMAIN, {})
        
        # Ensure context data is initialized
        if "temp_data" not in self.context:
            self.context["temp_data"] = {}
            
        # Always get or create DB and ensure it is loaded from disk
        if "db" not in self.hass.data[DOMAIN]:
            self._db = AccurateSolarSensorDB(self.hass)
            self.hass.data[DOMAIN]["db"] = self._db
        else:
            self._db = self.hass.data[DOMAIN]["db"]
        
        await self._db.async_load()

    def _getDefault(self, key, sourceData=None, fallback=vol.UNDEFINED):
        """Helper to get default value for schemas."""
        # Use property getter which points to context
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
            uomLower = (attributes.get("unit_of_measurement") or "").lower().strip()
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
            configEntryId = self.context.get("entry_id")
            if configEntryId:
                entry = self.hass.config_entries.async_get_entry(configEntryId)
                if entry:
                    for sub in entry.subentries:
                        if sub.data.get(CONF_ROOF_NAME) == roofName:
                            if CONF_TILT not in self.tempData:
                                defaultTilt = sub.data.get(CONF_TILT, 30)
                            if CONF_AZIMUTH not in self.tempData:
                                defaultAzimuth = sub.data.get(CONF_AZIMUTH, 180)
                            break

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

class PvModelsFlowMixin:
    async def async_step_menu_pv_models(self, userInput=None):
        """Submenú para Módulos FV."""
        options = ["pv_model_create"]
        
        models = self._db.listModels()
        if models:
             options.append("pv_model_edit_select")
             protectedId = slugify("Generico 450W")
             deletableModels = [k for k in models.keys() if k != protectedId]
             if len(deletableModels) > 0:
                options.append("pv_model_delete_select")
             
        return self.async_show_menu(
            step_id="menu_pv_models",
            menu_options=options
        )

    async def async_step_pv_model_create(self, userInput=None):
        """Crear un nuevo modelo."""
        errors = {}
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

        return self._showPvModelForm("pv_model_create", errors)

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

        modelData = self._db.getModel(self.selectedItemId)
        return self._showPvModelForm("pv_model_edit_form", {}, defaultData=modelData)

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

    def _showModelSelector(self, stepId):
        models = self._db.listModels()
        if not models:
             return self.async_abort(reason="no_models_available")
        schema = vol.Schema({
            vol.Required("selected_model"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(models.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id=stepId, data_schema=schema)

class SensorGroupsFlowMixin:
    async def async_step_menu_sensor_groups(self, userInput=None):
        if self._db:
             await self._db.async_load()
        groups = self._db.listSensorGroups()
        if not groups:
             return await self.async_step_sensor_group_create()
        options = ["sensor_group_create", "sensor_group_edit_select"]
        return self.async_show_menu(step_id="menu_sensor_groups", menu_options=options)

    async def async_step_sensor_group_create(self, userInput=None):
         errors = {}
         if userInput is not None:
            try:
                name = userInput.get(CONF_SENSOR_GROUP_NAME)
                if not name:
                    errors[CONF_SENSOR_GROUP_NAME] = "required"
                    return self._showSensorGroupForm("sensor_group_create", errors)
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
                if self._guidedFlow:
                    mainEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
                    if mainEntryId:
                        try:
                            entry = self.hass.config_entries.async_get_entry(mainEntryId)
                            if entry:
                                await self.hass.config_entries.async_add_subentry(
                                    entry, "sensor_group", data={CONF_SENSOR_GROUP_NAME: name}, title=name
                                )
                        except Exception as e:
                            _LOGGER.exception(f"Failed to add sensor group subentry: {e}")
                    data = dict(self.tempData)
                    data[CONF_SENSOR_GROUP_NAME] = groupId
                    self.tempData = data
                    if hasattr(self, 'async_step_string_create_select_relations'):
                        return await self.async_step_string_create_select_relations()
                    if hasattr(self, 'async_step_roof_finish'):
                        return await self.async_step_roof_finish()
                if getattr(self, "_isSubentry", False) or "Subentry" in self.__class__.__name__:
                     return self.async_create_entry(title=name, data={CONF_SENSOR_GROUP_NAME: name})
                return self.async_abort(reason="list_updated")
            except Exception as e:
                _LOGGER.exception(f"Critical error in sensor group creation flow: {e}")
                errors["base"] = "unknown"
         return self._showSensorGroupForm("sensor_group_create", errors)

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
            name = userInput[CONF_SENSOR_GROUP_NAME]
            newId = slugify(name)
            if newId != self.selectedItemId:
                await self._db.deleteSensorGroup(self.selectedItemId)
            await self._db.addSensorGroup(
                name=name,
                irradianceSensor=userInput[CONF_REF_SENSOR],
                tempSensor=userInput[CONF_TEMP_SENSOR],
                tempPanelSensor=userInput.get(CONF_TEMP_PANEL_SENSOR),
                windSensor=userInput.get(CONF_WIND_SENSOR),
                refTilt=float(userInput[CONF_REF_TILT]),
                refOrientation=float(userInput[CONF_REF_ORIENTATION]),
                weatherEntity=userInput.get(CONF_WEATHER_ENTITY),
                illuminanceSensor=userInput.get(CONF_ILLUMINANCE_SENSOR)
            )
            return self.async_abort(reason="list_updated")
        groupData = self._db.getSensorGroup(self.selectedItemId)
        return self._showSensorGroupForm("sensor_group_edit_form", {}, defaultData=groupData)

    def _showSensorGroupForm(self, stepId, errors, defaultData=None):
        if defaultData is None: defaultData = {}
        schema = self._getSensorGroupSchema(defaultData)
        return self.async_show_form(step_id=stepId, data_schema=schema, errors=errors)

class StringsFlowMixin:
    async def async_step_string_create_select_relations(self, userInput=None):
         if userInput is not None:
            self.tempData.update(userInput)
            if CONF_REAL_PRODUCTION_SENSOR not in userInput:
                self.tempData.pop(CONF_REAL_PRODUCTION_SENSOR, None)
            return await self.async_step_string_create_details()
         schema = self._getStringSelectRelationsSchema()
         if schema is None:
             return self.async_abort(reason="no_sensor_groups_available")
         return self.async_show_form(step_id="string_create_select_relations", data_schema=schema)

    async def async_step_string_create_details(self, userInput=None):
        if userInput is not None:
             finalData = {**self.tempData, **userInput}
             roofName = finalData.get(CONF_ROOF_NAME)
             stringName = finalData[CONF_STRING_NAME]
             stringId = slugify(stringName)
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
             if self._guidedFlow:
                 data = dict(self.tempData)
                 data.setdefault("strings", {})[stringId] = stringData
                 self.tempData = data
             else:
                 parentEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
                 targetSubId = self.context.get("selected_roof_id") or self.context.get("subentry_id")
                 if parentEntryId and targetSubId:
                     parentEntry = self.hass.config_entries.async_get_entry(parentEntryId)
                     if parentEntry:
                        sub = next((s for s in parentEntry.subentries if s.subentry_id == targetSubId), None)
                        if sub:
                             newSubData = dict(sub.data)
                             allStrings = dict(newSubData.get("strings", {}))
                             allStrings[stringId] = stringData
                             newSubData["strings"] = allStrings
                             self.hass.config_entries.async_update_subentry(parentEntry, sub.subentry_id, data=newSubData)
                             await self.hass.config_entries.async_reload_subentry(sub)
             for key in [CONF_STRING_NAME, CONF_REAL_PRODUCTION_SENSOR, CONF_PANEL_MODEL, CONF_NUM_PANELS, CONF_NUM_STRINGS, CONF_TILT, CONF_AZIMUTH]:
                 self.tempData.pop(key, None)
             if self._guidedFlow:
                 return await self.async_step_string_loop()
             return self.async_abort(reason="list_updated")
        schema = self._getStringDetailsSchema()
        return self.async_show_form(step_id="string_create_details", data_schema=schema)

class RoofsFlowMixin:
    def _getAllRoofs(self):
        configEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
        if not configEntryId: return {}
        entry = self.hass.config_entries.async_get_entry(configEntryId)
        if not entry: return {}
        return {
            sub.subentry_id: sub.data.get(CONF_ROOF_NAME, sub.title)
            for sub in entry.subentries if sub.data.get(CONF_ROOF_NAME)
        }

    async def async_step_menu_roofs(self, userInput=None):
        options = ["roof_create"]
        roofs = self._getAllRoofs()
        if roofs:
             options.append("roof_edit_select")
             options.append("roof_delete_select")
        return self.async_show_menu(step_id="menu_roofs", menu_options=options)

    async def async_step_user(self, userInput=None):
        if hasattr(self, "subentry_id") or self.context.get("subentry_id"):
            return await self.async_step_roof_manage_menu()
        return await self.async_step_roof_create(userInput)

    async def async_step_roof_manage_menu(self, userInput=None):
        if userInput is not None:
            if userInput["next_step"] == "roof_edit_form":
                return await self.async_step_roof_edit_form()
            if userInput["next_step"] == "string_create_select_relations":
                return await self.async_step_string_create_select_relations()
        return self.async_show_menu(step_id="roof_manage_menu", menu_options=["roof_edit_form", "string_create_select_relations"])

    async def async_step_roof_create(self, userInput=None):
        errors = {}
        if userInput is not None:
             name = userInput["name"]
             tilt = float(userInput[CONF_TILT])
             azimuth = float(userInput[CONF_AZIMUTH])
             sgId = userInput["selected_sensor_group"]
             return self.async_create_entry(
                 title=name,
                 data={
                     CONF_ROOF_NAME: name,
                     CONF_TILT: tilt,
                     CONF_AZIMUTH: azimuth,
                     CONF_SENSOR_GROUP_NAME: sgId,
                     "strings": {}
                 }
             )
        groups = self._db.listSensorGroups()
        if not groups:
            return self.async_abort(reason="no_sensor_groups")
        schema = vol.Schema({
            vol.Required("name"): str,
            vol.Required(CONF_TILT, default=30): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=180): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required("selected_sensor_group"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in groups.items()], mode="dropdown"
                )
            ),
        })
        return self.async_show_form(step_id="roof_create", data_schema=schema, errors=errors)

    async def async_step_roof_edit_select(self, userInput=None):
        if userInput is not None:
             self.selectedItemId = userInput["selected_roof"]
             self.context["selected_roof_id"] = userInput["selected_roof"]
             return await self.async_step_roof_edit_form()
        roofs = self._getAllRoofs()
        if not roofs:
             return self.async_abort(reason="no_roofs_available")
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in roofs.items()], mode="dropdown"
                )
            )
        })
        return self.async_show_form(step_id="roof_edit_select", data_schema=schema)

    async def async_step_roof_edit_form(self, userInput=None):
        configEntryId = getattr(self, "handler", None) or self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(configEntryId)
        targetId = self.context.get("selected_roof_id")
        subentry = next((s for s in entry.subentries if s.subentry_id == targetId), None)
        if not subentry: return self.async_abort(reason="not_found")
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
        sensorGroups = self._db.listSensorGroups()
        schema = vol.Schema({
            vol.Required("name", default=subentry.data.get(CONF_ROOF_NAME)): str,
            vol.Required(CONF_TILT, default=subentry.data.get(CONF_TILT, 30.0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=subentry.data.get(CONF_AZIMUTH, 180.0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required("selected_sensor_group", default=subentry.data.get(CONF_SENSOR_GROUP_NAME) or vol.UNDEFINED): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in sensorGroups.items()], mode="dropdown"
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
                    options=[{"value": k, "label": v} for k, v in roofs.items()], mode="dropdown"
                )
            )
        })
        return self.async_show_form(step_id="roof_delete_select", data_schema=schema)

class PvModelSubentryFlowHandler(AccurateForecastCommonFlow, PvModelsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        return await super().async_step_pv_model_create(userInput)

class RoofSubentryFlowHandler(AccurateForecastCommonFlow, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        if not self.context.get("subentry_id"):
            self.tempData = {}
            self._guidedFlow = True
        if self.context.get("subentry_id"):
            return await self.async_step_roof_manage_menu()
        return await self.async_step_roof_create(userInput)

    async def async_step_roof_create(self, userInput=None):
        if userInput is not None:
            name = userInput["name"]
            tilt = userInput[CONF_TILT]
            azimuth = userInput[CONF_AZIMUTH]
            data = dict(self.tempData)
            data.update({
                CONF_ROOF_NAME: name,
                CONF_TILT: float(tilt),
                CONF_AZIMUTH: float(azimuth),
                "strings": {}
            })
            self.tempData = data
            groups = self._db.listSensorGroups()
            if not groups:
                return await self.async_step_sensor_group_create()
            return await self.async_step_roof_select_sensor_group()
        schema = self._getRoofCreateSchema()
        return self.async_show_form(step_id="roof_create", data_schema=schema)

    async def async_step_roof_select_sensor_group(self, userInput=None):
        if userInput is not None:
            selectedGroupId = userInput["selected_sensor_group"]
            data = dict(self.tempData)
            data[CONF_SENSOR_GROUP_NAME] = selectedGroupId
            self.tempData = data
            return await self.async_step_string_create_select_relations()
        groups = self._db.listSensorGroups()
        schema = vol.Schema({
            vol.Required("selected_sensor_group"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in groups.items()], mode="dropdown"
                )
            )
        })
        return self.async_show_form(step_id="roof_select_sensor_group", data_schema=schema)

    async def async_step_string_loop(self, userInput=None):
        options = ["string_create_select_relations", "roof_finish"]
        return self.async_show_menu(step_id="string_loop", menu_options=options)

    async def async_step_roof_finish(self, userInput=None):
        roofName = self.tempData.get(CONF_ROOF_NAME, "Roof")
        subentryData = {
            CONF_ROOF_NAME: roofName,
            CONF_TILT: self.tempData.get(CONF_TILT, 30.0),
            CONF_AZIMUTH: self.tempData.get(CONF_AZIMUTH, 180.0),
            CONF_SENSOR_GROUP_NAME: self.tempData.get(CONF_SENSOR_GROUP_NAME, ""),
            "strings": self.tempData.get("strings", {})
        }
        self.context.pop("temp_data", None)
        self.context.pop("guided_flow", None)
        return self.async_create_entry(title=roofName, data=subentryData)

class SensorGroupSubentryFlowHandler(AccurateForecastCommonFlow, SensorGroupsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        self._isSubentry = True
        return await super().async_step_sensor_group_create(userInput)

class StringSubentryFlowHandler(AccurateForecastCommonFlow, RoofsFlowMixin, StringsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, userInput=None):
        await self._asyncInitRequirements()
        return await self.async_step_string_select_roof()

    async def async_step_string_select_roof(self, userInput=None):
        if userInput is not None:
            roofId = userInput["selected_roof"]
            roofs = self._getAllRoofs()
            self.tempData[CONF_ROOF_NAME] = roofs.get(roofId, "Roof")
            self.context["selected_roof_id"] = roofId
            return await self.async_step_string_create_select_relations()
        roofs = self._getAllRoofs()
        if not roofs: return self.async_abort(reason="no_roofs_available")
        schema = vol.Schema({
            vol.Required("selected_roof"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in roofs.items()], mode="dropdown"
                )
            )
        })
        return self.async_show_form(step_id="string_select_roof", data_schema=schema)

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
        try:
            state = getSubentryMenuState(configEntry.hass)
        except Exception:
            state = {"hasModels": False, "hasRoofs": False, "hasSensors": False, "canAddString": False}
        supported = {
            "pv_model": PvModelSubentryFlowHandler,
            "roof": RoofSubentryFlowHandler,
            "sensor_group": SensorGroupSubentryFlowHandler,
            "management": MenuSubentryFlowHandler,
        }
        if state["hasRoofs"] and state["hasSensors"] and state["hasModels"]:
            supported["string"] = StringSubentryFlowHandler
        return supported

    async def async_step_user(self, userInput=None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(title="Accurate Solar Forecast", data={})
