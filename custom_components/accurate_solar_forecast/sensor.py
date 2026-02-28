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
            _LOGGER.error("DATABASE NOT FOUND in hass.data. domainData: %s", domainData)
            return
        
        _LOGGER.debug(f"async_setup_entry starting for configEntry: {configEntry.title} ({configEntry.entry_id})")

        deviceRegistry = dr.async_get(hass)

        # 1. ENCONTRAR EL ENTRY PRINCIPAL (PARENT)
        allEntries = hass.config_entries.async_entries(DOMAIN)
        mainEntry = next((e for e in allEntries if CONF_ROOF_NAME not in e.data and CONF_SENSOR_GROUP_NAME not in e.data), configEntry)
        mainEntryId = mainEntry.entry_id

        # 2. SEPARATE SUBENTRY MAPS (to avoid Roof vs SG collisions)
        roofSubentryMap = {}   # slug -> entry_id
        groupSubentryMap = {}  # slug -> entry_id
        
        allSubentries = getattr(mainEntry, "subentries", None)
        if allSubentries:
            # Handle both dict-like and iterable subentries
            items = allSubentries.items() if hasattr(allSubentries, 'items') else ((getattr(s, 'subentry_id', idx), s) for idx, s in enumerate(allSubentries))
            for sId, sObj in items:
                sData = getattr(sObj, 'data', {}) or {}
                if CONF_ROOF_NAME in sData:
                    roofSubentryMap[slugify(sData[CONF_ROOF_NAME])] = sId
                if CONF_SENSOR_GROUP_NAME in sData:
                    groupSubentryMap[slugify(sData[CONF_SENSOR_GROUP_NAME])] = sId

        # CASO A: ENTRADA PRINCIPAL
        if configEntry.entry_id == mainEntryId:
            _LOGGER.debug(f"Configuring main entry: {mainEntryId}")
            
            # Global Counter (PV Library)
            deviceRegistry.async_get_or_create(
                config_entry_id=mainEntryId,
                identifiers={(DOMAIN, "pv_models_library")},
                name="Módulos Guardados",
                manufacturer="Accurate Solar Forecast",
                model="PV Library",
            )
            asyncAddEntities([PVModelCountSensor(hass, db)])
            
            # ORPHAN DETECTION (Objects in DB without HA subentry)
            # Build set of SGs that are already linked to roofs with subentries (they'll be created with the roof)
            sgLinkedToActiveRoofs = set()
            for rId, rObj in db.roofs.items():
                if rId in roofSubentryMap and rObj.sensorGroupId:
                    sgLinkedToActiveRoofs.add(rObj.sensorGroupId)
            
            for sgId, sg in db.sensor_groups.items():
                if sgId not in groupSubentryMap and sgId not in sgLinkedToActiveRoofs:
                    _LOGGER.info(f"Sensor group '{sgId}' is in DB but has no subentry and no active roof link. Registering as orphan.")
                    _processEntry(hass, mainEntryId, None, sg.to_dict(), db, deviceRegistry, asyncAddEntities)

            for roofId, roof in db.roofs.items():
                if roofId not in roofSubentryMap:
                    _LOGGER.info(f"Roof '{roofId}' is in DB but has no subentry. Registering as orphan.")
                    _processEntry(hass, mainEntryId, None, {CONF_ROOF_NAME: roof.name}, db, deviceRegistry, asyncAddEntities)
                else:
                    _LOGGER.debug(f"Roof '{roofId}' already has a subentry ({roofSubentryMap[roofId]}). Skipping main-entry processing.")

            return

        # CASO B: SUBENTRADA (PILL)
        _LOGGER.info(f"Configuring subentry pill '{configEntry.title}' (ID: {configEntry.entry_id})")
        _processEntry(hass, mainEntryId, configEntry.entry_id, configEntry.data, db, deviceRegistry, asyncAddEntities)

    except Exception as e:
        _LOGGER.exception(f"Error during sensor.py setup: {e}")


def _processEntry(hass, mainEntryId, subentryId, data, db, deviceRegistry, asyncAddEntities):
    """Procesa una entrada (subentry o huérfana) para crear sus dispositivos y entidades."""
    # --- TEJADO ---
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
        )

        roofObj = db.getRoof(roofId)
        if not roofObj:
            _LOGGER.error(f"CRITICAL: Roof '{roofId}' NOT FOUND in DB. Available roofs: {list(db.roofs.keys())}")
            return

        sensorGroupObj = db.getSensorGroupForRoof(roofId)
        _LOGGER.info(f"Processing Roof '{roofName}' ({roofId}). Strings in DB: {len(roofObj.strings)}. SensorGroup: {sensorGroupObj.name if sensorGroupObj else 'None'}")
        
        entities = []
        for stringId, stringObj in roofObj.strings.items():
            sData = stringObj.to_dict()
            sData[CONF_ROOF_NAME] = roofName
            sData["_roof_hub_identifier"] = roofHubIdentifier
            
            # Explicitly register string devices to link them to the subentry pill
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
        
        # Also create sensor group entities (Estado / Nubosidad) under this roof's subentry
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
            _LOGGER.info(f"Adding {len(entities)} entities for roof '{roofName}' (ID: {subentryId or 'Orphan'})")
            asyncAddEntities(entities)
        else:
            _LOGGER.warning(f"No entities created for roof '{roofName}' (zero strings found in DB object for '{roofId}')")

    # --- GRUPO DE SENSORES ---
    elif CONF_SENSOR_GROUP_NAME in data:
        groupName = data[CONF_SENSOR_GROUP_NAME]
        groupId = slugify(groupName)
        sgIdentifier = (DOMAIN, f"sg_{groupId}")
        
        # Explicitly register the SG device with the subentry
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
