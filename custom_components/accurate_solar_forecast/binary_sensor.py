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
            name="Accurate Solar Forecast (Diagnostics)",
            manufacturer="Accurate Solar Forecast",
            model="Diagnostic System",
        )

    @property
    def is_on(self) -> bool:
        """Return True if there is a problem."""
        try:
            if not self._db or not self._db.data:
                return True
            for roof in self._db.roofs.values():
                for string in roof.strings.values():
                    from .core import slugify
                    modelId = slugify(string.panelModel)
                    if modelId not in self._db.data:
                        return True
                    groupId = slugify(string.selectedSensorGroup)
                    if groupId not in self._db.sensor_groups:
                        return True
            return False
        except Exception:
            return True

    @property
    def extra_state_attributes(self):
        """Return detailed status."""
        try:
            issues = []
            if not self._db or not self._db.data:
                issues.append("Database not loaded or empty")

            for roofId, roof in self._db.roofs.items():
                for stringId, string in roof.strings.items():
                    from .core import slugify
                    if slugify(string.panelModel) not in self._db.data:
                        issues.append(f"Orphan string '{string.name}': Model '{string.panelModel}' missing")
                    if slugify(string.selectedSensorGroup) not in self._db.sensor_groups:
                        issues.append(f"Orphan string '{string.name}': Sensor Group '{string.selectedSensorGroup}' missing")

            return {
                "issues": issues,
                "models_count": len(self._db.data),
                "roofs_count": len(self._db.roofs),
                "groups_count": len(self._db.sensor_groups),
            }
        except Exception:
            return {"issues": ["Error reading database"]}
