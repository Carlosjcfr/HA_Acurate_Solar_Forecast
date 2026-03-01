"""Diagnostic entities for Accurate Solar Forecast."""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from .variables.const import DOMAIN
from .core.helpers import slugify

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, configEntry, asyncAddEntities):
    """Set up the diagnostic binary sensors (global only)."""
    try:
        domainData = hass.data.get(DOMAIN, {})
        db = domainData.get("db")
        if db:
            asyncAddEntities([AccurateSolarHealthSensor(hass, db, configEntry)])
    except Exception as e:
        _LOGGER.exception(f"Error setting up binary_sensor platform: {e}")


async def async_setup_subentry(hass, configEntry, subentry, asyncAddEntities):
    """No binary sensors per subentry — diagnostics are global."""
    pass


# ---------------------------------------------------------------------------
# Diagnostic checks registry
# ---------------------------------------------------------------------------

def _runAllChecks(db, hass=None) -> list[dict]:
    """Run all diagnostic checks and return a list of issue dicts.
    
    Each issue dict has:
      - severity: 'critical' | 'warning' | 'info'
      - category: 'database' | 'model' | 'roof' | 'string' | 'sensor_group' | 'consistency'
      - message: human-readable description
    """
    issues = []

    # --- DATABASE ---
    if not db:
        issues.append({"severity": "critical", "category": "database", "message": "Database instance not available"})
        return issues

    if not db.data:
        issues.append({"severity": "critical", "category": "database", "message": "PV model database is empty (no models loaded)"})

    # --- PV MODELS ---
    for modelId, model in db.data.items():
        if not model.brand or model.brand.strip() == "":
            issues.append({"severity": "warning", "category": "model", "message": f"Model '{model.name}' has no brand defined"})
        if model.pStc <= 0:
            issues.append({"severity": "warning", "category": "model", "message": f"Model '{model.name}' has invalid power STC: {model.pStc}W"})
        if model.gamma >= 0:
            issues.append({"severity": "info", "category": "model", "message": f"Model '{model.name}' has unusual gamma coefficient: {model.gamma} (should be negative)"})

    # --- ROOFS ---
    for roofId, roof in db.roofs.items():
        # Roof without strings
        if not roof.strings or len(roof.strings) == 0:
            issues.append({"severity": "warning", "category": "roof", "message": f"Roof '{roof.name}' has no strings configured"})

        # Roof without sensor group
        sgObj = db.getSensorGroupForRoof(roofId)
        if not sgObj:
            if roof.sensorGroupId:
                # Reference exists but SG is missing from DB
                issues.append({"severity": "critical", "category": "consistency", "message": f"Roof '{roof.name}' references sensor group '{roof.sensorGroupId}' which does not exist in the database"})
            else:
                issues.append({"severity": "critical", "category": "roof", "message": f"Roof '{roof.name}' has no sensor group assigned"})

        # Geometry validation
        if roof.tilt < 0 or roof.tilt > 90:
            issues.append({"severity": "warning", "category": "roof", "message": f"Roof '{roof.name}' tilt out of range: {roof.tilt}° (expected 0-90)"})
        if roof.azimuth < 0 or roof.azimuth > 360:
            issues.append({"severity": "warning", "category": "roof", "message": f"Roof '{roof.name}' azimuth out of range: {roof.azimuth}° (expected 0-360)"})

        # --- STRINGS (per roof) ---
        for stringId, string in roof.strings.items():
            # Orphan model
            modelId = slugify(string.panelModel)
            if modelId not in db.data:
                issues.append({"severity": "critical", "category": "string", "message": f"String '{string.name}' references model '{string.panelModel}' which is missing from the PV library"})

            # Panel count validation
            if string.numPanels <= 0:
                issues.append({"severity": "warning", "category": "string", "message": f"String '{string.name}' has invalid panel count: {string.numPanels}"})
            if string.numStrings <= 0:
                issues.append({"severity": "warning", "category": "string", "message": f"String '{string.name}' has invalid parallel strings count: {string.numStrings}"})

            # Geometry validation
            if string.tilt < 0 or string.tilt > 90:
                issues.append({"severity": "warning", "category": "string", "message": f"String '{string.name}' tilt out of range: {string.tilt}° (expected 0-90)"})
            if string.azimuth < 0 or string.azimuth > 360:
                issues.append({"severity": "warning", "category": "string", "message": f"String '{string.name}' azimuth out of range: {string.azimuth}° (expected 0-360)"})

    # --- SENSOR GROUPS ---
    for sgId, sg in db.sensor_groups.items():
        if not sg.refSensor or sg.refSensor.strip() == "":
            issues.append({"severity": "critical", "category": "sensor_group", "message": f"Sensor group '{sg.name}' has no irradiance sensor configured"})
        if not sg.tempSensor or sg.tempSensor.strip() == "":
            issues.append({"severity": "warning", "category": "sensor_group", "message": f"Sensor group '{sg.name}' has no temperature sensor configured"})

        # Irradiance sensor geometry
        if sg.refTilt < 0 or sg.refTilt > 90:
            issues.append({"severity": "warning", "category": "sensor_group", "message": f"Sensor group '{sg.name}' irradiance sensor tilt out of range: {sg.refTilt}°"})

        # Check if this SG is used by any roof
        linkedRoofs = [r.name for r in db.roofs.values() if r.sensorGroupId == sgId]
        if not linkedRoofs:
            issues.append({"severity": "info", "category": "sensor_group", "message": f"Sensor group '{sg.name}' is not linked to any roof"})

        # Validate sensor entity IDs exist in HA (if hass available)
        if hass:
            if sg.refSensor and not hass.states.get(sg.refSensor):
                issues.append({"severity": "warning", "category": "sensor_group", "message": f"Sensor group '{sg.name}': irradiance sensor '{sg.refSensor}' not found in HA"})
            if sg.tempSensor and not hass.states.get(sg.tempSensor):
                issues.append({"severity": "warning", "category": "sensor_group", "message": f"Sensor group '{sg.name}': temperature sensor '{sg.tempSensor}' not found in HA"})

    # --- CONSISTENCY: Orphan sensor groups ---
    linkedSgIds = {r.sensorGroupId for r in db.roofs.values() if r.sensorGroupId}
    for sgId in db.sensor_groups:
        if sgId not in linkedSgIds:
            # Already reported above as "info", skip duplicate
            pass

    return issues


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

class AccurateSolarHealthSensor(BinarySensorEntity):
    """Reflects the global health of the integration."""

    _attr_has_entity_name = True
    _attr_translation_key = "integration_health"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
        """Return True if there is a problem (any critical issue)."""
        try:
            allIssues = _runAllChecks(self._db, self.hass)
            return any(i["severity"] == "critical" for i in allIssues)
        except Exception:
            return True

    @property
    def extra_state_attributes(self):
        """Return detailed diagnostic status."""
        try:
            allIssues = _runAllChecks(self._db, self.hass)

            criticalCount = sum(1 for i in allIssues if i["severity"] == "critical")
            warningCount = sum(1 for i in allIssues if i["severity"] == "warning")
            infoCount = sum(1 for i in allIssues if i["severity"] == "info")

            # Group messages by severity
            criticalMessages = [i["message"] for i in allIssues if i["severity"] == "critical"]
            warningMessages = [i["message"] for i in allIssues if i["severity"] == "warning"]
            infoMessages = [i["message"] for i in allIssues if i["severity"] == "info"]

            return {
                "status": "HEALTHY" if criticalCount == 0 else "PROBLEMS DETECTED",
                "critical_count": criticalCount,
                "warning_count": warningCount,
                "info_count": infoCount,
                "critical_issues": criticalMessages,
                "warnings": warningMessages,
                "info": infoMessages,
                "models_count": len(self._db.data) if self._db else 0,
                "roofs_count": len(self._db.roofs) if self._db else 0,
                "groups_count": len(self._db.sensor_groups) if self._db else 0,
                "total_strings": sum(
                    len(r.strings) for r in self._db.roofs.values()
                ) if self._db else 0,
            }
        except Exception:
            return {
                "status": "ERROR",
                "critical_issues": ["Error reading database"],
            }
