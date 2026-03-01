"""Number platform for Accurate Solar Forecast."""
import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .variables.const import (
    DOMAIN, CONF_ROOF_NAME, CONF_STRING_NAME,
    CONF_REAL_PRODUCTION_SENSOR, CONF_PANEL_MODEL,
    CONF_TILT, CONF_AZIMUTH
)
from .core.helpers import slugify

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """No number entities on the main entry — handled per subentry."""
    pass


async def async_setup_subentry(hass, configEntry, subentry, asyncAddEntities):
    """Set up number entities for a roof subentry."""
    try:
        subData = dict(subentry.data) if subentry.data else {}
        if CONF_ROOF_NAME not in subData:
            return

        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            return

        roofName = subData[CONF_ROOF_NAME]
        stringsData = subData.get("strings", {})
        
        # Get sensor group from subentry data
        sensorGroupId = subData.get("selected_sensor_group", "")
        sensorGroupObj = db.getSensorGroup(sensorGroupId) if sensorGroupId else None

        entities = []
        for stringId, sDataRaw in stringsData.items():
            combinedData = dict(sDataRaw)
            combinedData[CONF_ROOF_NAME] = roofName
            
            entities.append(SolarStringTiltNumber(hass, combinedData, db, configEntry, subentry.subentry_id, stringId, sensorGroupObj))
            entities.append(SolarStringAzimuthNumber(hass, combinedData, db, configEntry, subentry.subentry_id, stringId, sensorGroupObj))

        if entities:
            asyncAddEntities(entities)
    except Exception as e:
        _LOGGER.exception(f"Error setting up number subentry: {e}")


# ---------------------------------------------------------------------------
# Entity classes
# ---------------------------------------------------------------------------

class SolarStringNumberEntity(NumberEntity):
    """Base class for Solar String numbers."""

    def __init__(self, hass, stringData, db, configEntry, subentryId, stringId, sensorGroupData):
        self.hass = hass
        self._data = stringData
        self._db = db
        self._configEntry = configEntry
        self._stringId = stringId
        self._subentryId = subentryId
        self._sensorGroup = sensorGroupData
        self._stringName = self._data.get(CONF_STRING_NAME)
        self._attr_has_entity_name = True
        self._debounceUnsub = None
        self._key = None
        modelName = self._data.get(CONF_PANEL_MODEL)
        self._panelData = db.data.get(slugify(modelName)) if db and db.data else None

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
        
        # Use the name of the root subentry hub as via_device
        subentry = next((s for s in self._configEntry.subentries if s.subentry_id == self._subentryId), None)
        roofName = subentry.data.get(CONF_ROOF_NAME) if subentry else None
        viaId = (DOMAIN, f"roof_{slugify(roofName)}") if roofName else None

        return DeviceInfo(
            identifiers=deviceIdentifiers,
            name=self._stringName if not foundDevice else None,
            manufacturer=(self._panelData.brand if self._panelData else "Generic") if not foundDevice else None,
            model=(self._panelData.name if self._panelData else None) if not foundDevice else None,
            via_device=viaId if not foundDevice else None
        )

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
        if self._debounceUnsub:
            self._debounceUnsub()

        async def _performUpdate(_now):
            # 1. Fetch current subentry state
            subentry = next((s for s in self._configEntry.subentries if s.subentry_id == self._subentryId), None)
            if not subentry:
                return
                
            # 2. Update the specific string data
            newData = dict(subentry.data)
            strings = dict(newData.get("strings", {}))
            
            if self._stringId in strings:
                stringData = dict(strings[self._stringId])
                stringData[self._key] = value
                strings[self._stringId] = stringData
                newData["strings"] = strings
                
                # 3. Save back to Subentry
                _LOGGER.info(f"Debounced update for string '{self._stringName}': {self._key}={value}")
                self.hass.config_entries.async_update_subentry(self._configEntry, subentry.subentry_id, data=newData)
                
                # 4. Reload to reflect change in engine
                await self.hass.config_entries.async_reload_subentry(subentry)

        self._debounceUnsub = async_call_later(self.hass, 2, _performUpdate)


class SolarStringTiltNumber(SolarStringNumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 90
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:angle-acute"

    def __init__(self, hass, stringData, db, configEntry, subentryId, stringId, sensorGroupData):
        super().__init__(hass, stringData, db, configEntry, subentryId, stringId, sensorGroupData)
        self._attr_name = "Inclinación"
        self._attr_unique_id = f"str_{self._stringId}_tilt"
        self._attr_native_value = self._data.get(CONF_TILT, 0)
        self._key = CONF_TILT


class SolarStringAzimuthNumber(SolarStringNumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 360
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "°"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:compass"

    def __init__(self, hass, stringData, db, configEntry, subentryId, stringId, sensorGroupData):
        super().__init__(hass, stringData, db, configEntry, subentryId, stringId, sensorGroupData)
        self._attr_name = "Orientación"
        self._attr_unique_id = f"str_{self._stringId}_azimuth"
        self._attr_native_value = self._data.get(CONF_AZIMUTH, 180)
        self._key = CONF_AZIMUTH
