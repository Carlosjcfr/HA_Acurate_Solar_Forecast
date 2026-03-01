"""Accurate Solar Forecast Integration."""
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntry
from .variables.const import DOMAIN, CONF_SENSOR_GROUP_NAME, CONF_ROOF_NAME
from .databases import AccurateSolarSensorDB
from .core import slugify
import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "select", "binary_sensor"]


async def _ensureDbLoaded(hass: HomeAssistant) -> AccurateSolarSensorDB:
    """Ensure the database is loaded and available in hass.data."""
    hass.data.setdefault(DOMAIN, {})
    if "db" not in hass.data[DOMAIN]:
        db = AccurateSolarSensorDB(hass)
        await db.async_load()
        hass.data[DOMAIN]["db"] = db
    return hass.data[DOMAIN]["db"]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Global initialization."""
    try:
        hass.data.setdefault(DOMAIN, {})["is_removing_all"] = False
        await _ensureDbLoaded(hass)
    except Exception as e:
        _LOGGER.exception(f"Error during async_setup: {e}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from the main config entry.
    
    This ONLY sets up global entities (Diagnosis, PV Library).
    Per-subentry entities (roofs, strings, SGs) are handled by async_setup_subentry.
    """
    try:
        db = await _ensureDbLoaded(hass)
        hass.data.setdefault(DOMAIN, {})["is_removing_all"] = False

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
    except Exception as e:
        _LOGGER.exception(f"Exception during async_setup_entry: {e}")
        return False


async def async_setup_subentry(hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry) -> bool:
    """Set up entities for a new or existing subentry (roof, sensor group, etc.).
    
    Called by HA:
      - On startup: once per existing subentry (after async_setup_entry)
      - Dynamically: when a new subentry is created via the config flow
    """
    try:
        subDataDict = dict(subentry.data) if subentry.data else {}
        _LOGGER.info(f"[DIAG] async_setup_subentry: title='{subentry.title}', id='{subentry.subentry_id}', type='{subentry.subentry_type}', data={subDataDict}")

        
        db = await _ensureDbLoaded(hass)

        await hass.config_entries.async_forward_subentry_setups(entry, subentry, PLATFORMS)
        return True
    except Exception as e:
        _LOGGER.exception(f"Error during async_setup_subentry: {e}")
        return False


async def async_unload_subentry(hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry) -> bool:
    """Unload entities for a subentry being removed."""
    try:
        _LOGGER.info(f"Unloading subentry: {subentry.title} ({subentry.subentry_id})")
        return await hass.config_entries.async_forward_subentry_unload(entry, subentry, PLATFORMS)
    except Exception as e:
        _LOGGER.exception(f"Error during async_unload_subentry: {e}")
        return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except Exception as e:
        _LOGGER.exception(f"Error during async_unload_entry: {e}")
        return True


async def async_remove_subentry(hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
    """Handle removal of a subentry dynamically without wiping the whole DB."""
    try:
        subData = dict(subentry.data) if subentry.data else {}
        subType = subentry.subentry_type
        
        _LOGGER.info(f"[DIAG] async_remove_subentry: title='{subentry.title}', id='{subentry.subentry_id}', type='{subType}', data={subData}")
        
        db = hass.data.get(DOMAIN, {}).get("db")
        if not db:
            db = AccurateSolarSensorDB(hass)
            await db.async_load()

        # Case A: Sensor Group
        if CONF_SENSOR_GROUP_NAME in subData:
            groupName = subData[CONF_SENSOR_GROUP_NAME]
            groupId = slugify(groupName)
            _LOGGER.warning(f"Removing Sensor Group from DB: {groupId}")
            await db.deleteSensorGroup(groupId)

        # Case B: Roof
        elif CONF_ROOF_NAME in subData:
            _LOGGER.info(f"Removing Roof subentry '{subentry.title}'. No DB cleanup needed (stored in subentry).")

        # Case C: Other subentries (Management, PV Model pills)
        else:
            _LOGGER.info(f"Removing UI subentry '{subType}'. No DB cleanup needed for this type.")

    except Exception as e:
        _LOGGER.exception(f"Error during async_remove_subentry: {e}")


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of the ENTIRE integration. This is a destructive clean wipe."""
    try:
        # SAFETY GUARD: If for some reason HA calls this for a subentry, DO NOT WIPE.
        if getattr(entry, "subentry_id", None):
            _LOGGER.info(f"async_remove_entry ignored for subentry {entry.subentry_id}")
            return

        # If we reach here, HA is deleting the main integration hub
        _LOGGER.warning("CRITICAL: Main integration entry is being removed. Performing FULL WIPE of the JSON database.")
        
        db = hass.data.get(DOMAIN, {}).get("db")
        if not db:
            db = AccurateSolarSensorDB(hass)
            await db.async_load()
            
        await db.async_clear()
        _LOGGER.warning("Full Database Wipe completed. All solar data (roofs, groups, models) has been deleted.")
            
    except Exception as e:
        _LOGGER.exception(f"Error during async_remove_entry (wipe): {e}")


async def async_remove_config_entry_device(
    hass: HomeAssistant, configEntry: ConfigEntry, deviceEntry: DeviceEntry
) -> bool:
    """Allow user to remove a device via the UI and clean up the database."""
    try:
        # Check all subentries for the device being removed
        for sub in configEntry.subentries:
            subData = dict(sub.data)
            if "strings" not in subData:
                continue

            for domain, identifier in deviceEntry.identifiers:
                if domain == DOMAIN and isinstance(identifier, str) and identifier.startswith("str_"):
                    # This identifier is 'str_<slugified_name>'
                    foundId = None
                    for sid in subData["strings"]:
                        if identifier == f"str_{sid}":
                           foundId = sid
                           break
                    
                    if foundId:
                        _LOGGER.warning(f"User deleted string device '{foundId}' from roof subentry '{sub.title}'. Removing from data.")
                        newStrings = dict(subData["strings"])
                        newStrings.pop(foundId, None)
                        subData["strings"] = newStrings
                        
                        hass.config_entries.async_update_subentry(configEntry, sub.subentry_id, data=subData)
                        await hass.config_entries.async_reload_subentry(sub)
                        return True
    except Exception as e:
        _LOGGER.exception(f"Error removing device: {e}")

    return True
