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


async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up Accurate Solar Forecast sensors.

    HA calls this for the MAIN config entry after any subentry change.
    We read all data directly from the in-memory DB so we don't rely
    on the configEntry.subentries API, which may not be accessible on
    all HA versions.

    Belt-and-suspenders: if called with a data-bearing subentry configEntry,
    we handle it directly and return.
    """
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if not db:
            _LOGGER.warning("DB not loaded — skipping sensor platform setup")
            return

        deviceRegistry = dr.async_get(hass)

        # ── BELT-AND-SUSPENDERS: subentry called directly ────────────
        # If HA DOES call per-subentry, handle it and return.
        # Otherwise the main-entry path below covers everything.
        if CONF_SENSOR_GROUP_NAME in configEntry.data:
            _setupSensorGroupFromData(
                hass, configEntry.entry_id, configEntry.data, db, deviceRegistry, asyncAddEntities
            )
            return

        if CONF_ROOF_NAME in configEntry.data:
            _setupRoofFromData(
                hass, configEntry.entry_id, configEntry.data, db, deviceRegistry, asyncAddEntities
            )
            return

        # ── MAIN ENTRY: set up overview + all DB items ───────────────
        _LOGGER.debug("Setting up main entry entities")

        # 1. "Módulos Guardados" service device + count sensor
        deviceRegistry.async_get_or_create(
            config_entry_id=configEntry.entry_id,
            identifiers={(DOMAIN, "pv_models_library")},
            name="Módulos Guardados",
            manufacturer="Accurate Solar Forecast",
            model="PV Library",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        asyncAddEntities([PVModelCountSensor(hass, db)])

        # 2. All sensor groups from DB
        for groupId, sensorGroup in db.sensor_groups.items():
            groupData = {
                CONF_SENSOR_GROUP_NAME: sensorGroup.name,
                CONF_REF_SENSOR: sensorGroup.refSensor,
                CONF_TEMP_SENSOR: sensorGroup.tempSensor,
                CONF_TEMP_PANEL_SENSOR: sensorGroup.tempPanelSensor,
                CONF_WIND_SENSOR: sensorGroup.windSensor,
                CONF_WEATHER_ENTITY: sensorGroup.weatherEntity,
                CONF_ILLUMINANCE_SENSOR: sensorGroup.illuminanceSensor,
                CONF_REF_TILT: sensorGroup.refTilt,
                CONF_REF_ORIENTATION: sensorGroup.refOrientation,
            }
            _setupSensorGroupFromData(
                hass, configEntry.entry_id, groupData, db, deviceRegistry, asyncAddEntities
            )

        # 3. All roofs from DB (each roof → hub + string child devices)
        for roofId, roof in db.roofs.items():
            roofData = {CONF_ROOF_NAME: roof.name}
            _setupRoofFromData(
                hass, configEntry.entry_id, roofData, db, deviceRegistry, asyncAddEntities
            )

    except Exception as e:
        _LOGGER.exception(f"Error setting up sensor platform: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Helper: sensor group
# ─────────────────────────────────────────────────────────────────────────────

def _setupSensorGroupFromData(hass, entryId, data, db, deviceRegistry, asyncAddEntities):
    """Create sensor group service device and its virtual sensors."""
    groupName = data.get(CONF_SENSOR_GROUP_NAME)
    if not groupName:
        return
    try:
        groupId = slugify(groupName)
        sgIdentifier = (DOMAIN, f"sg_{groupId}")
        deviceRegistry.async_get_or_create(
            config_entry_id=entryId,
            identifiers={sgIdentifier},
            name=groupName,
            manufacturer="Accurate Solar Forecast",
            model="Sensor Group",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        # Build a minimal proxy so VirtualSensor / CloudinessSensor read config
        class _Proxy:
            pass
        proxy = _Proxy()
        proxy.entry_id = entryId
        proxy.data = data

        asyncAddEntities([
            SensorGroupVirtualSensor(hass, proxy, {sgIdentifier}),
            SensorGroupCloudinessSensor(hass, proxy, {sgIdentifier}),
        ])
        _LOGGER.debug(f"Sensor group '{groupName}' entities registered")
    except Exception as e:
        _LOGGER.exception(f"Error setting up sensor group '{groupName}': {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Helper: roof + strings
# ─────────────────────────────────────────────────────────────────────────────

def _setupRoofFromData(hass, entryId, data, db, deviceRegistry, asyncAddEntities):
    """Create roof hub device and string child sensor entities."""
    roofName = data.get(CONF_ROOF_NAME)
    if not roofName:
        return
    try:
        roofId = slugify(roofName)
        roofStrings = db.getRoofStrings(roofId)
        sensorGroupObj = db.getSensorGroupForRoof(roofId)

        if not sensorGroupObj:
            _LOGGER.warning(
                f"Roof '{roofId}' has no sensor group assigned — "
                "strings will be registered in degraded mode."
            )

        # Roof hub device
        roofHubIdentifier = (DOMAIN, f"roof_{roofId}")
        deviceRegistry.async_get_or_create(
            config_entry_id=entryId,
            identifiers={roofHubIdentifier},
            name=roofName,
            manufacturer="Accurate Solar Forecast",
            model="Roof Hub",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

        if not roofStrings:
            _LOGGER.warning(f"Roof '{roofId}' has no strings configured yet.")
            return

        entities = []
        for stringId, stringObj in roofStrings.items():
            combinedData = stringObj.to_dict()
            combinedData[CONF_ROOF_NAME] = roofName
            combinedData["_roof_hub_identifier"] = roofHubIdentifier

            entities.append(SolarStringSensor(hass, combinedData, db, sensorGroupObj))
            if stringObj.realProductionSensor:
                entities.append(SolarStringPerformanceSensor(hass, combinedData, db, sensorGroupObj))

        if entities:
            asyncAddEntities(entities, update_before_add=True)
            _LOGGER.debug(f"Roof '{roofName}': {len(entities)} string entities registered")

    except Exception as e:
        _LOGGER.exception(f"Error setting up roof '{roofName}': {e}")
