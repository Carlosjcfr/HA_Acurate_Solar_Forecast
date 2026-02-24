import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from ..variables.const import *
from ..databases.acurate_solar_sensor_db import AcurateSolarSensorDB
from .flow_pv_models import PvModelsFlowMixin
from .flow_roofs import RoofsFlowMixin
from .flow_sensor_groups import SensorGroupsFlowMixin
from .flow_strings import StringsFlowMixin

_LOGGER = logging.getLogger(__name__)

class AccurateForecastCommonFlow:
    """Common methods for both ConfigFlow and OptionsFlow."""
    
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

        def get_default(key, fallback=vol.UNDEFINED):
            val = default_data.get(key)
            return val if val is not None else fallback

        ref_default = get_default(CONF_REF_SENSOR)
        if ref_default is not vol.UNDEFINED and ref_default not in valid_irradiance_sensors:
             valid_irradiance_sensors.append(ref_default)
             
        wind_default = get_default(CONF_WIND_SENSOR)
        if wind_default is not vol.UNDEFINED and wind_default not in valid_wind_sensors:
             valid_wind_sensors.append(wind_default)

        illu_default = get_default(CONF_ILLUMINANCE_SENSOR)
        if illu_default is not vol.UNDEFINED and illu_default not in valid_illuminance_sensors:
             valid_illuminance_sensors.append(illu_default)

        temp_default = get_default(CONF_TEMP_SENSOR)
        if temp_default is not vol.UNDEFINED and temp_default not in valid_temperature_sensors:
             valid_temperature_sensors.append(temp_default)

        temp_panel_default = get_default(CONF_TEMP_PANEL_SENSOR)
        if temp_panel_default is not vol.UNDEFINED and temp_panel_default not in valid_temperature_sensors:
             valid_temperature_sensors.append(temp_panel_default)

        return vol.Schema({
            vol.Required(CONF_SENSOR_GROUP_NAME, default=get_default(CONF_SENSOR_GROUP_NAME, "")): str,
            vol.Optional(CONF_WEATHER_ENTITY, default=get_default(CONF_WEATHER_ENTITY)): selector.EntitySelector(
                selector.SelectSelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_ILLUMINANCE_SENSOR, default=illu_default): selector.EntitySelector(
                selector.SelectSelectorConfig(include_entities=valid_illuminance_sensors)
            ),
            vol.Required(CONF_REF_SENSOR, default=ref_default): selector.EntitySelector(
                selector.SelectSelectorConfig(include_entities=valid_irradiance_sensors)
            ),
            vol.Required(CONF_REF_TILT, default=get_default(CONF_REF_TILT, 0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_REF_ORIENTATION, default=get_default(CONF_REF_ORIENTATION, 180)): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
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

         def get_default(key, fallback=vol.UNDEFINED):
             val = self.temp_data.get(key)
             return val if val is not None else fallback

         group_default = self.temp_data.get("selected_sensor_group")
         if group_default not in group_options:
             group_default = vol.UNDEFINED
             
         brand_default = self.temp_data.get(CONF_BRAND, "Generic")
         if brand_default not in brands_list:
             brand_default = vol.UNDEFINED

         schema_dict = {
            vol.Required(CONF_STRING_NAME, default=get_default(CONF_STRING_NAME)): str,
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
        def get_default(key, fallback=vol.UNDEFINED):
            val = self.temp_data.get(key)
            return val if val is not None else fallback

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
            vol.Required(CONF_NUM_PANELS, default=get_default(CONF_NUM_PANELS, 1)): vol.All(int, vol.Range(min=1)),
            vol.Required(CONF_NUM_STRINGS, default=get_default(CONF_NUM_STRINGS, 1)): vol.All(int, vol.Range(min=1)),
            vol.Required(CONF_TILT, default=default_tilt): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=default_azimuth): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })

    # MENU STEPS
    async def async_step_user(self, user_input=None):
        """Menú Principal: Acciones rápidas estilo píldoras."""
        self.hass.data.setdefault(DOMAIN, {})
        self.temp_data = {}
        if "db" not in self.hass.data[DOMAIN]:
            self._db = AcurateSolarSensorDB(self.hass)
            await self._db.async_load()
            self.hass.data[DOMAIN]["db"] = self._db
        else:
            self._db = self.hass.data[DOMAIN]["db"]
        
        menu_options = ["pv_model_create", "roof_create", "sensor_group_create"]
        if len(self._db.list_models()) > 0 and len(self._db.list_sensor_groups()) > 0:
            menu_options.append("string_create_select_relations")
        menu_options.append("menu_management")
        
        return self.async_show_menu(step_id="user", menu_options=menu_options)

    async def async_step_menu_management(self, user_input=None):
        """Submenú para gestionar (editar/borrar) elementos existentes."""
        return self.async_show_menu(step_id="menu_management", menu_options=["menu_pv_models", "menu_roofs", "menu_sensor_groups"])

    async def async_step_flow_success(self, user_input=None):
        """Menú de éxito para permitir bucles o finalizar."""
        return self.async_show_menu(step_id="flow_success", menu_options=["user", "finish"])

    async def async_step_finish(self, user_input=None):
        """Finalizar el flujo."""
        if hasattr(self, "config_entry") and self.config_entry:
             return self.async_create_entry(title="", data={})
        return self.async_abort(reason="list_updated")

class AccurateForecastFlow(AccurateForecastCommonFlow, PvModelsFlowMixin, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AccurateForecastOptionsFlowHandler(config_entry)

    def __init__(self):
        self._db = None
        self.selected_item_id = None
        self.temp_data = {}

class AccurateForecastOptionsFlowHandler(AccurateForecastCommonFlow, PvModelsFlowMixin, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.temp_data = dict(config_entry.data)
        self._db = None
        self.selected_item_id = None

    async def async_step_init(self, user_input=None):
        return await self.async_step_user()