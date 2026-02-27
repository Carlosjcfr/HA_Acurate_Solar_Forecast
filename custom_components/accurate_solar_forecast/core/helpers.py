from homeassistant.core import HomeAssistant
from typing import Any
from ..variables.const import DOMAIN

def slugify(text: str) -> str:
    """Convert a string to a slug (lowercase, replace spaces with underscores)."""
    if not text:
        return ""
    return str(text).lower().replace(" ", "_").strip()

def getSubentryMenuState(hass: HomeAssistant) -> dict[str, bool]:
    """Analyze the DB and return the integration's preparation state."""
    db = hass.data.get(DOMAIN, {}).get("db")
    
    if not db:
        return {
            "canAddString": False,
            "hasModels": False,
            "hasRoofs": False,
            "hasSensors": False
        }

    # db.data contains models
    # db.roofs contains roofs
    # db.sensor_groups contains sensor groups
    hasModels = len(db.data) > 0
    hasRoofs = len(db.roofs) > 0
    hasSensors = len(db.sensor_groups) > 0

    return {
        "canAddString": hasRoofs and hasSensors and hasModels,
        "hasModels": hasModels,
        "hasRoofs": hasRoofs,
        "hasSensors": hasSensors
    }
