from ..variables.const import DOMAIN

def slugify(text: str) -> str:
    """Convert a string to a slug (lowercase, replace spaces with underscores)."""
    if not text:
        return ""
    return str(text).lower().replace(" ", "_").strip()

def get_subentry_menu_state(hass):
    """Analiza la DB y devuelve el estado de preparación de la integración."""
    db = hass.data.get(DOMAIN, {}).get("db")
    
    if not db:
        return {
            "can_add_string": False,
            "has_models": False,
            "has_roofs": False,
            "has_sensors": False
        }

    # db.data contains models
    # db.roofs contains roofs
    # db.sensor_groups contains sensor groups
    has_models = len(db.data) > 0
    has_roofs = len(db.roofs) > 0
    has_sensors = len(db.sensor_groups) > 0

    return {
        "can_add_string": has_roofs and has_sensors and has_models,
        "has_models": has_models,
        "has_roofs": has_roofs,
        "has_sensors": has_sensors
    }
