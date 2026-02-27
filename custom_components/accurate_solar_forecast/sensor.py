import logging
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .variables.const import *
from .core import (
    SolarStringSensor,
    SensorGroupVirtualSensor,
    SensorGroupCloudinessSensor,
    SolarStringPerformanceSensor,
    AccurateSolarSensorDBSensor,
    PVModelCountSensor,
    slugify
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up Accurate Solar Forecast sensors.

    HA calls this once per config entry (main + subentries).
    We handle both cases:
      - Main entry  → create overview + iterate subentries for all entities
      - Subentry    → handled via main entry iteration (this path is a no-op)
    """
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            return

        isSubentry = (
            CONF_SENSOR_GROUP_NAME in configEntry.data
            or CONF_ROOF_NAME in configEntry.data
        )

        # ─────────────────────────────────────────────────────────────
        # CASE A: Called for a specific SUBENTRY
        # In HA's subentry model this path is also reached:
        # process the subentry data directly (belt-and-suspenders).
        # ─────────────────────────────────────────────────────────────
        if isSubentry:
            _setupSensorGroupEntry(hass, configEntry, db, asyncAddEntities)
            _setupRoofEntry(hass, configEntry, db, asyncAddEntities)
            return

        # ─────────────────────────────────────────────────────────────
        # CASE B: Called for the MAIN entry
        # 1. Create "Módulos Guardados" overview device + sensor
        # 2. Iterate over all subentries and set up their entities
        # ─────────────────────────────────────────────────────────────
        deviceRegistry = dr.async_get(hass)

        # "Módulos Guardados" service device
        deviceRegistry.async_get_or_create(
            config_entry_id=configEntry.entry_id,
            identifiers={(DOMAIN, "pv_models_library")},
            name="Módulos Guardados",
            manufacturer="Accurate Solar Forecast",
            model="PV Library",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        asyncAddEntities([PVModelCountSensor(hass, db)])

        # Iterate subentries — set up sensor groups and roofs
        subentries = getattr(configEntry, "subentries", {}) or {}
        for subentryId, subentry in subentries.items():
            subData = subentry.data if hasattr(subentry, "data") else {}
            _setupSensorGroupEntry(hass, configEntry, db, asyncAddEntities, subData)
            _setupRoofEntry(hass, configEntry, db, asyncAddEntities, subData)

    except Exception as e:
        _LOGGER.exception(f"Error setting up sensor platform: {e}")


def _setupSensorGroupEntry(hass, configEntry, db, asyncAddEntities, data=None):
    """Create sensor group service device and virtual sensors."""
    if data is None:
        data = configEntry.data
    if CONF_SENSOR_GROUP_NAME not in data:
        return

    try:
        groupName = data.get(CONF_SENSOR_GROUP_NAME, "Sensor Group")
        groupId = slugify(groupName)
        deviceRegistry = dr.async_get(hass)

        sgIdentifier = (DOMAIN, f"sg_{groupId}")
        deviceRegistry.async_get_or_create(
            config_entry_id=configEntry.entry_id,
            identifiers={sgIdentifier},
            name=groupName,
            manufacturer="Accurate Solar Forecast",
            model="Sensor Group",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        # Build a minimal proxy so VirtualSensor / CloudinessSensor can read data
        class _SubentryProxy:
            entry_id = configEntry.entry_id

        proxy = _SubentryProxy()
        proxy.data = data

        asyncAddEntities([
            SensorGroupVirtualSensor(hass, proxy, {sgIdentifier}),
            SensorGroupCloudinessSensor(hass, proxy, {sgIdentifier}),
        ])
    except Exception as e:
        _LOGGER.exception(f"Error setting up sensor group '{data.get(CONF_SENSOR_GROUP_NAME)}': {e}")


def _setupRoofEntry(hass, configEntry, db, asyncAddEntities, data=None):
    """Create roof hub device and string sensors as child devices."""
    if data is None:
        data = configEntry.data
    if CONF_ROOF_NAME not in data:
        return

    try:
        roofName = data.get(CONF_ROOF_NAME)
        roofId = slugify(roofName) if roofName else "default"
        roofStrings = db.getRoofStrings(roofId)
        deviceRegistry = dr.async_get(hass)

        sensorGroupObj = db.getSensorGroupForRoof(roofId)
        if not sensorGroupObj:
            _LOGGER.warning(
                f"Roof '{roofId}' has no sensor group assigned — "
                "strings registered in degraded mode."
            )

        # Roof hub device
        roofHubIdentifier = (DOMAIN, f"roof_{roofId}")
        deviceRegistry.async_get_or_create(
            config_entry_id=configEntry.entry_id,
            identifiers={roofHubIdentifier},
            name=roofName,
            manufacturer="Accurate Solar Forecast",
            model="Roof Hub",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        entities = []
        for stringId, stringObj in roofStrings.items():
            combinedData = stringObj.to_dict()
            combinedData[CONF_ROOF_NAME] = roofName
            combinedData["_roof_hub_identifier"] = roofHubIdentifier

            entities.append(SolarStringSensor(hass, combinedData, db, sensorGroupObj))
            if stringObj.realProductionSensor:
                entities.append(SolarStringPerformanceSensor(hass, combinedData, db, sensorGroupObj))

        if entities:
            asyncAddEntities(entities, update_before_add=True)

        if not roofStrings:
            _LOGGER.warning(f"Roof '{roofId}' has no strings configured.")

    except Exception as e:
        _LOGGER.exception(f"Error setting up roof '{data.get(CONF_ROOF_NAME)}': {e}")
