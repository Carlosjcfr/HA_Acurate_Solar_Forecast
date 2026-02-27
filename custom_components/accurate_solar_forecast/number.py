import logging
from .variables.const import DOMAIN, CONF_ROOF_NAME
from .core import SolarStringTiltNumber, SolarStringAzimuthNumber, slugify

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up number entities for solar strings."""
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            return

        # CASE A: direct subentry call
        if CONF_ROOF_NAME in configEntry.data:
            _setupRoofNumbers(hass, configEntry, db, asyncAddEntities, configEntry.data)
            return

        # CASE B: main entry — iterate subentries
        subentries = getattr(configEntry, "subentries", {}) or {}
        for subentryId, subentry in subentries.items():
            subData = subentry.data if hasattr(subentry, "data") else {}
            _setupRoofNumbers(hass, configEntry, db, asyncAddEntities, subData)

    except Exception as e:
        _LOGGER.exception(f"Error setting up number platform: {e}")


def _setupRoofNumbers(hass, configEntry, db, asyncAddEntities, data):
    if CONF_ROOF_NAME not in data:
        return
    try:
        roofName = data.get(CONF_ROOF_NAME)
        roofId = slugify(roofName) if roofName else "default"
        roofStrings = db.getRoofStrings(roofId)
        sensorGroupObj = db.getSensorGroupForRoof(roofId)
        entities = []
        for stringId, stringObj in roofStrings.items():
            combinedData = stringObj.to_dict()
            combinedData[CONF_ROOF_NAME] = roofName
            entities.append(SolarStringTiltNumber(hass, combinedData, db, configEntry, stringId, roofId, sensorGroupObj))
            entities.append(SolarStringAzimuthNumber(hass, combinedData, db, configEntry, stringId, roofId, sensorGroupObj))
        if entities:
            asyncAddEntities(entities)
    except Exception as e:
        _LOGGER.exception(f"Error setting up numbers for roof '{data.get(CONF_ROOF_NAME)}': {e}")
