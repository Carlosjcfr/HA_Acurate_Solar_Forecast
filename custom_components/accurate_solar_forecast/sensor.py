import logging
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .variables.const import *
from .core import (
    SolarStringSensor,
    SensorGroupVirtualSensor,
    SensorGroupCloudinessSensor,
    SolarStringPerformanceSensor,
    AccurateSolarSensorDBSensor,
    slugify
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up the Accurate Solar Forecast sensors from a config entry."""
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            return
        
        # CASE 1: SENSOR GROUP
        if CONF_SENSOR_GROUP_NAME in configEntry.data:
            refSensorId = configEntry.data.get(CONF_REF_SENSOR)
            deviceIdentifiers = None
            
            if refSensorId:
                try:
                    entityRegistry = er.async_get(hass)
                    deviceRegistry = dr.async_get(hass)
                    refEntry = entityRegistry.async_get(refSensorId)
                    if refEntry and refEntry.device_id:
                        device = deviceRegistry.async_get(refEntry.device_id)
                        if device:
                            deviceIdentifiers = device.identifiers
                except Exception as e:
                    _LOGGER.warning(f"Could not link to existing device: {e}")

            asyncAddEntities([
                SensorGroupVirtualSensor(hass, configEntry, deviceIdentifiers),
                SensorGroupCloudinessSensor(hass, configEntry, deviceIdentifiers)
            ])

            # Add PV database monitor sensor
            asyncAddEntities([AccurateSolarSensorDBSensor(hass, db)])

        # CASE 2: ROOF (CONTAINS SOLAR STRINGS)
        elif CONF_ROOF_NAME in configEntry.data:
            roofName = configEntry.data.get(CONF_ROOF_NAME)
            roofId = slugify(roofName) if roofName else "default"
            roofStrings = db.getRoofStrings(roofId)
            
            # Sensor group is now associated at roof level
            sensorGroupObj = db.getSensorGroupForRoof(roofId)
            if not sensorGroupObj:
                _LOGGER.warning(
                    f"Roof '{roofId}' has no sensor group assigned — "
                    "strings registered in degraded mode (no forecast)."
                )

            # Create the roof hub device in HA device registry
            deviceRegistry = dr.async_get(hass)
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
                
                # Always create string sensor (sensorGroupObj=None = degraded mode)
                entities.append(SolarStringSensor(hass, combinedData, db, sensorGroupObj))
                if stringObj.realProductionSensor:
                    entities.append(SolarStringPerformanceSensor(hass, combinedData, db, sensorGroupObj))
                        
            if entities:
                asyncAddEntities(entities, update_before_add=True)
    except Exception as e:
        _LOGGER.exception(f"Error setting up sensor platform: {e}")

