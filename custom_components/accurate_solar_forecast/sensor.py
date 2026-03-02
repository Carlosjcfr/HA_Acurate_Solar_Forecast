"""Sensor platform for Accurate Solar Forecast."""
import logging
from homeassistant.helpers import device_registry as dr
from .const import *
from .engine import (
    SolarStringSensor,
    SensorGroupVirtualSensor,
    SensorGroupCloudinessSensor,
    SolarStringPerformanceSensor,
    PVModelCountSensor
)
from .helpers import slugify

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

        _LOGGER.info(f"[DIAG] sensor.async_setup_entry: Creating global entities for '{configEntry.title}' ({mainEntryId})")

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

        _LOGGER.info(f"[DIAG] sensor.async_setup_subentry: title='{subentry.title}', id='{subId}', data={subData}")

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
    roofName = data.get(CONF_ROOF_NAME, "?")
    roofId = slugify(roofName)
    roofHubIdentifier = (DOMAIN, f"roof_{roofId}")

    _LOGGER.info(f"[DIAG-ROOF] ── START setup for roof='{roofName}' (id='{roofId}') ──")
    _LOGGER.info(f"[DIAG-ROOF]   subentry_id='{subentryId}', main_entry_id='{mainEntryId}'")

    # ── STEP 1: Register the Roof Hub device ──
    # REMOVED as per user request (wants strings directly under subentry)
    _LOGGER.info(f"[DIAG-ROOF] skipped Roof Hub device registration (Direct Subentry mode)")

    # ── STEP 2: Use Subentry Data for geometry ──
    _LOGGER.info(f"[DIAG-ROOF]   Data from Subentry: {data}")
    tilt = data.get(CONF_TILT, 30.0)
    azimuth = data.get(CONF_AZIMUTH, 180.0)
    sensorGroupId = data.get(CONF_SENSOR_GROUP_NAME, "")
    
    _LOGGER.info(f"[DIAG-ROOF]   [OK] Data from Subentry: tilt={tilt}, az={azimuth}, group='{sensorGroupId}'")

    # ── STEP 3: Fetch sensor group ──
    sensorGroupObj = db.getSensorGroup(sensorGroupId) if sensorGroupId else None
    if sensorGroupObj:
        _LOGGER.info(f"[DIAG-ROOF]   [OK] Sensor group resolved: '{sensorGroupObj.name}' (id='{sensorGroupId}')")
    else:
        if sensorGroupId:
            _LOGGER.warning(
                f"[DIAG-ROOF]   [WARN] SensorGroupId='{sensorGroupId}' is set on roof "
                f"but NOT FOUND in DB. Available groups: {list(db.sensor_groups.keys())}. "
                f"String sensors will run in DEGRADED mode (no irradiance data)."
            )
        else:
            _LOGGER.warning(
                f"[DIAG-ROOF]   [WARN] Roof '{roofName}' has no sensor group assigned. "
                f"String sensors will run in DEGRADED mode (no irradiance data)."
            )

    # ── STEP 4: Create string entities ──
    stringsData = data.get("strings", {})
    stringCount = len(stringsData)
    _LOGGER.info(f"[DIAG-ROOF]   Strings found in Subentry for this roof: {stringCount} → {list(stringsData.keys())}")

    entities = []
    for stringId, sDataRaw in stringsData.items():
        stringName = sDataRaw.get(CONF_STRING_NAME, stringId)
        panelModelName = sDataRaw.get(CONF_PANEL_MODEL, "Unknown")
        
        _LOGGER.info(f"[DIAG-ROOF]   Processing string: id='{stringId}', name='{stringName}', model='{panelModelName}'")

        # Validate the panel model exists in the PV library
        modelId = slugify(panelModelName)
        panelModel = db.data.get(modelId)
        if not panelModel:
            _LOGGER.warning(
                f"[DIAG-ROOF]   [WARN] String '{stringName}': panel model '{panelModelName}' "
                f"(id='{modelId}') NOT FOUND in PV library. Available models: {list(db.data.keys())}. "
                f"Power calculation will use defaults."
            )

        sData = dict(sDataRaw)
        sData[CONF_ROOF_NAME] = roofName
        sData["_roof_hub_identifier"] = roofHubIdentifier

        # Register device for this string
        try:
            deviceRegistry.async_get_or_create(
                config_entry_id=mainEntryId,
                config_subentry_id=subentryId,
                identifiers={(DOMAIN, f"str_{slugify(stringName)}")},
                name=stringName,
                manufacturer="Accurate Solar Forecast",
                model=panelModelName,
            )
            _LOGGER.info(f"[DIAG-ROOF]   [OK] Device registered for string '{stringName}'")
        except Exception as e:
            _LOGGER.error(f"[DIAG-ROOF]   [FAIL] Could not register device for string '{stringName}': {e}", exc_info=True)

        entities.append(SolarStringSensor(hass, sData, db, sensorGroupObj))
        _LOGGER.info(f"[DIAG-ROOF]   [OK] SolarStringSensor created for '{stringName}'")

        if sData.get(CONF_REAL_PRODUCTION_SENSOR):
            entities.append(SolarStringPerformanceSensor(hass, sData, db, sensorGroupObj))
            _LOGGER.info(f"[DIAG-ROOF]   [OK] SolarStringPerformanceSensor created for '{stringName}'")

    # ── STEP 5: Create sensor group entities (Estado / Nubosidad) ──
    if sensorGroupObj and sensorGroupId:
        sgIdentifier = (DOMAIN, f"sg_{sensorGroupId}")
        try:
            deviceRegistry.async_get_or_create(
                config_entry_id=mainEntryId,
                config_subentry_id=subentryId,
                identifiers={sgIdentifier},
                name=sensorGroupObj.name,
                manufacturer="Accurate Solar Forecast",
                model="Sensor Group",
            )
            _LOGGER.info(f"[DIAG-ROOF]   [OK] Sensor Group device registered: '{sensorGroupObj.name}'")
        except Exception as e:
            _LOGGER.error(f"[DIAG-ROOF]   [FAIL] Could not register Sensor Group device: {e}", exc_info=True)

        entities.append(SensorGroupVirtualSensor(hass, db, sensorGroupId, {sgIdentifier}))
        entities.append(SensorGroupCloudinessSensor(hass, db, sensorGroupId, {sgIdentifier}))
        _LOGGER.info(f"[DIAG-ROOF]   [OK] SensorGroup status + cloudiness sensors added")
    else:
        _LOGGER.info(f"[DIAG-ROOF]   Skipping SG device/sensors (no sensor group linked to this roof)")

    # ── STEP 6: Register all entities ──
    if entities:
        asyncAddEntities(entities)
        _LOGGER.info(f"[DIAG-ROOF]   [OK] asyncAddEntities called with {len(entities)} entities for roof '{roofName}' ✓")
    else:
        _LOGGER.warning(
            f"[DIAG-ROOF]   [WARN] No entities generated for roof '{roofName}'. "
            f"Reason: 0 strings in Subentry for this roof."
        )

    _LOGGER.info(f"[DIAG-ROOF] ── END setup for roof='{roofName}' (total entities: {len(entities)}) ──")


def _setupSensorGroupEntities(hass, mainEntryId, subentryId, data, db, deviceRegistry, asyncAddEntities):
    """Create devices and entities for a standalone sensor group subentry (e.g., Pill: Grupo Sensores)."""
    groupName = data.get(CONF_SENSOR_GROUP_NAME, "?")
    groupId = slugify(groupName)
    sgIdentifier = (DOMAIN, f"sg_{groupId}")

    _LOGGER.warning(f"[DIAG-SG] ── START setup for sensor group='{groupName}' (id='{groupId}') ──")
    _LOGGER.info(f"[DIAG-SG]   subentry_id='{subentryId}', main_entry_id='{mainEntryId}'")

    # 1. Validate group exists in DB
    groupObj = db.getSensorGroup(groupId)
    if not groupObj:
        _LOGGER.warning(
            f"[DIAG-SG]   [FAIL] Sensor group '{groupId}' NOT FOUND in DB. "
            f"Available groups: {list(db.sensor_groups.keys())}. "
            f"Check if the JSON database was accidentally wiped or if the name contains special characters."
        )
        return

    _LOGGER.info(f"[DIAG-SG]   [OK] Group found in DB: refSensor='{groupObj.refSensor}', tempSensor='{groupObj.tempSensor}'")

    # 2. Register the Sensor Group Device
    try:
        deviceRegistry.async_get_or_create(
            config_entry_id=mainEntryId,
            config_subentry_id=subentryId,
            identifiers={sgIdentifier},
            name=groupName,
            manufacturer="Accurate Solar Forecast",
            model="Sensor Group",
        )
        _LOGGER.info(f"[DIAG-SG]   [OK] Sensor Group device registered: {sgIdentifier}")
    except Exception as e:
        _LOGGER.error(f"[DIAG-SG]   [FAIL] Could not register Sensor Group device: {e}", exc_info=True)
        return

    # 3. Create and add entities
    entities = [
        SensorGroupVirtualSensor(hass, db, groupId, {sgIdentifier}),
        SensorGroupCloudinessSensor(hass, db, groupId, {sgIdentifier}),
    ]

    if entities:
        asyncAddEntities(entities)
        _LOGGER.warning(f"[DIAG-SG]   [OK] asyncAddEntities called with {len(entities)} entities for '{groupName}' ✓")
    
    _LOGGER.warning(f"[DIAG-SG] ── END setup for sensor group='{groupName}' ──")

