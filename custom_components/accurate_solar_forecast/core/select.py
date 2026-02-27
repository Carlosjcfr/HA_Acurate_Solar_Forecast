import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..variables.const import *

_LOGGER = logging.getLogger(__name__)

class SolarStringRoofSelect(SelectEntity):
    """Select entity for choosing the roof of a solar string."""
    _attr_has_entity_name, _attr_translation_key, _attr_icon = True, "roof", "mdi:home-roof"
    def __init__(self, hass, stringData, db, configEntry, stringId, roofId):
        self.hass, self._configEntry, self._data, self._stringId, self._roofId, self._db = hass, configEntry, stringData, stringId, roofId, db
        self._stringName, self._attr_unique_id = self._data.get(CONF_STRING_NAME), f"str_{self._stringId}_roof_select"
        from .helpers import slugify
        self._sensorGroup = db.getSensorGroup(self._data.get("selected_sensor_group"))
        modelName = self._data.get("panel_model")
        self._panelData = db.data.get(slugify(modelName)) if db and db.data else None

    @property
    def options(self): return list(self._db.listRoofs().values())
    @property
    def current_option(self): return self._data.get(CONF_ROOF_NAME)
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
                 if device: deviceIdentifiers, foundDevice = device.identifiers, True
        return DeviceInfo(
            identifiers=deviceIdentifiers,
            name=self._stringName if not foundDevice else None,
            manufacturer=(self._panelData.brand if self._panelData else "Generic") if not foundDevice else None,
            model=(self._panelData.name if self._panelData else modelName) if not foundDevice else None,
            via_device=(DOMAIN, self._sensorGroup.name) if (not foundDevice and self._sensorGroup) else None
        )

    async def async_select_option(self, option: str) -> None:
        targetRoofId = next((rid for rid, rname in self._db.listRoofs().items() if rname == option), None)
        if not targetRoofId: return
        roofObj = self._db.getRoof(targetRoofId)
        newData = self._configEntry.data.copy()
        newData[CONF_ROOF_NAME] = option
        if roofObj:
            if roofObj.tilt is not None: newData[CONF_TILT] = roofObj.tilt
            if roofObj.azimuth is not None: newData[CONF_AZIMUTH] = roofObj.azimuth
        self.hass.config_entries.async_update_entry(self._configEntry, data=newData)
        await self.hass.config_entries.async_reload(self._configEntry.entry_id)
