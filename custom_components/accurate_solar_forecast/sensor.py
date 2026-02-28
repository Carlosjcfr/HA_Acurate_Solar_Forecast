import logging
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
    """Set up Accurate Solar Forecast sensors."""
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
<<<<<<< HEAD
=======
            _LOGGER.error("DB not found in hass.data — skipping sensor.py setup")
>>>>>>> 58f268e90c2b0be8660805ca12469610abf73521
            return

        deviceRegistry = dr.async_get(hass)
        
        # Collect subentries to map names -> subentry IDs for UI grouping
        subentries = getattr(configEntry, "subentries", {}) or {}
        subentryMap = {} # key: slugified name, value: entry_id
        for sId, sObj in subentries.items():
            name = sObj.data.get(CONF_ROOF_NAME) or sObj.data.get(CONF_SENSOR_GROUP_NAME)
            if name:
                subentryMap[slugify(name)] = sId

<<<<<<< HEAD
        # 1. MAIN ENTRY OVERVIEW (counter)
        if not (CONF_SENSOR_GROUP_NAME in configEntry.data or CONF_ROOF_NAME in configEntry.data):
             deviceRegistry.async_get_or_create(
=======
        # ── CASE MAIN ENTRY ──────────────────────────────────────────
        # If this is the main entry, it manages the library and
        # delegates creation of all current subentries.
        if CONF_SENSOR_GROUP_NAME not in configEntry.data and CONF_ROOF_NAME not in configEntry.data:
            _LOGGER.debug("Setting up main entry devices")
            
            # PV Library device (always flat under main entry)
            deviceRegistry.async_get_or_create(
>>>>>>> 58f268e90c2b0be8660805ca12469610abf73521
                config_entry_id=configEntry.entry_id,
                identifiers={(DOMAIN, "pv_models_library")},
                name="Módulos Guardados",
                manufacturer="Accurate Solar Forecast",
                model="PV Library",
                entry_type=dr.DeviceEntryType.SERVICE,
            )
<<<<<<< HEAD
             asyncAddEntities([PVModelCountSensor(hass, db)])

        # 2. SENSOR GROUPS (Global or Subentry)
        for groupId, sg in db.sensor_groups.items():
            _setupSensorGroup(hass, configEntry.entry_id, subentryMap.get(groupId), sg, deviceRegistry, asyncAddEntities)

        # 3. ROOFS + STRINGS
        for roofId, roof in db.roofs.items():
            _setupRoof(hass, configEntry.entry_id, subentryMap.get(roofId), roof, db, deviceRegistry, asyncAddEntities)

    except Exception as e:
        _LOGGER.exception(f"Error during sensor platform setup: {e}")


def _setupSensorGroup(hass, entryId, subentryId, sg, dr, asyncAddEntities):
    sgIdentifier = (DOMAIN, f"sg_{slugify(sg.name)}")
    dr.async_get_or_create(
        config_entry_id=entryId,
        config_subentry_id=subentryId,
        identifiers={sgIdentifier},
        name=sg.name,
        manufacturer="Accurate Solar Forecast",
        model="Sensor Group",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    # Entity logic
    class _P: entry_id = entryId; data = sg.to_dict()
    asyncAddEntities([
        SensorGroupVirtualSensor(hass, _P(), {sgIdentifier}),
        SensorGroupCloudinessSensor(hass, _P(), {sgIdentifier}),
    ])


def _setupRoof(hass, entryId, subentryId, roof, db, dr, asyncAddEntities):
    roofId = slugify(roof.name)
    roofHubIdentifier = (DOMAIN, f"roof_{roofId}")
    
    dr.async_get_or_create(
        config_entry_id=entryId,
        config_subentry_id=subentryId,
        identifiers={roofHubIdentifier},
        name=roof.name,
        manufacturer="Accurate Solar Forecast",
        model="Roof Hub",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    sensorGroupObj = db.getSensorGroupForRoof(roofId)
    entities = []
    for stringId, stringObj in roof.strings.items():
        sData = stringObj.to_dict()
        sData[CONF_ROOF_NAME] = roof.name
        sData["_roof_hub_identifier"] = roofHubIdentifier
        entities.append(SolarStringSensor(hass, sData, db, sensorGroupObj))
        if stringObj.realProductionSensor:
             entities.append(SolarStringPerformanceSensor(hass, sData, db, sensorGroupObj))
             
    if entities:
        asyncAddEntities(entities)
=======
            asyncAddEntities([PVModelCountSensor(hass, db)])

            # Iterate child subentries (the pills)
            subentries = getattr(configEntry, "subentries", {}) or {}
            for subId, sub in subentries.items():
                _processSubentry(hass, configEntry.entry_id, sub, db, deviceRegistry, asyncAddEntities)
            return

        # ── CASE SUBENTRY CALL ───────────────────────────────────────
        # HA also calls setup directly for each pill.
        _processSubentry(hass, configEntry.entry_id, configEntry, db, deviceRegistry, asyncAddEntities)

    except Exception as e:
        _LOGGER.exception(f"Error during sensor.py setup: {e}")


def _processSubentry(hass, mainEntryId, entry, db, deviceRegistry, asyncAddEntities):
    """Unified handler for subentry processing."""
    data = entry.data
    # Use the entry's own ID if it's a subentry (pill), otherwise None
    # This is CRITICAL for the HA UI to group items under the pill.
    subentryId = entry.entry_id if entry.entry_id != mainEntryId else None

    # 1. SENSOR GROUP
    if CONF_SENSOR_GROUP_NAME in data:
        groupName = data.get(CONF_SENSOR_GROUP_NAME)
        groupId = slugify(groupName)
        sgIdentifier = (DOMAIN, f"sg_{groupId}")
        
        deviceRegistry.async_get_or_create(
            config_entry_id=mainEntryId,
            config_subentry_id=subentryId,
            identifiers={sgIdentifier},
            name=groupName,
            manufacturer="Accurate Solar Forecast",
            model="Sensor Group",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        class _SimpleProxy: entry_id = mainEntryId; data = data
        proxy = _SimpleProxy()
        
        asyncAddEntities([
            SensorGroupVirtualSensor(hass, proxy, {sgIdentifier}),
            SensorGroupCloudinessSensor(hass, proxy, {sgIdentifier}),
        ])

    # 2. ROOF + CHILD STRINGS
    if CONF_ROOF_NAME in data:
        roofName = data.get(CONF_ROOF_NAME)
        roofId = slugify(roofName)
        roofHubIdentifier = (DOMAIN, f"roof_{roofId}")
        
        # Create Roof Hub device linked to this subentry
        deviceRegistry.async_get_or_create(
            config_entry_id=mainEntryId,
            config_subentry_id=subentryId,
            identifiers={roofHubIdentifier},
            name=roofName,
            manufacturer="Accurate Solar Forecast",
            model="Roof Hub",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        roofStrings = db.getRoofStrings(roofId)
        sensorGroupObj = db.getSensorGroupForRoof(roofId)
        
        entities = []
        for stringId, stringObj in roofStrings.items():
            sData = stringObj.to_dict()
            sData[CONF_ROOF_NAME] = roofName
            sData["_roof_hub_identifier"] = roofHubIdentifier
            
            # Entities will use _roof_hub_identifier as via_device
            entities.append(SolarStringSensor(hass, sData, db, sensorGroupObj))
            if stringObj.realProductionSensor:
                entities.append(SolarStringPerformanceSensor(hass, sData, db, sensorGroupObj))
        
        if entities:
            asyncAddEntities(entities)
>>>>>>> 58f268e90c2b0be8660805ca12469610abf73521
