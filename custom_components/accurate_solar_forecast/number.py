import logging
from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from .variables.const import DOMAIN, CONF_STRING_NAME, CONF_TILT, CONF_AZIMUTH, CONF_SENSOR_GROUP_NAME, CONF_ROOF_NAME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Accurate Solar Forecast number entities."""
    
    if CONF_ROOF_NAME in config_entry.data:
        db = hass.data[DOMAIN]["db"]
        roof_name = config_entry.data.get(CONF_ROOF_NAME)
        roof_id = roof_name.lower().replace(" ", "_") if roof_name else "default"
        roof_strings = db.get_roof_strings(roof_id)
        
        entities = []
        for string_id, string_data in roof_strings.items():
            combined_data = dict(string_data)
            combined_data[CONF_ROOF_NAME] = roof_name
            entities.append(SolarStringTiltNumber(hass, combined_data, db, config_entry, string_id, roof_id))
            entities.append(SolarStringAzimuthNumber(hass, combined_data, db, config_entry, string_id, roof_id))
            
        if entities:
            async_add_entities(entities)

class SolarStringNumberEntity(NumberEntity):
    """Base class for Solar String numbers."""
    
    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id):
        self.hass = hass
        self._data = string_data
        self._db = db
        self._config_entry = config_entry
        self._string_id = string_id
        self._roof_id = roof_id
        self._string_name = self._data.get(CONF_STRING_NAME)
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        """Return device info linked to the String."""
        # Baseline identifier
        string_id = f"str_{self._string_name.lower().replace(' ', '_')}"
        device_identifiers = {(DOMAIN, string_id)}
        
        # Try to link to Real Production Sensor's device if configured
        from .const import CONF_REAL_PRODUCTION_SENSOR
        from homeassistant.helpers import device_registry as dr, entity_registry as er
        real_sensor_id = self._data.get(CONF_REAL_PRODUCTION_SENSOR)
        self.found_device = False
        if real_sensor_id:
             ent_reg = er.async_get(self.hass)
             entity_entry = ent_reg.async_get(real_sensor_id)
             if entity_entry and entity_entry.device_id:
                 dev_reg = dr.async_get(self.hass)
                 device = dev_reg.async_get(entity_entry.device_id)
                 if device:
                     device_identifiers = device.identifiers
                     found_device = True

        if getattr(self, "found_device", False):
            # No fallback to roof since we want a device per string
            pass

        return DeviceInfo(
            identifiers=device_identifiers
        )

class SolarStringTiltNumber(SolarStringNumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 90
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:angle-acute"

    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id):
        super().__init__(hass, string_data, db, config_entry, string_id, roof_id)
        self._attr_name = f"{self._string_name} Inclinación"
        self._attr_unique_id = f"str_{self._string_id}_tilt"
        self._attr_native_value = self._data.get(CONF_TILT, 0)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        
        # Update DB instead of config entry
        self._data[CONF_TILT] = value
        await self._db.add_string_to_roof(self._roof_id, self._string_id, self._data)
        
        # Reload entry to propagate changes to sensor
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

class SolarStringAzimuthNumber(SolarStringNumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 360
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:compass"

    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id):
        super().__init__(hass, string_data, db, config_entry, string_id, roof_id)
        self._attr_name = f"{self._string_name} Orientación"
        self._attr_unique_id = f"str_{self._string_id}_azimuth"
        self._attr_native_value = self._data.get(CONF_AZIMUTH, 180)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        
        # Update DB instead of config entry
        self._data[CONF_AZIMUTH] = value
        await self._db.add_string_to_roof(self._roof_id, self._string_id, self._data)
        
        # Reload entry to propagate changes to sensor
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)
