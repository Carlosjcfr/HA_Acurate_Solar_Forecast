import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..variables.const import *

_LOGGER = logging.getLogger(__name__)

class SolarStringRoofSelect(SelectEntity):
    """Select entity for choosing the roof of a solar string."""
    _attr_has_entity_name, _attr_translation_key, _attr_icon = True, "roof", "mdi:home-roof"
    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id):
        self.hass, self._config_entry, self._data, self._string_id, self._roof_id, self._db = hass, config_entry, string_data, string_id, roof_id, db
        self._string_name, self._attr_unique_id = self._data.get(CONF_STRING_NAME), f"str_{self._string_id}_roof_select"
        from .helpers import slugify
        self._sensor_group = db.get_sensor_group(self._data.get("selected_sensor_group"))
        model_name = self._data.get("panel_model")
        self._panel_data = db.data.get(slugify(model_name)) if db and db.data else None

    @property
    def options(self): return list(self._db.list_roofs().values())
    @property
    def current_option(self): return self._data.get(CONF_ROOF_NAME)
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
                 if device: device_identifiers, found_device = device.identifiers, True
        return DeviceInfo(
            identifiers=device_identifiers,
            name=self._string_name if not found_device else None,
            manufacturer=(self._panel_data.brand if self._panel_data else "Generic") if not found_device else None,
            model=(self._panel_data.name if self._panel_data else model_name) if not found_device else None,
            via_device=(DOMAIN, self._sensor_group.name) if (not found_device and self._sensor_group) else None
        )

    async def async_select_option(self, option: str) -> None:
        roof_id = next((rid for rid, rname in self._db.list_roofs().items() if rname == option), None)
        if not roof_id: return
        roof_obj = self._db.get_roof(roof_id)
        new_data = self._config_entry.data.copy()
        new_data[CONF_ROOF_NAME] = option
        if roof_obj:
            if roof_obj.tilt is not None: new_data[CONF_TILT] = roof_obj.tilt
            if roof_obj.azimuth is not None: new_data[CONF_AZIMUTH] = roof_obj.azimuth
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)
