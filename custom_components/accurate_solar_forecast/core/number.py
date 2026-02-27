import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..variables.const import *

_LOGGER = logging.getLogger(__name__)

class SolarStringNumberEntity(NumberEntity):
    """Base class for Solar String numbers."""
    def __init__(self, hass, stringData, db, configEntry, stringId, roofId, sensorGroupData):
        self.hass, self._data, self._db, self._configEntry = hass, stringData, db, configEntry
        self._stringId, self._roofId, self._sensorGroup = stringId, roofId, sensorGroupData
        self._stringName = self._data.get(CONF_STRING_NAME)
        self._attr_has_entity_name, self._debounceUnsub, self._key = True, None, None
        from .helpers import slugify
        modelName = self._data.get(CONF_PANEL_MODEL)
        self._panelData = db.data.get(slugify(modelName)) if db and db.data else None

    @property
    def device_info(self):
        from .helpers import slugify
        stringIdSlug = f"str_{slugify(self._stringName)}"
        deviceIdentifiers = {(DOMAIN, stringIdSlug)}
        realSensorId = self._data.get(CONF_REAL_PRODUCTION_SENSOR)
        foundDevice = False
        if realSensorId:
             entityEntry = er.async_get(self.hass).async_get(realSensorId)
             if entityEntry and entityEntry.device_id:
                 device = dr.async_get(self.hass).async_get(entityEntry.device_id)
                 if device:
                     deviceIdentifiers, foundDevice = device.identifiers, True
        return DeviceInfo(
            identifiers=deviceIdentifiers,
            name=self._stringName if not foundDevice else None,
            manufacturer=(self._panelData.brand if self._panelData else "Generic") if not foundDevice else None,
            model=(self._panelData.name if self._panelData else modelName) if not foundDevice else None,
            via_device=(DOMAIN, self._sensorGroup.name) if (not foundDevice and self._sensorGroup) else None
        )

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
        if self._debounceUnsub: self._debounceUnsub()
        async def _performUpdate(_now):
            self._data[self._key] = value
            await self._db.addStringToRoof(self._roofId, self._stringId, self._data)
            await self.hass.config_entries.async_reload(self._configEntry.entry_id)
        self._debounceUnsub = async_call_later(self.hass, 2, _performUpdate)

class SolarStringTiltNumber(SolarStringNumberEntity):
    _attr_native_min_value, _attr_native_max_value, _attr_native_step = 0, 90, 1
    _attr_native_unit_of_measurement, _attr_mode, _attr_icon = "°", NumberMode.BOX, "mdi:angle-acute"
    def __init__(self, hass, stringData, db, configEntry, stringId, roofId, sensorGroupData):
        super().__init__(hass, stringData, db, configEntry, stringId, roofId, sensorGroupData)
        self._attr_name, self._attr_unique_id, self._attr_native_value, self._key = "Inclinación", f"str_{self._stringId}_tilt", self._data.get(CONF_TILT, 0), CONF_TILT

class SolarStringAzimuthNumber(SolarStringNumberEntity):
    _attr_native_min_value, _attr_native_max_value, _attr_native_step = 0, 360, 1
    _attr_native_unit_of_measurement, _attr_mode, _attr_icon = "°", NumberMode.BOX, "mdi:compass"
    def __init__(self, hass, stringData, db, configEntry, stringId, roofId, sensorGroupData):
        super().__init__(hass, stringData, db, configEntry, stringId, roofId, sensorGroupData)
        self._attr_name, self._attr_unique_id, self._attr_native_value, self._key = "Orientación", f"str_{self._stringId}_azimuth", self._data.get(CONF_AZIMUTH, 180), CONF_AZIMUTH
