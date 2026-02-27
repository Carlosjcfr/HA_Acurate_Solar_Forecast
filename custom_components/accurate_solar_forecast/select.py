import logging
from .variables.const import DOMAIN, CONF_ROOF_NAME
from .core import SolarStringRoofSelect, slugify

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up the Accurate Solar Forecast select entities."""
    if CONF_ROOF_NAME in configEntry.data:
        db = hass.data[DOMAIN]["db"]
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
