from homeassistant.core import HomeAssistant
from typing import Any
from .const import DOMAIN, CONF_ROOF_NAME, CONF_SENSOR_GROUP_NAME

def slugify(text: str) -> str:
    """Convert a string to a slug (lowercase, replace spaces with underscores)."""
    if not text:
        return ""
    return str(text).lower().replace(" ", "_").strip()

def getSubentryMenuState(hass: HomeAssistant) -> dict[str, bool]:
    """Analyze the DB and HA subentries to return the integration's preparation state."""
    db = hass.data.get(DOMAIN, {}).get("db")
    
    state = {
        "canAddString": False,
        "hasModels": False,
        "hasRoofs": False,
        "hasSensors": False
    }

    if not db:
        return state

    # 1. Models and Sensor Groups come from DB
    state["hasModels"] = len(db.data) > 0
    state["hasSensors"] = len(db.sensor_groups) > 0

    # 2. Roofs (and potentially Sensor Groups too) can come from HA Subentries
    # We iterate through all entries of our domain
    for entry in hass.config_entries.async_entries(DOMAIN):
        # Count roofs in subentries
        for sub in entry.subentries:
            if not sub.data:
                continue
            if CONF_ROOF_NAME in sub.data:
                state["hasRoofs"] = True
            if CONF_SENSOR_GROUP_NAME in sub.data:
                state["hasSensors"] = True
        
        if state["hasRoofs"] and state["hasSensors"]:
            break

    state["canAddString"] = state["hasRoofs"] and state["hasSensors"] and state["hasModels"]
    return state
