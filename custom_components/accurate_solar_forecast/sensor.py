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

        # === PROCESS ALL DATA FROM THE MAIN ENTRY ===
        # With the Subentries API, async_setup_entry is called ONCE for the main entry.
        # Subentries are NOT separate config entries — they are data attached to the main entry.
        # We must process ALL roofs/SGs here, passing the correct subentry ID for each.
        
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
        
        # Build set of SGs that are linked to roofs (they'll be created as children of the roof)
        sgLinkedToRoofs = set()
        for rId, rObj in db.roofs.items():
            if rObj.sensorGroupId:
                sgLinkedToRoofs.add(rObj.sensorGroupId)
        
        # Process standalone sensor groups (those with their own subentry OR orphans NOT linked to any roof)
        for sgId, sg in db.sensor_groups.items():
            if sgId in sgLinkedToRoofs:
                continue  # Will be created as part of the roof processing
            subId = groupSubentryMap.get(sgId)  # None if orphan
            _LOGGER.info(f"Processing standalone sensor group '{sgId}' (subentry: {subId or 'orphan'})")
            _processEntry(hass, mainEntryId, subId, sg.to_dict(), db, deviceRegistry, asyncAddEntities)

        # Process ALL roofs (with or without subentry)
        for roofId, roof in db.roofs.items():
            subId = roofSubentryMap.get(roofId)  # None if orphan
            _LOGGER.info(f"Processing roof '{roofId}' (subentry: {subId or 'orphan'})")
            _processEntry(hass, mainEntryId, subId, {CONF_ROOF_NAME: roof.name}, db, deviceRegistry, asyncAddEntities)

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
