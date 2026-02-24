import logging
import asyncio
from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from .variables.const import (
    DOMAIN, 
    CONF_STRING_NAME, 
    CONF_TILT, 
    CONF_AZIMUTH, 
    CONF_SENSOR_GROUP_NAME, 
    CONF_ROOF_NAME, 
    CONF_REAL_PRODUCTION_SENSOR,
    CONF_PANEL_MODEL,
    CONF_BRAND
)

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
            
            group_name = string_data.get("selected_sensor_group")
            sensor_group_data = db.get_sensor_group(group_name)
            
            entities.append(SolarStringTiltNumber(hass, combined_data, db, config_entry, string_id, roof_id, sensor_group_data))
            entities.append(SolarStringAzimuthNumber(hass, combined_data, db, config_entry, string_id, roof_id, sensor_group_data))
            
        if entities:
            async_add_entities(entities)

class SolarStringNumberEntity(NumberEntity):
    """Base class for Solar String numbers."""
    
    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data):
        self.hass = hass
        self._data = string_data
        self._db = db
        self._config_entry = config_entry
        self._string_id = string_id
        self._roof_id = roof_id
        self._sensor_group = sensor_group_data
        self._string_name = self._data.get(CONF_STRING_NAME)
        self._attr_has_entity_name = True
        self._cancel_update = None

        # Recuperar datos del modelo
        model_name = self._data.get(CONF_PANEL_MODEL)
        self._panel_data = {}
        if db and db.data:
            for v in db.data.values():
                if v.get("name") == model_name:
                    self._panel_data = v
                    break

    @property
    def device_info(self):
        """Return device info linked to the String."""
        # Baseline identifier
        string_id_slug = f"str_{self._string_name.lower().replace(' ', '_')}"
        device_identifiers = {(DOMAIN, string_id_slug)}
        
        # Try to link to Real Production Sensor's device if configured

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
                     self.found_device = True

        return DeviceInfo(
            identifiers=device_identifiers,
            name=self._string_name if not self.found_device else None,
            manufacturer=self._panel_data.get(CONF_BRAND, "Generic") if not self.found_device else None,
            model=self._data.get(CONF_PANEL_MODEL) if not self.found_device else None,
            via_device=(DOMAIN, self._sensor_group.get(CONF_SENSOR_GROUP_NAME)) if (not self.found_device and self._sensor_group) else None
        )

    async def _async_debounced_update(self, key, value):
        """Perform the actual update after debounce."""
        if self._cancel_update:
            self._cancel_update.cancel()
            
        self._cancel_update = asyncio.create_task(self._perform_update(key, value))

    async def _perform_update(self, key, value):
        """Wait 2 seconds then update DB and reload."""
        try:
            await asyncio.sleep(2)
            self._data[key] = value
            await self._db.add_string_to_roof(self._roof_id, self._string_id, self._data)
            _LOGGER.info(f"Updated {key} to {value} for string {self._string_id} in DB")
            # Reload entry to propagate changes to sensor
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
        except asyncio.CancelledError:
            pass

class SolarStringTiltNumber(SolarStringNumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 90
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:angle-acute"

    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data):
        super().__init__(hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data)
        self._attr_name = "Inclinación"
        self._attr_unique_id = f"str_{self._string_id}_tilt"
        self._attr_native_value = self._data.get(CONF_TILT, 0)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value with debounce."""
        self._attr_native_value = value
        self.async_write_ha_state()
        await self._async_debounced_update(CONF_TILT, value)

class SolarStringAzimuthNumber(SolarStringNumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 360
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:compass"

    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data):
        super().__init__(hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data)
        self._attr_name = "Orientación"
        self._attr_unique_id = f"str_{self._string_id}_azimuth"
        self._attr_native_value = self._data.get(CONF_AZIMUTH, 180)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value with debounce."""
        self._attr_native_value = value
        self.async_write_ha_state()
        await self._async_debounced_update(CONF_AZIMUTH, value)
