"""Select platform for Accurate Solar Forecast."""
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .variables.const import (
    DOMAIN, CONF_ROOF_NAME, CONF_STRING_NAME,
    CONF_REAL_PRODUCTION_SENSOR, CONF_TILT, CONF_AZIMUTH, CONF_SENSOR_GROUP_NAME
)
from .core.helpers import slugify

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """No select entities on the main entry — handled per subentry."""
    pass


async def async_setup_subentry(hass, configEntry, subentry, asyncAddEntities):
    """Set up select entities for a roof subentry."""
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

        entities = []
        for stringId, sDataRaw in stringsData.items():
            combinedData = dict(sDataRaw)
            combinedData[CONF_ROOF_NAME] = roofName
            entities.append(SolarStringRoofSelect(hass, combinedData, db, configEntry, subentry.subentry_id, stringId))

        if entities:
            asyncAddEntities(entities)
    except Exception as e:
        _LOGGER.exception(f"Error setting up select subentry: {e}")


class SolarStringRoofSelect(SelectEntity):
    """Select entity for choosing the roof of a solar string."""
    _attr_has_entity_name = True
    _attr_translation_key = "roof"
    _attr_icon = "mdi:home-roof"

    def __init__(self, hass, stringData, db, configEntry, subentryId, stringId):
        self.hass = hass
        self._configEntry = configEntry
        self._data = stringData
        self._stringId = stringId
        self._subentryId = subentryId
        self._db = db
        self._stringName = self._data.get(CONF_STRING_NAME)
        self._attr_unique_id = f"str_{self._stringId}_roof_select"
        
        # Get sensor group from subentry data
        subentry = next((s for s in configEntry.subentries if s.subentry_id == subentryId), None)
        sensorGroupId = subentry.data.get(CONF_SENSOR_GROUP_NAME, "") if subentry else ""
        self._sensorGroup = db.getSensorGroup(sensorGroupId) if sensorGroupId else None

        modelName = self._data.get("panel_model")
        self._panelData = db.data.get(slugify(modelName)) if db and db.data else None

    @property
    def options(self):
        """List names of all available roofs (subentries)."""
        return [
            sub.data.get(CONF_ROOF_NAME) 
            for sub in self._configEntry.subentries 
            if sub.data.get(CONF_ROOF_NAME)
        ]

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

    async def async_select_option(self, option: str) -> None:
        """Update the string's roof association by moving it between Subentries."""
        targetSubentry = next(
            (s for s in self._configEntry.subentries if s.data.get(CONF_ROOF_NAME) == option), 
            None
        )
        if not targetSubentry:
            _LOGGER.error(f"Target roof '{option}' not found in subentries")
            return
            
        currentSubentry = next(
            (s for s in self._configEntry.subentries if s.subentry_id == self._subentryId),
            None
        )
        if not currentSubentry:
            return

        # 1. Update Current Subentry: Remove the string
        currentStrings = dict(currentSubentry.data.get("strings", {}))
        stringData = currentStrings.pop(self._stringId, self._data)
        
        newCurrentData = dict(currentSubentry.data)
        newCurrentData["strings"] = currentStrings
        self.hass.config_entries.async_update_subentry(self._configEntry, currentSubentry.subentry_id, data=newCurrentData)

        # 2. Update Target Subentry: Add the string
        newTargetData = dict(targetSubentry.data)
        targetStrings = dict(newTargetData.get("strings", {}))
        
        # Update string geometry to match target roof
        stringData[CONF_ROOF_NAME] = option
        stringData[CONF_TILT] = newTargetData.get(CONF_TILT, 30.0)
        stringData[CONF_AZIMUTH] = newTargetData.get(CONF_AZIMUTH, 180.0)
        
        targetStrings[self._stringId] = stringData
        newTargetData["strings"] = targetStrings
        self.hass.config_entries.async_update_subentry(self._configEntry, targetSubentry.subentry_id, data=newTargetData)

        _LOGGER.warning(f"Moved string '{self._stringName}' from hub '{currentSubentry.title}' to '{targetSubentry.title}'")
