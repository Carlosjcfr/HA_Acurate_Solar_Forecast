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

from homeassistant.config_entries import ConfigSubentryFlow

_LOGGER = logging.getLogger(__name__)

class AccurateForecastCommonFlow:
    """Common methods for both ConfigFlow, OptionsFlow and SubentryFlow."""
    
    async def _async_init_requirements(self):
        self.hass.data.setdefault(DOMAIN, {})
        if not hasattr(self, "temp_data"):
            self.temp_data = {}
        if "db" not in self.hass.data[DOMAIN]:
            self._db = AccurateSolarSensorDB(self.hass)
            await self._db.async_load()
            self.hass.data[DOMAIN]["db"] = self._db
        else:
            self._db = self.hass.data[DOMAIN]["db"]

    def _get_default(self, key, source_data=None, fallback=vol.UNDEFINED):
        """Helper to get default value for schemas."""
        data = source_data if source_data is not None else self.temp_data
        val = data.get(key)
        return val if val is not None else fallback

    def _get_sensor_group_schema(self, default_data):
        valid_irradiance_sensors = []
        valid_wind_sensors = []
        valid_illuminance_sensors = []
        valid_temperature_sensors = []
        for state in self.hass.states.async_all("sensor"):
            attributes = state.attributes
            uom_lower = (attributes.get("unit_of_measurement") or "").lower()
            device_class = attributes.get("device_class")

            if (device_class == "irradiance" or 
                uom_lower in ["w/m²", "w/m2"]):
                valid_irradiance_sensors.append(state.entity_id)
                
            if (device_class == "wind_speed" or 
                uom_lower in ["m/s", "km/h", "mph", "kn", "ft/s", "bft"]):
                valid_wind_sensors.append(state.entity_id)

            if (device_class == "illuminance" or 
                uom_lower in ["lx", "lux"]):
                valid_illuminance_sensors.append(state.entity_id)

            if (device_class == "temperature" or 
                uom_lower in ["°c", "°f", "k"]):
                valid_temperature_sensors.append(state.entity_id)
                
        valid_irradiance_sensors.sort()
        valid_wind_sensors.sort()
        valid_illuminance_sensors.sort()
        valid_temperature_sensors.sort()

        ref_default = self._get_default(CONF_REF_SENSOR, default_data)
        if ref_default is not vol.UNDEFINED and ref_default not in valid_irradiance_sensors:
             valid_irradiance_sensors.append(ref_default)
             
        wind_default = self._get_default(CONF_WIND_SENSOR, default_data)
        if wind_default is not vol.UNDEFINED and wind_default not in valid_wind_sensors:
             valid_wind_sensors.append(wind_default)

        illu_default = self._get_default(CONF_ILLUMINANCE_SENSOR, default_data)
        if illu_default is not vol.UNDEFINED and illu_default not in valid_illuminance_sensors:
             valid_illuminance_sensors.append(illu_default)

        temp_default = self._get_default(CONF_TEMP_SENSOR, default_data)
        if temp_default is not vol.UNDEFINED and temp_default not in valid_temperature_sensors:
             valid_temperature_sensors.append(temp_default)

        temp_panel_default = self._get_default(CONF_TEMP_PANEL_SENSOR, default_data)
        if temp_panel_default is not vol.UNDEFINED and temp_panel_default not in valid_temperature_sensors:
             valid_temperature_sensors.append(temp_panel_default)

        return vol.Schema({
            vol.Required(CONF_SENSOR_GROUP_NAME, default=self._get_default(CONF_SENSOR_GROUP_NAME, default_data, "")): str,
            vol.Optional(CONF_WEATHER_ENTITY, default=self._get_default(CONF_WEATHER_ENTITY, default_data)): selector.EntitySelector(
                selector.SelectSelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_ILLUMINANCE_SENSOR, default=illu_default): selector.EntitySelector(
                selector.SelectSelectorConfig(include_entities=valid_illuminance_sensors)
            ),
            vol.Required(CONF_REF_SENSOR, default=ref_default): selector.EntitySelector(
                selector.SelectSelectorConfig(include_entities=valid_irradiance_sensors)
            ),
            vol.Required(CONF_REF_TILT, default=self._get_default(CONF_REF_TILT, default_data, 0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_REF_ORIENTATION, default=self._get_default(CONF_REF_ORIENTATION, default_data, 180)): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required(CONF_TEMP_SENSOR, default=temp_default): selector.EntitySelector(
                selector.SelectSelectorConfig(include_entities=valid_temperature_sensors)
            ),
            vol.Optional(CONF_TEMP_PANEL_SENSOR, default=temp_panel_default): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=valid_temperature_sensors)
            ),
            vol.Optional(CONF_WIND_SENSOR, default=wind_default): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=valid_wind_sensors)
            ),
        })

    def _get_string_select_relations_schema(self):
         brands_list = self._db.list_brands()
         sensor_groups = self._db.list_sensor_groups()
         if not sensor_groups: return None 

         valid_power_sensors = []
         for state in self.hass.states.async_all("sensor"):
             attributes = state.attributes
             if (attributes.get("device_class") == "power" or 
                 (attributes.get("unit_of_measurement") and attributes.get("unit_of_measurement") in ["W", "kW"])):
                 valid_power_sensors.append(state.entity_id)
         valid_power_sensors.sort()
         
         group_options = list(sensor_groups.keys())
         
         group_default = self.temp_data.get("selected_sensor_group")
         if group_default not in group_options:
             group_default = vol.UNDEFINED
             
         brand_default = self.temp_data.get(CONF_BRAND, "Generic")
         if brand_default not in brands_list:
             brand_default = vol.UNDEFINED
             
         schema_dict = {
            vol.Required(CONF_STRING_NAME, default=self._get_default(CONF_STRING_NAME)): str,
            vol.Required("selected_sensor_group", default=group_default): selector.SelectSelector(
                selector.SelectSelectorConfig(options=group_options, mode="dropdown")
            ),
            vol.Required(CONF_BRAND, default=brand_default): selector.SelectSelector(
                selector.SelectSelectorConfig(options=brands_list, mode="dropdown")
            ),
         }
         
         real_prod_default = self.temp_data.get(CONF_REAL_PRODUCTION_SENSOR)
         if real_prod_default and real_prod_default not in valid_power_sensors:
             valid_power_sensors.append(real_prod_default)

         schema_dict[vol.Optional(CONF_REAL_PRODUCTION_SENSOR, default=real_prod_default or vol.UNDEFINED)] = selector.EntitySelector(
             selector.EntitySelectorConfig(include_entities=valid_power_sensors)
         )
         return vol.Schema(schema_dict)

    def _get_roof_create_schema(self):
        return vol.Schema({
            vol.Required("name"): str,
            vol.Required(CONF_TILT, default=30): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=180): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })

    def _get_string_details_schema(self):
        selected_brand = self.temp_data.get(CONF_BRAND, "Generic")
        models_filtered = self._db.list_models_by_brand(selected_brand)
        
        default_tilt = self.temp_data.get(CONF_TILT, 30)
        default_azimuth = self.temp_data.get(CONF_AZIMUTH, 180)
        
        roof_name = self.temp_data.get(CONF_ROOF_NAME)
        if roof_name:
             roof_id = None
             for rid, rname in self._db.list_roofs().items():
                 if rname == roof_name:
                     roof_id = rid
                     break
             
             if roof_id:
                 roof_data = self._db.get_roof(roof_id)
                 if roof_data:
                     if CONF_TILT not in self.temp_data: 
                         default_tilt = roof_data.get("tilt") or 30
                     if CONF_AZIMUTH not in self.temp_data:
                         default_azimuth = roof_data.get("azimuth") or 180

        model_default = self.temp_data.get(CONF_PANEL_MODEL)
        model_options = list(models_filtered.values())
        if model_default not in model_options:
            model_default = vol.UNDEFINED
            
        return vol.Schema({
            vol.Required(CONF_PANEL_MODEL, default=model_default): selector.SelectSelector(
                selector.SelectSelectorConfig(options=model_options, mode="dropdown")
            ),
            vol.Required(CONF_NUM_PANELS, default=self._get_default(CONF_NUM_PANELS, fallback=1)): vol.All(int, vol.Range(min=1)),
            vol.Required(CONF_NUM_STRINGS, default=self._get_default(CONF_NUM_STRINGS, fallback=1)): vol.All(int, vol.Range(min=1)),
            vol.Required(CONF_TILT, default=default_tilt): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=default_azimuth): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })

    # MENU STEPS
    async def async_step_menu_management(self, user_input=None):
        """Submenú para gestionar (editar/borrar) elementos existentes."""
        return self.async_show_menu(step_id="menu_management", menu_options=["menu_pv_models", "menu_roofs", "menu_sensor_groups"])

class PvModelSubentryFlowHandler(AccurateForecastCommonFlow, PvModelsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        await self._async_init_requirements()
        return await super().async_step_pv_model_create(user_input)

class RoofSubentryFlowHandler(AccurateForecastCommonFlow, RoofsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        await self._async_init_requirements()
        return await super().async_step_roof_create(user_input)

class SensorGroupSubentryFlowHandler(AccurateForecastCommonFlow, SensorGroupsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        await self._async_init_requirements()
        return await super().async_step_sensor_group_create(user_input)

class StringSubentryFlowHandler(AccurateForecastCommonFlow, StringsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        await self._async_init_requirements()
        return await super().async_step_string_create_select_relations(user_input)

class MenuSubentryFlowHandler(AccurateForecastCommonFlow, PvModelsFlowMixin, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        await self._async_init_requirements()
        return await super().async_step_menu_management(user_input)

from ..core import get_subentry_menu_state

class AccurateForecastFlow(AccurateForecastCommonFlow, PvModelsFlowMixin, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry) -> dict[str, type[ConfigSubentryFlow]]:
        """Devolver flujos subentry soportados dinámicamente según el estado."""
        state = get_subentry_menu_state(config_entry.hass)
        
        supported = {
            "pv_model": PvModelSubentryFlowHandler,
            "roof": RoofSubentryFlowHandler,
            "sensor_group": SensorGroupSubentryFlowHandler,
            "management": MenuSubentryFlowHandler,
        }
        
        # Solo permitimos añadir un "String" si hay infraestructura previa
        if state["can_add_string"]:
            supported["string"] = StringSubentryFlowHandler
            
        return supported

    def __init__(self):
        self._db = None
        self.selected_item_id = None
        self.temp_data = {}

    async def async_step_user(self, user_input=None):
        if not self._async_current_entries():
            return await self.async_step_setup(user_input)
        
        return self.async_abort(reason="not_supported")

    async def async_step_setup(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Accurate Solar Forecast", data={})
        return self.async_show_form(step_id="setup", data_schema=vol.Schema({}))