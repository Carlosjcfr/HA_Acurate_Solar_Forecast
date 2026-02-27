from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry
from .variables.const import DOMAIN, CONF_SENSOR_GROUP_NAME, CONF_ROOF_NAME
from .databases import AccurateSolarSensorDB
from .core import slugify
import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "select", "binary_sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Cargar la DB y ponerla disponible globalmente
    if DOMAIN not in hass.data:
        db = AccurateSolarSensorDB(hass)
        await db.async_load()
        hass.data[DOMAIN] = {"db": db}
    else:
        # Ensure older entries get the DB reference if hot-reloading
        if "db" not in hass.data[DOMAIN]:
             db = AccurateSolarSensorDB(hass)
             await db.async_load()
             hass.data[DOMAIN]["db"] = db

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_setup(hass: HomeAssistant, config: dict[str, Any]):
    # Inicialización global
    hass.data.setdefault(DOMAIN, {})
    if "db" not in hass.data[DOMAIN]:
        db = AccurateSolarSensorDB(hass)
        await db.async_load()
        hass.data[DOMAIN]["db"] = db
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    # This is called when the user clicks 'Delete' on the Integration card.
    if DOMAIN in hass.data and "db" in hass.data[DOMAIN]:
        db = hass.data[DOMAIN]["db"]
        
        # Case A: Sensor Group
        if CONF_SENSOR_GROUP_NAME in entry.data:
            # The key in DB is usually name.lower().replace(" ", "_")
            groupName = entry.data[CONF_SENSOR_GROUP_NAME]
            groupId = slugify(groupName)
            _LOGGER.info(f"Removing Sensor Group from DB: {groupId}")
            result = db.deleteSensorGroup(groupId)
            if result:
               await result
               
        # Case B: Roof Entry
        if CONF_ROOF_NAME in entry.data:
            roofName = entry.data[CONF_ROOF_NAME]
            roofId = slugify(roofName) if roofName else "default"
            _LOGGER.info(f"Removing Roof from DB: {roofId}")
            result = db.deleteRoof(roofId)
            if result:
               await result
               
        # Case B: String (Strings are now devices under Roof config entries, handled by async_remove_config_entry_device)
        return

async def async_remove_config_entry_device(
    hass: HomeAssistant, configEntry: ConfigEntry, deviceEntry: DeviceEntry
) -> bool:
    """Allow user to remove a device via the UI and clean up the database."""
    if DOMAIN in hass.data and "db" in hass.data[DOMAIN]:
        db = hass.data[DOMAIN]["db"]
        
        # Check if this device is part of a Roof entry
        if CONF_ROOF_NAME in configEntry.data:
            roofName = configEntry.data[CONF_ROOF_NAME]
            roofId = slugify(roofName) if roofName else "default"
            
            # Find the string ID from the device identifiers
            # Typically a set of tuples like {(DOMAIN, "str_mppt1")}
            for domain, identifier in deviceEntry.identifiers:
                if domain == DOMAIN and isinstance(identifier, str) and identifier.startswith("str_"):
                    stringId = identifier[4:] # remove 'str_' prefix
                    _LOGGER.info(f"Removing string device '{stringId}' from roof '{roofId}'")
                    
                    # Delete from our custom JSON DB
                    db.deleteStringFromRoof(roofId, stringId)
                    return True
                    
    # Return True to allow Home Assistant to complete the deletion of the device entity
    return True
