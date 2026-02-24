from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry
from .const import DOMAIN, CONF_SENSOR_GROUP_NAME, CONF_ROOF_NAME
from .acurate_solar_sensor_db import AcurateSolarSensorDB
import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "select"]

async def async_setup_entry(hass: HomeAssistant, entry):
    # Cargar la DB y ponerla disponible globalmente
    if DOMAIN not in hass.data:
        db = AcurateSolarSensorDB(hass)
        await db.async_load()
        hass.data[DOMAIN] = {"db": db}
    else:
        # Ensure older entries get the DB reference if hot-reloading
        if "db" not in hass.data[DOMAIN]:
             db = AcurateSolarSensorDB(hass)
             await db.async_load()
             hass.data[DOMAIN]["db"] = db

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_setup(hass: HomeAssistant, config):
    # Inicialización global
    hass.data.setdefault(DOMAIN, {})
    if "db" not in hass.data[DOMAIN]:
        db = AcurateSolarSensorDB(hass)
        await db.async_load()
        hass.data[DOMAIN]["db"] = db
    return True

async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_remove_entry(hass: HomeAssistant, entry) -> None:
    """Handle removal of an entry."""
    # This is called when the user clicks 'Delete' on the Integration card.
    if DOMAIN in hass.data and "db" in hass.data[DOMAIN]:
        db = hass.data[DOMAIN]["db"]
        
        # Case A: Sensor Group
        if CONF_SENSOR_GROUP_NAME in entry.data:
            # The key in DB is usually name.lower().replace(" ", "_")
            group_name = entry.data[CONF_SENSOR_GROUP_NAME]
            group_id = group_name.lower().replace(" ", "_")
            _LOGGER.info(f"Removing Sensor Group from DB: {group_id}")
            result = db.delete_sensor_group(group_id)
            if result:
               await result
               
        # Case B: Roof Entry
        if CONF_ROOF_NAME in entry.data:
            roof_name = entry.data[CONF_ROOF_NAME]
            roof_id = roof_name.lower().replace(" ", "_") if roof_name else "default"
            _LOGGER.info(f"Removing Roof from DB: {roof_id}")
            result = db.delete_roof(roof_id)
            if result:
               await result
               
        # Case B: String (Strings are now devices under Roof config entries, handled by async_remove_config_entry_device)
        return

async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow user to remove a device via the UI and clean up the database."""
    if DOMAIN in hass.data and "db" in hass.data[DOMAIN]:
        db = hass.data[DOMAIN]["db"]
        
        # Check if this device is part of a Roof entry
        if CONF_ROOF_NAME in config_entry.data:
            roof_name = config_entry.data[CONF_ROOF_NAME]
            roof_id = roof_name.lower().replace(" ", "_") if roof_name else "default"
            
            # Find the string ID from the device identifiers
            # Typically a set of tuples like {(DOMAIN, "str_mppt1")}
            for domain, identifier in device_entry.identifiers:
                if domain == DOMAIN and isinstance(identifier, str) and identifier.startswith("str_"):
                    string_id = identifier[4:] # remove 'str_' prefix
                    _LOGGER.info(f"Removing string device '{string_id}' from roof '{roof_id}'")
                    
                    # Delete from our custom JSON DB
                    db.delete_string_from_roof(roof_id, string_id)
                    return True
                    
    # Return True to allow Home Assistant to complete the deletion of the device entity
    return True