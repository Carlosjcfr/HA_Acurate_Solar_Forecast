"""Accurate Solar Forecast Integration."""
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
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
        # Reset removal flag on startup
        hass.data.setdefault(DOMAIN, {})["is_removing_all"] = False
        await _ensureDbLoaded(hass)
    except Exception as e:
        _LOGGER.exception(f"Error during async_setup: {e}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry."""
    try:
        db = await _ensureDbLoaded(hass)
        
        # Reset removal flag if this is the main entry setup
        isMain = (CONF_ROOF_NAME not in entry.data and CONF_SENSOR_GROUP_NAME not in entry.data)
        if isMain:
            hass.data.setdefault(DOMAIN, {})["is_removing_all"] = False
            # Sync DB with current subentries — remove orphaned DB records
            await _syncDbWithSubentries(hass, entry, db)

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True
    except Exception as e:
        _LOGGER.exception(f"Exception during async_setup_entry: {e}")
        return False


async def _syncDbWithSubentries(hass: HomeAssistant, entry: ConfigEntry, db) -> None:
    """Remove DB records whose subentries no longer exist in HA."""
    try:
        subentries = getattr(entry, "subentries", None)
        if subentries is None:
            return  # subentries API not available — skip sync

        # Collect names of existing sensor groups and roofs from subentries
        activeGroupNames = set()
        activeRoofNames = set()
        
        # Handle both dict-like and iterable subentries
        if hasattr(subentries, 'items'):
            iterItems = ((sId, sObj) for sId, sObj in subentries.items())
        else:
            iterItems = ((getattr(s, 'subentry_id', idx), s) for idx, s in enumerate(subentries))
        
        for subId, sub in iterItems:
            subData = getattr(sub, "data", {}) or {}
            if CONF_SENSOR_GROUP_NAME in subData:
                activeGroupNames.add(slugify(subData[CONF_SENSOR_GROUP_NAME]))
            if CONF_ROOF_NAME in subData:
                activeRoofNames.add(slugify(subData[CONF_ROOF_NAME]))

        # Keep sensor groups that are referenced by active roofs
        for roofId in activeRoofNames:
            roof = db.getRoof(roofId)
            if roof and roof.sensorGroupId:
                activeGroupNames.add(roof.sensorGroupId)

        # Remove orphaned sensor groups from DB
        orphanGroups = [gId for gId in db.sensor_groups if gId not in activeGroupNames]
        for gId in orphanGroups:
            _LOGGER.info(f"DB sync: removing orphaned sensor group '{gId}'")
            await db.deleteSensorGroup(gId)

        # Remove orphaned roofs from DB
        orphanRoofs = [rId for rId in db.roofs if rId not in activeRoofNames]
        for rId in orphanRoofs:
            _LOGGER.info(f"DB sync: removing orphaned roof '{rId}'")
            await db.deleteRoof(rId)
    except Exception as e:
        _LOGGER.warning(f"Error syncing DB with subentries: {e}")


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
            # Try to load it just to be sure we can wipe the storage if needed
            db = AccurateSolarSensorDB(hass)
            await db.async_load()

        # Case A: Sensor Group Subentry
        if CONF_SENSOR_GROUP_NAME in entry.data:
            groupName = entry.data[CONF_SENSOR_GROUP_NAME]
            groupId = slugify(groupName)
            _LOGGER.info(f"Removing Sensor Group from DB: {groupId}")
            await db.deleteSensorGroup(groupId)

        # Case B: Roof Subentry
        elif CONF_ROOF_NAME in entry.data:
            roofName = entry.data[CONF_ROOF_NAME]
            roofId = slugify(roofName) if roofName else "default"
            _LOGGER.info(f"Removing Roof from DB: {roofId}")
            await db.deleteRoof(roofId)

        # Case C: Main Hub Entry (Everything else)
        else:
            _LOGGER.warning("Deep Clean: Removing Main Entry. Wiping entire JSON Database.")
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
