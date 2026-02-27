"""Diagnostic entities for Accurate Solar Forecast."""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.entity import DeviceInfo
from .variables.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up the diagnostic binary sensors."""
    try:
        # Only create the health sensor on the main entry (no special key in data)
        from .variables.const import CONF_SENSOR_GROUP_NAME, CONF_ROOF_NAME
        if CONF_SENSOR_GROUP_NAME in configEntry.data or CONF_ROOF_NAME in configEntry.data:
            return
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if db:
            asyncAddEntities([AccurateSolarHealthSensor(hass, db, configEntry)])
    except Exception as e:
        _LOGGER.exception(f"Error setting up binary_sensor platform: {e}")

class AccurateSolarHealthSensor(BinarySensorEntity):
    """Reflects the global health of the integration."""

    _attr_has_entity_name = True
    _attr_translation_key = "integration_health"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hass, db, configEntry):
        self.hass = hass
        self._db = db
        self._configEntry = configEntry
        self._attr_unique_id = f"{configEntry.entry_id}_health"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "global_diagnostics")},
            name="Diagnosis",
            manufacturer="Accurate Solar Forecast",
            model="Diagnosis",
        )

    @property
    def is_on(self) -> bool:
        """Return True if there is a problem."""
        try:
            if not self._db or not self._db.data:
                return True
            from .core import slugify
            for roofId, roof in self._db.roofs.items():
                for string in roof.strings.values():
                    modelId = slugify(string.panelModel)
                    if modelId not in self._db.data:
                        return True
                # Sensor group is now at roof level
                if not self._db.getSensorGroupForRoof(roofId):
                    return True
            return False
        except Exception:
            return True

    @property
    def extra_state_attributes(self):
        """Return detailed status."""
        try:
            from .core import slugify
            issues = []
            if not self._db or not self._db.data:
                issues.append("Database not loaded or empty")

            for roofId, roof in self._db.roofs.items():
                for stringId, string in roof.strings.items():
                    if slugify(string.panelModel) not in self._db.data:
                        issues.append(f"Orphan string '{string.name}': Model '{string.panelModel}' missing")
                if not self._db.getSensorGroupForRoof(roofId):
                    issues.append(f"Roof '{roofId}' has no sensor group assigned")

            return {
                "issues": issues,
                "models_count": len(self._db.data),
                "roofs_count": len(self._db.roofs),
                "groups_count": len(self._db.sensor_groups),
            }
        except Exception:
            return {"issues": ["Error reading database"]}
