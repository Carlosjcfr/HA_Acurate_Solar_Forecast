"""Select platform for Accurate Solar Forecast."""
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .variables.const import (
    DOMAIN, CONF_ROOF_NAME, CONF_STRING_NAME,
    CONF_REAL_PRODUCTION_SENSOR, CONF_TILT, CONF_AZIMUTH
)
from .core.helpers import slugify

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up the Accurate Solar Forecast select entities."""
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            return

        entities = []
        for roofId, roofObj in db.roofs.items():
            roofName = roofObj.name
            for stringId, stringObj in roofObj.strings.items():
                combinedData = stringObj.to_dict()
                combinedData[CONF_ROOF_NAME] = roofName
                entities.append(SolarStringRoofSelect(hass, combinedData, db, configEntry, stringId, roofId))

        if entities:
            asyncAddEntities(entities)
    except Exception as e:
        _LOGGER.exception(f"Error setting up select platform: {e}")


class SolarStringRoofSelect(SelectEntity):
    """Select entity for choosing the roof of a solar string."""
    _attr_has_entity_name = True
    _attr_translation_key = "roof"
    _attr_icon = "mdi:home-roof"

    def __init__(self, hass, stringData, db, configEntry, stringId, roofId):
        self.hass = hass
        self._configEntry = configEntry
        self._data = stringData
        self._stringId = stringId
        self._roofId = roofId
        self._db = db
        self._stringName = self._data.get(CONF_STRING_NAME)
        self._attr_unique_id = f"str_{self._stringId}_roof_select"
        self._sensorGroup = db.getSensorGroup(self._data.get("selected_sensor_group"))
        modelName = self._data.get("panel_model")
        self._panelData = db.data.get(slugify(modelName)) if db and db.data else None

    @property
    def options(self):
        return list(self._db.listRoofs().values())

    @property
    def current_option(self):
        return self._data.get(CONF_ROOF_NAME)

    @property
    def device_info(self):
        stringIdSlug = f"str_{slugify(self._stringName)}"
        deviceIdentifiers = {(DOMAIN, stringIdSlug)}
        realSensorId = self._data.get(CONF_REAL_PRODUCTION_SENSOR)
        foundDevice = False
        if realSensorId:
            entityEntry = er.async_get(self.hass).async_get(realSensorId)
            if entityEntry and entityEntry.device_id:
                device = dr.async_get(self.hass).async_get(entityEntry.device_id)
                if device:
                    deviceIdentifiers = device.identifiers
                    foundDevice = True
        return DeviceInfo(
            identifiers=deviceIdentifiers,
            name=self._stringName if not foundDevice else None,
            manufacturer=(self._panelData.brand if self._panelData else "Generic") if not foundDevice else None,
            model=(self._panelData.name if self._panelData else None) if not foundDevice else None,
            via_device=(DOMAIN, self._sensorGroup.name) if (not foundDevice and self._sensorGroup) else None
        )

    async def async_select_option(self, option: str) -> None:
        targetRoofId = next((rid for rid, rname in self._db.listRoofs().items() if rname == option), None)
        if not targetRoofId:
            return
        roofObj = self._db.getRoof(targetRoofId)
        newData = self._configEntry.data.copy()
        newData[CONF_ROOF_NAME] = option
        if roofObj:
            if roofObj.tilt is not None:
                newData[CONF_TILT] = roofObj.tilt
            if roofObj.azimuth is not None:
                newData[CONF_AZIMUTH] = roofObj.azimuth
        self.hass.config_entries.async_update_entry(self._configEntry, data=newData)
        await self.hass.config_entries.async_reload(self._configEntry.entry_id)
