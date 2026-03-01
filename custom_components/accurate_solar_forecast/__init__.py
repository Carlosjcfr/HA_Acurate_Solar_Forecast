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


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry (main or subentry)."""
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            db = AccurateSolarSensorDB(hass)
            await db.async_load()

        subId = getattr(entry, "subentry_id", None)
        subType = getattr(entry, "subentry_type", "main")
        isSubentry = subId is not None

        _LOGGER.info(f"async_remove_entry: entry_id='{entry.entry_id}', subentry_id='{subId}', type='{subType}', data={dict(entry.data)}")

        # Case A: Sensor Group Subentry (or deleted from Management)
        if CONF_SENSOR_GROUP_NAME in entry.data:
            groupName = entry.data[CONF_SENSOR_GROUP_NAME]
            groupId = slugify(groupName)
            _LOGGER.info(f"Removing Sensor Group from DB: {groupId} (subentry: {subId})")
            await db.deleteSensorGroup(groupId)

        # Case B: Roof Subentry
        elif CONF_ROOF_NAME in entry.data:
            roofName = entry.data[CONF_ROOF_NAME]
            roofId = slugify(roofName) if roofName else "default"
            _LOGGER.info(f"Removing Roof from DB: {roofId} (subentry: {subId})")
            await db.deleteRoof(roofId)

        # Case C: PV Model Subentry (Specific Cleanup)
        elif subType == "pv_model" or "panel_model" in entry.data:
            _LOGGER.info(f"Removing PV Model Subentry UI element (subentry: {subId}). Note: Specific models in JSON are preserved unless manually deleted in Management.")

        # Case D: Management / Other UI-only subentries
        elif isSubentry:
            _LOGGER.info(f"Removing UI-only subentry '{subType}' (id: {subId}). No DB changes required.")

        # Case E: Main Hub Entry -> FULL WIPE
        else:
            _LOGGER.warning("CRITICAL: Removing Main Entry. Performing Deep Clean of the entire JSON Database.")
            await db.async_clear()
            
    except Exception as e:
        _LOGGER.exception(f"Error removing entry from DB: {e}")


async def async_remove_config_entry_device(
    hass: HomeAssistant, configEntry: ConfigEntry, deviceEntry: DeviceEntry
) -> bool:
    """Allow user to remove a device via the UI and clean up the database."""
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            return True

        if CONF_ROOF_NAME in configEntry.data:
            roofName = configEntry.data[CONF_ROOF_NAME]
            roofId = slugify(roofName) if roofName else "default"

            for domain, identifier in deviceEntry.identifiers:
                if domain == DOMAIN and isinstance(identifier, str) and identifier.startswith("str_"):
                    stringId = identifier[4:]
                    _LOGGER.info(f"Removing string device '{stringId}' from roof '{roofId}'")
                    await db.deleteStringFromRoof(roofId, stringId)
                    return True
    except Exception as e:
        _LOGGER.exception(f"Error removing device: {e}")

    return True
