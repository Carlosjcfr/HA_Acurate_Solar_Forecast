import logging
from .variables.const import DOMAIN, CONF_ROOF_NAME
from .core import SolarStringRoofSelect, slugify

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up the Accurate Solar Forecast select entities."""
    try:
        if CONF_ROOF_NAME not in configEntry.data:
            return
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            return
        roofName = configEntry.data.get(CONF_ROOF_NAME)
        roofId = slugify(roofName) if roofName else "default"
        roofStrings = db.getRoofStrings(roofId)
        
        entities = []
        for stringId, stringObj in roofStrings.items():
            combinedData = stringObj.to_dict()
            combinedData[CONF_ROOF_NAME] = roofName
            entities.append(SolarStringRoofSelect(hass, combinedData, db, configEntry, stringId, roofId))
            
        if entities:
            asyncAddEntities(entities)
    except Exception as e:
        _LOGGER.exception(f"Error setting up select platform: {e}")

