"""Sensor platform for Accurate Solar Forecast."""
import logging
from homeassistant.helpers import device_registry as dr
from .variables.const import *
from .core import (
    SolarStringSensor,
    SensorGroupVirtualSensor,
    SensorGroupCloudinessSensor,
    SolarStringPerformanceSensor,
    PVModelCountSensor,
    slugify
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up GLOBAL sensors (Diagnosis device, PV Library counter).
    
    Per-subentry sensors (roofs, strings, SGs) are handled by async_setup_subentry.
    """
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            _LOGGER.error("DATABASE NOT FOUND in hass.data")
            return

        deviceRegistry = dr.async_get(hass)
        mainEntryId = configEntry.entry_id

        _LOGGER.warning(f"[DIAG] sensor.async_setup_entry: Creating global entities for '{configEntry.title}' ({mainEntryId})")

        # Global Counter (PV Library) — always under main entry, no subentry
        deviceRegistry.async_get_or_create(
            config_entry_id=mainEntryId,
            identifiers={(DOMAIN, "pv_models_library")},
            name="Módulos Guardados",
            manufacturer="Accurate Solar Forecast",
            model="PV Library",
        )
        asyncAddEntities([PVModelCountSensor(hass, db)])

    except Exception as e:
        _LOGGER.exception(f"Error during sensor.async_setup_entry: {e}")


async def async_setup_subentry(hass, configEntry, subentry, asyncAddEntities):
    """Set up sensors for a specific subentry (roof or sensor group).
    
    Called by HA:
      - On startup: once per existing subentry
      - Dynamically: when a new subentry is created
    """
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            _LOGGER.error("DATABASE NOT FOUND in hass.data (subentry setup)")
            return

        subData = dict(subentry.data) if subentry.data else {}
        subId = subentry.subentry_id
        mainEntryId = configEntry.entry_id
        deviceRegistry = dr.async_get(hass)

        _LOGGER.warning(f"[DIAG] sensor.async_setup_subentry: title='{subentry.title}', id='{subId}', data={subData}")

        # --- ROOF SUBENTRY ---
        if CONF_ROOF_NAME in subData:
            _setupRoofEntities(hass, mainEntryId, subId, subData, db, deviceRegistry, asyncAddEntities)

        # --- SENSOR GROUP SUBENTRY ---
        elif CONF_SENSOR_GROUP_NAME in subData:
            _setupSensorGroupEntities(hass, mainEntryId, subId, subData, db, deviceRegistry, asyncAddEntities)

        # --- PV MODEL or MANAGEMENT subentry — no sensors needed ---
        else:
            _LOGGER.debug(f"Subentry '{subentry.title}' has no sensor entities to create (type: {subentry.subentry_type})")

    except Exception as e:
        _LOGGER.exception(f"Error during sensor.async_setup_subentry: {e}")


def _setupRoofEntities(hass, mainEntryId, subentryId, data, db, deviceRegistry, asyncAddEntities):
    """Create all devices and entities for a roof subentry."""
    roofName = data[CONF_ROOF_NAME]
    roofId = slugify(roofName)
    roofHubIdentifier = (DOMAIN, f"roof_{roofId}")

    # Register the Roof Hub device
    deviceRegistry.async_get_or_create(
        config_entry_id=mainEntryId,
        config_subentry_id=subentryId,
        identifiers={roofHubIdentifier},
        name=roofName,
        manufacturer="Accurate Solar Forecast",
        model="Roof Hub",
    )

    roofObj = db.getRoof(roofId)
    if not roofObj:
        _LOGGER.error(f"CRITICAL: Roof '{roofId}' NOT FOUND in DB. Available: {list(db.roofs.keys())}")
        return

    sensorGroupObj = db.getSensorGroupForRoof(roofId)
    _LOGGER.warning(f"[DIAG] Roof '{roofName}': {len(roofObj.strings)} strings, SG='{sensorGroupObj.name if sensorGroupObj else 'None'}'")

    entities = []

    # String entities
    for stringId, stringObj in roofObj.strings.items():
        sData = stringObj.to_dict()
        sData[CONF_ROOF_NAME] = roofName
        sData["_roof_hub_identifier"] = roofHubIdentifier

        # Register the string device under this subentry
        deviceRegistry.async_get_or_create(
            config_entry_id=mainEntryId,
            config_subentry_id=subentryId,
            identifiers={(DOMAIN, f"str_{slugify(stringObj.name)}")},
            name=stringObj.name,
            manufacturer="Accurate Solar Forecast",
            model=stringObj.panelModel,
            via_device=roofHubIdentifier,
        )

        entities.append(SolarStringSensor(hass, sData, db, sensorGroupObj))
        if stringObj.realProductionSensor:
            entities.append(SolarStringPerformanceSensor(hass, sData, db, sensorGroupObj))

    # Sensor group entities (Estado / Nubosidad) as child device of the roof
    if sensorGroupObj and roofObj.sensorGroupId:
        sgIdentifier = (DOMAIN, f"sg_{roofObj.sensorGroupId}")
        deviceRegistry.async_get_or_create(
            config_entry_id=mainEntryId,
            config_subentry_id=subentryId,
            identifiers={sgIdentifier},
            name=sensorGroupObj.name,
            manufacturer="Accurate Solar Forecast",
            model="Sensor Group",
            via_device=roofHubIdentifier,
        )
        entities.append(SensorGroupVirtualSensor(hass, db, roofObj.sensorGroupId, {sgIdentifier}))
        entities.append(SensorGroupCloudinessSensor(hass, db, roofObj.sensorGroupId, {sgIdentifier}))

    if entities:
        _LOGGER.warning(f"[DIAG] Adding {len(entities)} entities for roof '{roofName}' (subentry: {subentryId})")
        asyncAddEntities(entities)
    else:
        _LOGGER.warning(f"No entities created for roof '{roofName}' (0 strings in DB)")


def _setupSensorGroupEntities(hass, mainEntryId, subentryId, data, db, deviceRegistry, asyncAddEntities):
    """Create devices and entities for a standalone sensor group subentry."""
    groupName = data[CONF_SENSOR_GROUP_NAME]
    groupId = slugify(groupName)
    sgIdentifier = (DOMAIN, f"sg_{groupId}")

    deviceRegistry.async_get_or_create(
        config_entry_id=mainEntryId,
        config_subentry_id=subentryId,
        identifiers={sgIdentifier},
        name=groupName,
        manufacturer="Accurate Solar Forecast",
        model="Sensor Group",
    )

    asyncAddEntities([
        SensorGroupVirtualSensor(hass, db, groupId, {sgIdentifier}),
        SensorGroupCloudinessSensor(hass, db, groupId, {sgIdentifier}),
    ])
    _LOGGER.warning(f"[DIAG] Added SG entities for '{groupName}' (subentry: {subentryId})")
