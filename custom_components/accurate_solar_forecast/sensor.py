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

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Accurate Solar Forecast sensors from a config entry."""
    db = hass.data[DOMAIN]["db"]
    
    # CASE 1: SENSOR GROUP
    if CONF_SENSOR_GROUP_NAME in config_entry.data:
        ref_sensor_id = config_entry.data.get(CONF_REF_SENSOR)
        device_identifiers = None
        
        if ref_sensor_id:
            try:
                ent_reg = er.async_get(hass)
                dev_reg = dr.async_get(hass)
                ref_entry = ent_reg.async_get(ref_sensor_id)
                if ref_entry and ref_entry.device_id:
                    device = dev_reg.async_get(ref_entry.device_id)
                    if device:
                        device_identifiers = device.identifiers
            except Exception as e:
                _LOGGER.warning(f"Could not link to existing device: {e}")

        async_add_entities([
            SensorGroupVirtualSensor(hass, config_entry, device_identifiers),
            SensorGroupCloudinessSensor(hass, config_entry, device_identifiers)
        ])

    # CASE 2: ROOF (CONTAINS SOLAR STRINGS)
    elif CONF_ROOF_NAME in config_entry.data:
        roof_name = config_entry.data.get(CONF_ROOF_NAME)
        roof_id = slugify(roof_name) if roof_name else "default"
        roof_strings = db.get_roof_strings(roof_id)
        
        entities = []
        for string_id, string_obj in roof_strings.items():
            combined_data = string_obj.to_dict()
            combined_data[CONF_ROOF_NAME] = roof_name
            group_name = string_obj.selected_sensor_group
            sensor_group_obj = db.get_sensor_group(group_name)
            
            if sensor_group_obj:
                entities.append(SolarStringSensor(hass, combined_data, db, sensor_group_obj))
                if string_obj.real_production_sensor:
                    entities.append(SolarStringPerformanceSensor(hass, combined_data, db, sensor_group_obj))
                    
        if entities:
            async_add_entities(entities, update_before_add=True)

    # CASE 3: PV DATABASE MONITOR
    if CONF_SENSOR_GROUP_NAME in config_entry.data and "db" in hass.data[DOMAIN]:
         async_add_entities([AccurateSolarSensorDBSensor(hass, hass.data[DOMAIN]["db"])])
