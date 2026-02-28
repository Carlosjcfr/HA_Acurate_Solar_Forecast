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
            return

        deviceRegistry = dr.async_get(hass)
        
        # Collect subentries to map names -> subentry IDs for UI grouping
        subentries = getattr(configEntry, "subentries", {}) or {}
        subentryMap = {} # key: slugified name, value: entry_id
        for sId, sObj in subentries.items():
            name = sObj.data.get(CONF_ROOF_NAME) or sObj.data.get(CONF_SENSOR_GROUP_NAME)
            if name:
                subentryMap[slugify(name)] = sId

        # 1. MAIN ENTRY OVERVIEW (counter)
        if not (CONF_SENSOR_GROUP_NAME in configEntry.data or CONF_ROOF_NAME in configEntry.data):
             deviceRegistry.async_get_or_create(
                config_entry_id=configEntry.entry_id,
                identifiers={(DOMAIN, "pv_models_library")},
                name="Módulos Guardados",
                manufacturer="Accurate Solar Forecast",
                model="PV Library",
                entry_type=dr.DeviceEntryType.SERVICE,
            )
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
