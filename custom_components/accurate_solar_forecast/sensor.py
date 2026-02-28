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
            _LOGGER.error("DB not found in hass.data — skipping sensor.py setup")
            return

        deviceRegistry = dr.async_get(hass)

        # 1. ENCONTRAR EL ENTRY PRINCIPAL (PARENT)
        allEntries = hass.config_entries.async_entries(DOMAIN)
        mainEntry = next((e for e in allEntries if CONF_ROOF_NAME not in e.data and CONF_SENSOR_GROUP_NAME not in e.data), configEntry)
        mainEntryId = mainEntry.entry_id

        # CASO A: ENTRADA PRINCIPAL
        if configEntry.entry_id == mainEntryId:
            _LOGGER.debug(f"Configuring main entry: {mainEntryId}")
            
            # Global Counter (PV Library) always on Main Entry
            deviceRegistry.async_get_or_create(
                config_entry_id=mainEntryId,
                identifiers={(DOMAIN, "pv_models_library")},
                name="Módulos Guardados",
                manufacturer="Accurate Solar Forecast",
                model="PV Library",
                entry_type=dr.DeviceEntryType.SERVICE,
            )
            asyncAddEntities([PVModelCountSensor(hass, db)])
            
            # FALLBACK: Check DB for orphaned objects that don't have their own subentries.
            # This happens in Case: Guided flow (Roof created with a new SG in one go).
            subentryIds = {sub.entry_id for sub in getattr(mainEntry, "subentries", {}).values()} or set()
            
            # Map of name->subentryId for grouping
            subentryMap = {}
            for sId, sObj in getattr(mainEntry, "subentries", {}).items():
                name = sObj.data.get(CONF_ROOF_NAME, sObj.data.get(CONF_SENSOR_GROUP_NAME))
                if name: subentryMap[slugify(name)] = sId

            # Iterate DB objects
            for sgId, sg in db.sensor_groups.items():
                if sgId not in subentryMap:
                    _LOGGER.info(f"Sensor group '{sgId}' is in DB but has no subentry. Registering as orphan.")
                    _processEntry(hass, mainEntryId, None, sg.to_dict(), db, deviceRegistry, asyncAddEntities)

            # NOTE: For roofs, we usually always have a subentry unless something went wrong.
            for rId, roof in db.roofs.items():
                if rId not in subentryMap:
                    _LOGGER.warning(f"Roof '{rId}' is in DB but has no subentry. Registering as orphan.")
                    # Fallback data for orphan roof
                    dummyData = {CONF_ROOF_NAME: roof.name}
                    _processEntry(hass, mainEntryId, None, dummyData, db, deviceRegistry, asyncAddEntities)

            return

        # CASO B: SUBENTRADA (PILL)
        _LOGGER.debug(f"Configuring subentry flow: {configEntry.entry_id}")
        _processEntry(hass, mainEntryId, configEntry.entry_id, configEntry.data, db, deviceRegistry, asyncAddEntities)

    except Exception as e:
        _LOGGER.exception(f"Error during sensor.py setup: {e}")


def _processEntry(hass, mainEntryId, subentryId, data, db, deviceRegistry, asyncAddEntities):
    """Procesa una entrada (subentry o huérfana) para crear sus dispositivos y entidades."""
    # --- TEJADO (ROOF) ---
    if CONF_ROOF_NAME in data:
        roofName = data[CONF_ROOF_NAME]
        roofId = slugify(roofName)
        
        roofHubIdentifier = (DOMAIN, f"roof_{roofId}")
        deviceRegistry.async_get_or_create(
            config_entry_id=mainEntryId,
            config_subentry_id=subentryId,
            identifiers={roofHubIdentifier},
            name=roofName,
            manufacturer="Accurate Solar Forecast",
            model="Roof Hub",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        roofObj = db.getRoof(roofId)
        if not roofObj: return

        sensorGroupObj = db.getSensorGroupForRoof(roofId)
        entities = []
        for stringId, stringObj in roofObj.strings.items():
            sData = stringObj.to_dict()
            sData[CONF_ROOF_NAME] = roofName
            sData["_roof_hub_identifier"] = roofHubIdentifier
            entities.append(SolarStringSensor(hass, sData, db, sensorGroupObj))
            if stringObj.realProductionSensor:
                entities.append(SolarStringPerformanceSensor(hass, sData, db, sensorGroupObj))
        
        if entities:
            asyncAddEntities(entities)

    # --- GRUPO DE SENSORES ---
    if CONF_SENSOR_GROUP_NAME in data:
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
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        class _Proxy: 
            entry_id = mainEntryId
            data = data
        
        asyncAddEntities([
            SensorGroupVirtualSensor(hass, _Proxy(), {sgIdentifier}),
            SensorGroupCloudinessSensor(hass, _Proxy(), {sgIdentifier}),
        ])
