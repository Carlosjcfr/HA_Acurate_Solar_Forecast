import logging
from .variables.const import DOMAIN, CONF_ROOF_NAME
from .core import SolarStringRoofSelect, slugify

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Accurate Solar Forecast select entities."""
    if CONF_ROOF_NAME in config_entry.data:
        db = hass.data[DOMAIN]["db"]
        roof_name = config_entry.data.get(CONF_ROOF_NAME)
        roof_id = slugify(roof_name) if roof_name else "default"
        roof_strings = db.get_roof_strings(roof_id)
        
        entities = []
        for string_id, string_obj in roof_strings.items():
            combined_data = string_obj.to_dict()
            combined_data[CONF_ROOF_NAME] = roof_name
            entities.append(SolarStringRoofSelect(hass, combined_data, db, config_entry, string_id, roof_id))
            
        if entities:
            async_add_entities(entities)
