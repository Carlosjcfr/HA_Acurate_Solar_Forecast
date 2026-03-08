import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from ..variables.const import *
from ..databases.acurate_solar_sensor_db import AcurateSolarSensorDB
from .flow_pv_models import PvModelsFlowMixin
from .flow_roofs import RoofsFlowMixin
from .flow_sensor_groups import SensorGroupsFlowMixin
from .flow_strings import StringsFlowMixin

class AccurateForecastCommonFlow:
    """Common methods for both ConfigFlow and OptionsFlow."""
    
    def _get_sensor_group_schema(self, default_data):
        valid_irradiance_sensors = []
        valid_wind_sensors = []
        for state in self.hass.states.async_all("sensor"):
            attributes = state.attributes
            if (attributes.get("device_class") == "irradiance" or 
                attributes.get("unit_of_measurement") in ["W/m²", "W/m2"]):
                valid_irradiance_sensors.append(state.entity_id)
                
            if (attributes.get("device_class") == "wind_speed" or 
                attributes.get("unit_of_measurement") in ["m/s", "km/h"]):
                valid_wind_sensors.append(state.entity_id)
                
        valid_irradiance_sensors.sort()
        valid_wind_sensors.sort()

        def get_default(key, fallback=vol.UNDEFINED):
            val = default_data.get(key)
            return val if val is not None else fallback

        ref_default = get_default(CONF_REF_SENSOR)
        if ref_default is not vol.UNDEFINED and ref_default not in valid_irradiance_sensors:
             # Ensure the old valid sensor is temporarily allowed so the form doesn't crash
             valid_irradiance_sensors.append(ref_default)
             
        wind_default = get_default(CONF_WIND_SENSOR)
        if wind_default is not vol.UNDEFINED and wind_default not in valid_wind_sensors:
             # Ensure the old valid sensor is temporarily allowed so the form doesn't crash
             valid_wind_sensors.append(wind_default)

        return vol.Schema({
            vol.Required(CONF_SENSOR_GROUP_NAME, default=get_default(CONF_SENSOR_GROUP_NAME, "")): str,
            vol.Optional(CONF_WEATHER_ENTITY, default=get_default(CONF_WEATHER_ENTITY)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_ILLUMINANCE_SENSOR, default=get_default(CONF_ILLUMINANCE_SENSOR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="illuminance")
            ),
            vol.Required(CONF_REF_SENSOR, default=ref_default): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=valid_irradiance_sensors)
            ),
            vol.Required(CONF_REF_TILT, default=get_default(CONF_REF_TILT, 0)): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_REF_ORIENTATION, default=get_default(CONF_REF_ORIENTATION, 180)): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.Required(CONF_TEMP_SENSOR, default=get_default(CONF_TEMP_SENSOR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_TEMP_PANEL_SENSOR, default=get_default(CONF_TEMP_PANEL_SENSOR)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_WIND_SENSOR, default=wind_default): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=valid_wind_sensors)
            ),
        })

    def _get_string_select_relations_schema(self):
         brands_list = self._db.list_brands()
         sensor_groups = self._db.list_sensor_groups()
         if not sensor_groups: return None # Indicate abort condition
         
         group_options = list(sensor_groups.keys())
         roof_options = ["Nuevo tejado"] + list(self._db.list_roofs().values())

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
         
         if self.temp_data.get(CONF_REAL_PRODUCTION_SENSOR):
             schema_dict[vol.Optional(CONF_REAL_PRODUCTION_SENSOR, default=self.temp_data.get(CONF_REAL_PRODUCTION_SENSOR))] = selector.EntitySelector(
                 selector.EntitySelectorConfig(domain="sensor", device_class="power")
             )
         else:
             schema_dict[vol.Optional(CONF_REAL_PRODUCTION_SENSOR)] = selector.EntitySelector(
                 selector.EntitySelectorConfig(domain="sensor", device_class="power")
             )
             
         # Remove roof selection because we are already in the context of a roof.
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
                     if CONF_TILT not in self.temp_data:  # If not reconfiguring existing tilt
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

class AccurateForecastFlow(AccurateForecastCommonFlow, PvModelsFlowMixin, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AccurateForecastOptionsFlowHandler(config_entry)

    def __init__(self):
        self._db = None
        
        # State Management
        self.selected_item_id = None     # ID of the item being edited/deleted
        self.temp_data = {}              # Temporary storage for multi-step flows
        
        # Branch Handling
        # Branch 1: PV Models
        # Branch 2: Strings
        # Branch 3: Sensor Groups
        
    async def async_step_user(self, user_input=None):
        """Menú Principal: ¿Qué quieres gestionar?"""
        # Asegurar que DOMAIN existe en hass.data
        self.hass.data.setdefault(DOMAIN, {})
        # Reset generic temporary data to ensure clean state
        self.temp_data = {}

        # Inicializar la base de datos si no existe
        if "db" not in self.hass.data[DOMAIN]:
            self._db = AcurateSolarSensorDB(self.hass)
            await self._db.async_load()
            self.hass.data[DOMAIN]["db"] = self._db
        else:
            self._db = self.hass.data[DOMAIN]["db"]
        
        menu_options = ["menu_pv_models"]
        
        # Strings/Roofs require a sensor group to be associated with
        if self._db.list_sensor_groups() and len(self._db.list_sensor_groups()) > 0:
            menu_options.append("menu_roofs")
            
        menu_options.append("menu_sensor_groups")
        
        return self.async_show_menu(
            step_id="user",
            menu_options=menu_options
        )

    # =================================================================================
    # RECONFIGURE FLOW (Native "Configure" button support)
    # =================================================================================
    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of an existing entry."""
        # Ensure DB is loaded (as async_step_user is not called here)
        self.hass.data.setdefault(DOMAIN, {})
        if "db" not in self.hass.data[DOMAIN]:
            self._db = AcurateSolarSensorDB(self.hass)
            await self._db.async_load()
            self.hass.data[DOMAIN]["db"] = self._db
        else:
            self._db = self.hass.data[DOMAIN]["db"]
            
        self.reconfigure_entry = self._get_reconfigure_entry()
        
        if CONF_SENSOR_GROUP_NAME in self.reconfigure_entry.data:
            return await self.async_step_reconfigure_sensor_group()
        elif CONF_STRING_NAME in self.reconfigure_entry.data:
            return await self.async_step_reconfigure_string()
            
        return self.async_abort(reason="not_supported")

    async def async_step_reconfigure_sensor_group(self, user_input=None):
        """Handle reconfiguration of a Sensor Group."""
        if user_input is not None:
             old_name = self.reconfigure_entry.data[CONF_SENSOR_GROUP_NAME]
             new_name = user_input[CONF_SENSOR_GROUP_NAME]
             
             # Update DB
             # If name changed, delete old DB entry (derived from old name)
             if old_name != new_name:
                 old_id = old_name.lower().replace(" ", "_")
                 # We try to delete, but simple delete_sensor_group might suffice
                 await self._db.delete_sensor_group(old_id)
                 
             await self._db.add_sensor_group(
                new_name,
                user_input[CONF_REF_SENSOR],
                user_input[CONF_TEMP_SENSOR],
                user_input.get(CONF_TEMP_PANEL_SENSOR),
                user_input.get(CONF_WIND_SENSOR),
                user_input[CONF_REF_TILT],
                user_input[CONF_REF_ORIENTATION],
                user_input.get(CONF_WEATHER_ENTITY),
                user_input.get(CONF_ILLUMINANCE_SENSOR)
             )
             
             # Update Config Entry
             self.hass.config_entries.async_update_entry(
                 self.reconfigure_entry, 
                 data=user_input, 
                 title="Modulos y Sensores"
             )
             return self.async_update_reload_and_abort(self.reconfigure_entry)
             
        schema = self._get_sensor_group_schema(self.reconfigure_entry.data)
        return self.async_show_form(step_id="reconfigure_sensor_group", data_schema=schema)

    async def async_step_reconfigure_string(self, user_input=None):
        """Handle reconfiguration of a String by reusing the creation flow."""
        self.temp_data = dict(self.reconfigure_entry.data)
        return await self.async_step_string_create_select_relations()

class AccurateForecastOptionsFlowHandler(AccurateForecastCommonFlow, PvModelsFlowMixin, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.temp_data = dict(config_entry.data)
        self._db = None

    async def async_step_init(self, user_input=None):
        self.hass.data.setdefault(DOMAIN, {})
        if "db" not in self.hass.data[DOMAIN]:
            self._db = AcurateSolarSensorDB(self.hass)
            await self._db.async_load()
            self.hass.data[DOMAIN]["db"] = self._db
        else:
            self._db = self.hass.data[DOMAIN]["db"]
            
        if CONF_SENSOR_GROUP_NAME in self.config_entry.data:
            return await self.async_step_sensor_group()
        elif CONF_STRING_NAME in self.config_entry.data:
            return await self.async_step_string_select_relations()
        elif CONF_ROOF_NAME in self.config_entry.data:
            # For roof entries, go directly to string management
            self.temp_data[CONF_ROOF_NAME] = self.config_entry.data[CONF_ROOF_NAME]
            return await self.async_step_string_select_relations()
            
        return self.async_abort(reason="not_supported")

    async def async_step_sensor_group(self, user_input=None):
        if user_input is not None:
             old_name = self.config_entry.data[CONF_SENSOR_GROUP_NAME]
             new_name = user_input[CONF_SENSOR_GROUP_NAME]
             
             if old_name != new_name:
                 old_id = old_name.lower().replace(" ", "_")
                 await self._db.delete_sensor_group(old_id)
                 
             await self._db.add_sensor_group(
                new_name,
                user_input[CONF_REF_SENSOR],
                user_input[CONF_TEMP_SENSOR],
                user_input.get(CONF_TEMP_PANEL_SENSOR),
                user_input.get(CONF_WIND_SENSOR),
                user_input[CONF_REF_TILT],
                user_input[CONF_REF_ORIENTATION],
                user_input.get(CONF_WEATHER_ENTITY),
                user_input.get(CONF_ILLUMINANCE_SENSOR)
             )
             
             self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)
             return self.async_create_entry(title="", data={})
             
        schema = self._get_sensor_group_schema(self.config_entry.data)
        return self.async_show_form(step_id="sensor_group", data_schema=schema)

    async def async_step_string_select_relations(self, user_input=None):
         if user_input is not None:
            self.temp_data.update(user_input)
            if self.temp_data.get(CONF_ROOF_NAME) == "Nuevo tejado":
                return await self.async_step_roof_create()
            return await self.async_step_string_details()

         schema = self._get_string_select_relations_schema()
         if schema is None:
             return self.async_abort(reason="no_sensor_groups_available")
             
         return self.async_show_form(step_id="string_select_relations", data_schema=schema)

    async def async_step_roof_create(self, user_input=None):
        if user_input is not None:
            name = user_input["name"]
            tilt = user_input[CONF_TILT]
            azimuth = user_input[CONF_AZIMUTH]
            await self._db.add_roof(name, tilt, azimuth)
            self.temp_data[CONF_ROOF_NAME] = name
            return await self.async_step_string_details()
            
        schema = self._get_roof_create_schema()
        return self.async_show_form(step_id="roof_create", data_schema=schema)

    async def async_step_string_details(self, user_input=None):
        if user_input is not None:
             final_data = {**self.temp_data, **user_input}
             self.hass.config_entries.async_update_entry(self.config_entry, data=final_data)
             return self.async_create_entry(title="", data={})
            
        schema = self._get_string_details_schema()
        return self.async_show_form(step_id="string_details", data_schema=schema)