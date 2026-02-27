import math
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..variables.const import *
from .helpers import slugify

_LOGGER = logging.getLogger(__name__)

# --- UTILS & CONSTANTS ---
SUN_MOVEMENT_THRESHOLD = 0.5  # Re-calculate geometry only if sun moves > 0.5 degrees
SENSOR_REFRESH_THRESHOLD = 5.0 # Re-calculate if input changes significantly

def get_converted_value(hass, entity_id, target_type, default=0.0):
    """Fetch state and convert to target internal units (Celsius, m/s, W/m2)."""
    if not entity_id:
        return default
    state = hass.states.get(entity_id)
    if not state or state.state in ["unavailable", "unknown"]:
        return default
        
    try:
        val = float(state.state)
        unit = (state.attributes.get("unit_of_measurement") or "").lower().strip()
        
        # 1. TEMPERATURE (Target: Celsius)
        if target_type == "temperature":
            if unit in ["°f", "f"]: 
                return (val - 32) * 5 / 9
            if unit == "k": 
                return val - 273.15
            return val 
            
        # 2. SPEED (Target: m/s)
        if target_type == "speed":
            if unit == "km/h": return val / 3.6
            if unit == "mph": return val / 2.23694
            if unit == "kn": return val / 1.94384
            if unit == "ft/s": return val / 3.28084
            if unit == "bft":
                bft_map = [0, 0.45, 2.45, 4.4, 6.7, 9.35, 12.3, 15.5, 18.95, 22.6, 26.45, 30.55, 32.7]
                idx = int(min(max(0, val), 12))
                return bft_map[idx]
            return val
            
        # 3. IRRADIANCE (Target: W/m²)
        if target_type == "irradiance":
            if "kw/m" in unit: return val * 1000.0
            return val

        # 4. ILLUMINANCE (Target: lux)
        if target_type == "illuminance":
            return val
            
        return val
    except:
        return default

# --- SENSOR CLASSES ---
class SolarStringSensor(SensorEntity):
    def __init__(self, hass, config_entry_data, db, sensor_group_data):
        self.hass = hass
        self._config = config_entry_data
        self._db = db
        self._sensor_group = sensor_group_data
        
        model_name = self._config.get(CONF_PANEL_MODEL)
        self._panel_data = db.data.get(slugify(model_name)) if db and db.data else None
        
        string_name_raw = self._config.get(CONF_STRING_NAME)
        self._attr_has_entity_name = True
        self._attr_name = f"{string_name_raw} Potencia"
        self._attr_unique_id = f"str_{slugify(string_name_raw)}"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {}

        real_sensor_id = self._config.get(CONF_REAL_PRODUCTION_SENSOR)
        device_iden = None
        device_name = None
        
        if real_sensor_id:
             ent_reg = er.async_get(hass)
             entity_entry = ent_reg.async_get(real_sensor_id)
             if entity_entry and entity_entry.device_id:
                 dev_reg = dr.async_get(hass)
                 device = dev_reg.async_get(entity_entry.device_id)
                 if device:
                     device_iden = device.identifiers

        if not device_iden:
            device_iden = {(DOMAIN, self._attr_unique_id)} 
            device_name = string_name_raw

        self._attr_device_info = DeviceInfo(
            identifiers=device_iden,
            name=device_name if not real_sensor_id else None,
            manufacturer=(self._panel_data.brand if self._panel_data else "Generic") if not real_sensor_id else None,
            model=model_name if not real_sensor_id else None,
            via_device=(DOMAIN, self._sensor_group.name if self._sensor_group else "Unknown") if not real_sensor_id else None
        )
        
        # Performance caching
        self._last_sun_az = -100.0
        self._last_sun_el = -100.0
        self._cached_geometric_factor = 0.0
        self._cached_cloud_info = (0.0, "None", 1.0) # (coverage, source, kt)
        self._last_irr_ref = -1.0
        self._last_t_amb = -100.0

    @property
    def check_config(self):
        return self._panel_data is not None and self._sensor_group is not None

    def calculate_cos_incidence(self, sun_az, sun_el, panel_az, panel_tilt):
        sol_zenith_rad = math.radians(90 - sun_el)
        sol_az_rad = math.radians(sun_az)
        panel_tilt_rad = math.radians(panel_tilt)
        panel_az_rad = math.radians(panel_az)
        cos_theta = (math.cos(sol_zenith_rad) * math.cos(panel_tilt_rad)) + \
                    (math.sin(sol_zenith_rad) * math.sin(panel_tilt_rad) * math.cos(sol_az_rad - panel_az_rad))
        return max(0, cos_theta)

    @callback
    def _update_logic(self, event=None):
        if not self.check_config: return
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state: return
        sun_az = float(sun_state.attributes.get("azimuth", 180))
        sun_el = float(sun_state.attributes.get("elevation", 0))

        if sun_el <= 0:
            if self._attr_native_value != 0:
                self._attr_native_value = 0
                self._attr_extra_state_attributes = {"estado_solar": "Noche", "sun_elevation": sun_el}
                self.async_write_ha_state()
            return

        # 1. Inputs Check
        ref_sensor = self._sensor_group.ref_sensor
        irr_ref = get_converted_value(self.hass, ref_sensor, "irradiance", 0.0)
        t_amb = get_converted_value(self.hass, self._sensor_group.temp_sensor, "temperature", 25.0)
        
        # 2. Geometric & Cloud Update (Throttled)
        sun_moved = (abs(sun_az - self._last_sun_az) > SUN_MOVEMENT_THRESHOLD or 
                     abs(sun_el - self._last_sun_el) > SUN_MOVEMENT_THRESHOLD)
        
        if sun_moved:
            target_az = self._config.get(CONF_AZIMUTH)
            target_tilt = self._config.get(CONF_TILT)
            cos_theta_target = self.calculate_cos_incidence(sun_az, sun_el, target_az, target_tilt)
            cos_theta_ref = self.calculate_cos_incidence(sun_az, sun_el, self._sensor_group.ref_orientation, self._sensor_group.ref_tilt)
            
            try:
                self._cached_geometric_factor = 0 if cos_theta_ref < 0.05 else cos_theta_target / cos_theta_ref
            except ZeroDivisionError:
                self._cached_geometric_factor = 0

            # Cloud & KT calculation (also depends on sun_el)
            kt, cloud_source, cloud_coverage = 1.0, "None", 0.0
            ill_sensor = self._sensor_group.illuminance_sensor
            if ill_sensor:
                lux_real = get_converted_value(self.hass, ill_sensor, "illuminance", -1)
                if lux_real >= 0 and sun_el > 2:
                    lux_teo = 120000 * math.sin(math.radians(sun_el))
                    if lux_teo > 10:
                        try:
                            kt = max(0.05, min(1.2, lux_real / lux_teo))
                            cloud_coverage = max(0, min(100, 100 * (1 - kt)))
                            cloud_source = "Lux Sensor"
                        except ZeroDivisionError: pass
            
            if cloud_source == "None":
                weather_entity = self._sensor_group.weather_entity
                if weather_entity:
                    w_state = self.hass.states.get(weather_entity)
                    if w_state and w_state.state not in ["unavailable", "unknown"]:
                        if w_state.domain == "sensor":
                            try: cloud_coverage = float(w_state.state)
                            except: pass
                        elif w_state.domain == "weather":
                            c = w_state.attributes.get("cloud_coverage")
                            if c is not None:
                               try: cloud_coverage = float(c)
                               except: pass
                            else:
                                condition = w_state.state
                                if condition in ["sunny", "clear-night"]: cloud_coverage = 0
                                elif condition in ["partlycloudy"]: cloud_coverage = 40
                                elif condition in ["cloudy"]: cloud_coverage = 90
                                else: cloud_coverage = 100
                        kt = 1.0 - (cloud_coverage / 100.0)
                        cloud_source = "Weather Entity"
            
            self._cached_cloud_info = (cloud_coverage, cloud_source, kt)
            self._last_sun_az, self._last_sun_el = sun_az, sun_el

        # 3. Final Power Calculation (Always uses current inputs)
        cloud_coverage, cloud_source, kt = self._cached_cloud_info
        k = 0.1 + (0.8 * (cloud_coverage / 100.0))
        combined_factor = ((1 - k) * self._cached_geometric_factor) + (k * 1.0)
        irr_target = irr_ref * combined_factor

        try:
            p_stc = self._panel_data.p_stc if self._panel_data else 450
            gamma = (self._panel_data.gamma if self._panel_data else -0.35) / 100.0
            noct = self._panel_data.noct if self._panel_data else 45
            
            t_cell = t_amb + (irr_target / 800) * (noct - 20)
            power_unit = p_stc * (irr_target / 1000.0) * (1 + (gamma * (t_cell - 25)))
            total_power = max(0, power_unit * self._config.get(CONF_NUM_PANELS, 1) * self._config.get(CONF_NUM_STRINGS, 1))
        except Exception as e:
            _LOGGER.error(f"Error calculating solar power for {self.name}: {e}")
            total_power, irr_target, t_cell = 0, 0, t_amb

        self._attr_native_value = round(total_power, 2)
        self._attr_extra_state_attributes = {
            "irradiancia_incidente_estimada": round(irr_target, 1),
            "factor_transposicion": round(geometric_factor, 3),
            "temperatura_celula": round(t_cell, 1),
            "cloud_coverage_estimated": round(cloud_coverage, 1),
            "cloud_source": cloud_source
        }
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Suscribirse a actualizaciones."""
        entities = ["sun.sun", self._sensor_group.ref_sensor, self._sensor_group.temp_sensor]
        if self._sensor_group.weather_entity: entities.append(self._sensor_group.weather_entity)
        if self._sensor_group.illuminance_sensor: entities.append(self._sensor_group.illuminance_sensor)
        self.async_on_remove(async_track_state_change_event(self.hass, entities, self._update_logic))

class SensorGroupVirtualSensor(SensorEntity):
    def __init__(self, hass, config_entry, target_device_identifiers=None):
        self.hass = hass
        self._config = config_entry.data
        self._name = self._config.get(CONF_SENSOR_GROUP_NAME)
        self._attr_name = self._name
        self._attr_unique_id = f"sg_{slugify(self._name)}_status"
        self._attr_icon = "mdi:link-variant"
        
        if target_device_identifiers:
            self._attr_device_info = DeviceInfo(identifiers=target_device_identifiers)
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, config_entry.entry_id)},
                name=self._name,
                manufacturer="Accurate Solar Forecast",
                model="Sensor Group",
                entry_type=dr.DeviceEntryType.SERVICE
            )

    async def async_added_to_hass(self):
        sensors = [v for k,v in self._config.items() if "sensor" in k or k == CONF_WEATHER_ENTITY]
        self.async_on_remove(async_track_state_change_event(self.hass, sensors, self._update_state))
        self._update_state()

    @callback
    def _update_state(self, event=None):
        attributes = {}
        status = "OK"
        for k, attr in [(CONF_REF_SENSOR, "irradiance"), (CONF_TEMP_SENSOR, "temperature")]:
            ent = self._config.get(k)
            if ent:
                st = self.hass.states.get(ent)
                if st:
                    attributes[attr] = st.state
                    if st.state in ["unavailable", "unknown"]: status = "Partial"
                else: status = "Error"
        
        if attributes.get("irradiance") in ["unavailable", "unknown", None]: status = "Unavailable"
        self._attr_native_value = status
        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()

class SensorGroupCloudinessSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "cloud_coverage"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cloud-percent"

    def __init__(self, hass, config_entry, target_device_identifiers=None):
        self.hass = hass
        self._config = config_entry.data
        self._name = self._config.get(CONF_SENSOR_GROUP_NAME)
        self._attr_unique_id = f"sg_{slugify(self._name)}_cloudiness"
        self._attr_device_info = DeviceInfo(identifiers=target_device_identifiers) if target_device_identifiers else DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)}, name=self._name, entry_type=dr.DeviceEntryType.SERVICE
        )
        self._last_sun_el = -100.0
        self._cached_value = 0.0

    async def async_added_to_hass(self):
        entities = ["sun.sun"]
        if self._config.get(CONF_ILLUMINANCE_SENSOR): entities.append(self._config[CONF_ILLUMINANCE_SENSOR])
        if self._config.get(CONF_WEATHER_ENTITY): entities.append(self._config[CONF_WEATHER_ENTITY])
        self.async_on_remove(async_track_state_change_event(self.hass, entities, self._update_logic))
        self._update_logic()

    @callback
    def _update_logic(self, event=None):
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state: return
        sun_el = float(sun_state.attributes.get("elevation", 0))
        
        # Throttling
        if abs(sun_el - self._last_sun_el) < SUN_MOVEMENT_THRESHOLD:
            # Check if source sensors changed (if event is from a sensor change, we should probably re-calc)
            if event and event.data.get("entity_id") == "sun.sun":
                return

        cloud_coverage = 0.0
        if sun_el > 0:
            ill_sensor = self._config.get(CONF_ILLUMINANCE_SENSOR)
            if ill_sensor:
                lux_real = get_converted_value(self.hass, ill_sensor, "illuminance", -1)
                if lux_real >= 0 and sun_el > 2:
                    lux_teo = 120000 * math.sin(math.radians(sun_el))
                    if lux_teo > 10:
                        cloud_coverage = max(0, min(100, 100 * (1 - (lux_real / lux_teo))))
        
        self._last_sun_el = sun_el
        self._attr_native_value = round(cloud_coverage, 1)
        self.async_write_ha_state()

class SolarStringPerformanceSensor(SensorEntity):
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-line"

    def __init__(self, hass, config_entry_data, db, sensor_group_data):
        self.hass = hass
        self._config = config_entry_data
        self._string_name = self._config.get(CONF_STRING_NAME)
        self._attr_has_entity_name = True
        self._attr_name = f"{self._string_name} Rendimiento"
        self._attr_unique_id = f"str_{slugify(self._string_name)}_performance"
        real_sensor_id = self._config.get(CONF_REAL_PRODUCTION_SENSOR)
        device_iden = None
        if real_sensor_id:
             entity_entry = er.async_get(hass).async_get(real_sensor_id)
             if entity_entry and entity_entry.device_id:
                 device = dr.async_get(hass).async_get(entity_entry.device_id)
                 if device: device_iden = device.identifiers
        self._attr_device_info = DeviceInfo(identifiers=device_iden or {(DOMAIN, f"str_{self._string_name.lower().replace(' ', '_')}")})
        self.real_sensor_id = real_sensor_id

    async def async_added_to_hass(self):
        if self.real_sensor_id:
            self.async_on_remove(async_track_state_change_event(self.hass, [self.real_sensor_id], self._update_state))
        
    @callback
    def _update_state(self, event=None):
        if not self.real_sensor_id: return
        real_state = self.hass.states.get(self.real_sensor_id)
        if not real_state or real_state.state in ["unavailable", "unknown"]: return
        try: real_w = float(real_state.state)
        except: return
        sibling_uid = f"str_{slugify(self._string_name)}"
        sibling_entry = er.async_get(self.hass).async_get_entity_id("sensor", DOMAIN, sibling_uid)
        forecast_w = 1 
        if sibling_entry:
            s_state = self.hass.states.get(sibling_entry)
            if s_state and s_state.state not in ["unavailable", "unknown"]:
                try: forecast_w = float(s_state.state)
                except: pass
        if forecast_w < 1: forecast_w = 1
        self._attr_native_value = round((real_w / forecast_w) * 100, 1)
        self.async_write_ha_state()

class AccurateSolarSensorDBSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "pv_db_status"
    _attr_unique_id = "pv_database_status"
    _attr_icon = "mdi:solar-panel"
    _attr_native_unit_of_measurement = "items"

    def __init__(self, hass, db):
        self.hass = hass
        self._db = db
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, "pv_database_global")}, name="Módulos Fotovoltaicos", model="Database")
        self._update_state()

    def _update_state(self):
        models, roofs = self._db.list_models(), self._db.list_roofs()
        self._attr_native_value = len(models) + len(roofs)
        self.async_write_ha_state()
    
    async def async_added_to_hass(self):
        self._update_state()
