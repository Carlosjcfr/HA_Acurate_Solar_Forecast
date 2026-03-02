"""Diagnostic entities for Accurate Solar Forecast."""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from .const import DOMAIN, CONF_ROOF_NAME, CONF_SENSOR_GROUP_NAME, CONF_TILT, CONF_AZIMUTH
from .helpers import slugify
from .models import Roof

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

    # --- ROOFS (now from Subentries) ---
    roofs: list[Roof] = []
    if hass:
        for entry in hass.config_entries.async_entries(DOMAIN):
                # Check for sub.data existence (HA might have subentries with None data during early stages)
                if sub.data and CONF_ROOF_NAME in sub.data:
                    try:
                        roofs.append(Roof.from_dict({
                            "name": sub.data.get(CONF_ROOF_NAME, "Roof"),
                            "tilt": sub.data.get(CONF_TILT, 30.0),
                            "azimuth": sub.data.get(CONF_AZIMUTH, 180.0),
                            "sensor_group_id": sub.data.get(CONF_SENSOR_GROUP_NAME, ""),
                            "strings": sub.data.get("strings", {})
                        }))
                    except Exception as e:
                        issues.append({"severity": "critical", "category": "roof", "message": f"Error parsing roof subentry '{sub.title or 'Unknown'}': {e}"})

    for roof in roofs:
        # Roof without strings
        if not roof.strings or len(roof.strings) == 0:
            issues.append({"severity": "warning", "category": "roof", "message": f"Roof '{roof.name}' has no strings configured"})

        # Roof without sensor group
        if not roof.sensorGroupId:
            issues.append({"severity": "critical", "category": "roof", "message": f"Roof '{roof.name}' has no sensor group assigned"})
        elif roof.sensorGroupId not in db.sensor_groups:
             issues.append({"severity": "critical", "category": "consistency", "message": f"Roof '{roof.name}' references sensor group '{roof.sensorGroupId}' which does not exist in the database"})

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
        # We compare both by SG name and SG ID to be robust
        isLinked = any(r.sensorGroupId == sgId or r.sensorGroupId == sg.name for r in roofs)
        
        if not isLinked:
            issues.append({"severity": "info", "category": "sensor_group", "message": f"Sensor group '{sg.name}' is not linked to any roof"})

        # Validate sensor entity IDs exist in HA (if hass available)
        if hass:
            if sg.refSensor and not hass.states.get(sg.refSensor):
                issues.append({"severity": "warning", "category": "sensor_group", "message": f"Sensor group '{sg.name}': irradiance sensor '{sg.refSensor}' not found in HA"})
            if sg.tempSensor and not hass.states.get(sg.tempSensor):
                issues.append({"severity": "warning", "category": "sensor_group", "message": f"Sensor group '{sg.name}': temperature sensor '{sg.tempSensor}' not found in HA"})

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

            # Re-run checks to get the roofs list for counting
            # (In a real app we'd optimize this to avoid double work, but for diagnostics it's okay)
            roofs: list[Roof] = []
            if self.hass:
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    for sub in entry.subentries:
                        if sub.data and CONF_ROOF_NAME in sub.data:
                            try:
                                roofs.append(Roof.from_dict({
                                    "name": sub.data.get(CONF_ROOF_NAME, "Roof"),
                                    "tilt": sub.data.get(CONF_TILT, 30.0),
                                    "azimuth": sub.data.get(CONF_AZIMUTH, 180.0),
                                    "sensor_group_id": sub.data.get(CONF_SENSOR_GROUP_NAME, ""),
                                    "strings": sub.data.get("strings", {})
                                }))
                            except: pass

            return {
                "status": "HEALTHY" if criticalCount == 0 else "PROBLEMS DETECTED",
                "critical_count": criticalCount,
                "warning_count": warningCount,
                "info_count": infoCount,
                "critical_issues": criticalMessages,
                "warnings": warningMessages,
                "info": infoMessages,
                "models_count": len(self._db.data) if self._db else 0,
                "roofs_count": len(roofs),
                "groups_count": len(self._db.sensor_groups) if self._db else 0,
                "total_strings": sum(
                    len(r.strings) for r in roofs
                ),
            }
        except Exception as e:
            _LOGGER.error(f"Error reading database in diagnostic sensor: {e}", exc_info=True)
            return {
                "status": "ERROR",
                "critical_issues": [f"Error reading database: {e}"],
            }
