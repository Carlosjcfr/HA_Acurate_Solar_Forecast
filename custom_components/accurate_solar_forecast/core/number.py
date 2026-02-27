import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..variables.const import *

_LOGGER = logging.getLogger(__name__)

class SolarStringNumberEntity(NumberEntity):
    """Base class for Solar String numbers."""
    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data):
        self.hass, self._data, self._db, self._config_entry = hass, string_data, db, config_entry
        self._string_id, self._roof_id, self._sensor_group = string_id, roof_id, sensor_group_data
        self._string_name = self._data.get(CONF_STRING_NAME)
        self._attr_has_entity_name, self._debounce_unsub, self._key = True, None, None
        from .helpers import slugify
        model_name = self._data.get(CONF_PANEL_MODEL)
        self._panel_data = db.data.get(slugify(model_name)) if db and db.data else None

    @property
    def device_info(self):
        from .helpers import slugify
        string_id_slug = f"str_{slugify(self._string_name)}"
        device_identifiers = {(DOMAIN, string_id_slug)}
        real_sensor_id = self._data.get(CONF_REAL_PRODUCTION_SENSOR)
        found_device = False
        if real_sensor_id:
             entity_entry = er.async_get(self.hass).async_get(real_sensor_id)
             if entity_entry and entity_entry.device_id:
                 device = dr.async_get(self.hass).async_get(entity_entry.device_id)
                 if device:
                     device_identifiers, found_device = device.identifiers, True
        return DeviceInfo(
            identifiers=device_identifiers,
            name=self._string_name if not found_device else None,
            manufacturer=(self._panel_data.brand if self._panel_data else "Generic") if not found_device else None,
            model=(self._panel_data.name if self._panel_data else model_name) if not found_device else None,
            via_device=(DOMAIN, self._sensor_group.name) if (not found_device and self._sensor_group) else None
        )

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
        if self._debounce_unsub: self._debounce_unsub()
        async def _perform_update(_now):
            self._data[self._key] = value
            await self._db.add_string_to_roof(self._roof_id, self._string_id, self._data)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
        self._debounce_unsub = async_call_later(self.hass, 2, _perform_update)

class SolarStringTiltNumber(SolarStringNumberEntity):
    _attr_native_min_value, _attr_native_max_value, _attr_native_step = 0, 90, 1
    _attr_native_unit_of_measurement, _attr_mode, _attr_icon = "°", NumberMode.BOX, "mdi:angle-acute"
    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data):
        super().__init__(hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data)
        self._attr_name, self._attr_unique_id, self._attr_native_value, self._key = "Inclinación", f"str_{self._string_id}_tilt", self._data.get(CONF_TILT, 0), CONF_TILT

class SolarStringAzimuthNumber(SolarStringNumberEntity):
    _attr_native_min_value, _attr_native_max_value, _attr_native_step = 0, 360, 1
    _attr_native_unit_of_measurement, _attr_mode, _attr_icon = "°", NumberMode.BOX, "mdi:compass"
    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data):
        super().__init__(hass, string_data, db, config_entry, string_id, roof_id, sensor_group_data)
        self._attr_name, self._attr_unique_id, self._attr_native_value, self._key = "Orientación", f"str_{self._string_id}_azimuth", self._data.get(CONF_AZIMUTH, 180), CONF_AZIMUTH
