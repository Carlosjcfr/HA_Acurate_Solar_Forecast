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

# Identifier for the main integration hub device — used as via_device anchor
MAIN_HUB_ID = (DOMAIN, "main_hub")


async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up the Accurate Solar Forecast sensors from a config entry."""
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            return

        deviceRegistry = dr.async_get(hass)

        # ─────────────────────────────────────────────────────────────
        # CASE 1: SENSOR GROUP SUBENTRY
        # ─────────────────────────────────────────────────────────────
        if CONF_SENSOR_GROUP_NAME in configEntry.data:
            groupName = configEntry.data.get(CONF_SENSOR_GROUP_NAME, "Sensor Group")
            groupId = slugify(groupName)

            # Create a dedicated service device for this sensor group,
            # nested under the main hub via via_device
            sgIdentifier = (DOMAIN, f"sg_{groupId}")
            deviceRegistry.async_get_or_create(
                config_entry_id=configEntry.entry_id,
                identifiers={sgIdentifier},
                name=groupName,
                manufacturer="Accurate Solar Forecast",
                model="Sensor Group",
                entry_type=dr.DeviceEntryType.SERVICE,
                via_device=MAIN_HUB_ID,
            )

            asyncAddEntities([
                SensorGroupVirtualSensor(hass, configEntry, {sgIdentifier}),
                SensorGroupCloudinessSensor(hass, configEntry, {sgIdentifier})
            ])

        # ─────────────────────────────────────────────────────────────
        # CASE 2: ROOF SUBENTRY (contains solar strings / hub)
        # ─────────────────────────────────────────────────────────────
        elif CONF_ROOF_NAME in configEntry.data:
            roofName = configEntry.data.get(CONF_ROOF_NAME)
            roofId = slugify(roofName) if roofName else "default"
            roofStrings = db.getRoofStrings(roofId)

            # Sensor group is associated at roof level
            sensorGroupObj = db.getSensorGroupForRoof(roofId)
            if not sensorGroupObj:
                _LOGGER.warning(
                    f"Roof '{roofId}' has no sensor group assigned — "
                    "strings registered in degraded mode (no forecast)."
                )

            # Create the roof hub device, nested under the main hub
            roofHubIdentifier = (DOMAIN, f"roof_{roofId}")
            deviceRegistry.async_get_or_create(
                config_entry_id=configEntry.entry_id,
                identifiers={roofHubIdentifier},
                name=roofName,
                manufacturer="Accurate Solar Forecast",
                model="Roof Hub",
                entry_type=dr.DeviceEntryType.SERVICE,
                via_device=MAIN_HUB_ID,
            )

            entities = []
            for stringId, stringObj in roofStrings.items():
                combinedData = stringObj.to_dict()
                combinedData[CONF_ROOF_NAME] = roofName
                combinedData["_roof_hub_identifier"] = roofHubIdentifier

                # Always create string sensor (None sensorGroup = degraded mode)
                entities.append(SolarStringSensor(hass, combinedData, db, sensorGroupObj))
                if stringObj.realProductionSensor:
                    entities.append(SolarStringPerformanceSensor(hass, combinedData, db, sensorGroupObj))

            if entities:
                asyncAddEntities(entities, update_before_add=True)

        # ─────────────────────────────────────────────────────────────
        # CASE 0: MAIN INTEGRATION ENTRY
        # Creates the structural hub devices and global overview sensors
        # ─────────────────────────────────────────────────────────────
        else:
            # 1. Create the integration master hub device (anchor for all via_device)
            deviceRegistry.async_get_or_create(
                config_entry_id=configEntry.entry_id,
                identifiers={MAIN_HUB_ID},
                name="Accurate Solar Forecast",
                manufacturer="Accurate Solar Forecast",
                model="Integration Hub",
                entry_type=dr.DeviceEntryType.SERVICE,
            )

            # 2. Create "Módulos Guardados" service device nested under main hub
            deviceRegistry.async_get_or_create(
                config_entry_id=configEntry.entry_id,
                identifiers={(DOMAIN, "pv_models_library")},
                name="Módulos Guardados",
                manufacturer="Accurate Solar Forecast",
                model="PV Library",
                entry_type=dr.DeviceEntryType.SERVICE,
                via_device=MAIN_HUB_ID,
            )

            # 3. Register overview sensors on the PV library device
            asyncAddEntities([
                PVModelCountSensor(hass, db),
                AccurateSolarSensorDBSensor(hass, db),
            ])

    except Exception as e:
        _LOGGER.exception(f"Error setting up sensor platform: {e}")
