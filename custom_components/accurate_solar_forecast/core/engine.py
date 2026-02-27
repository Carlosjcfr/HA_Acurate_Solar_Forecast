import math
import logging
from typing import Any, Optional
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr, entity_registry as er
from ..variables.const import *
from .helpers import slugify

_LOGGER = logging.getLogger(__name__)

# --- UTILS & CONSTANTS ---
SUN_MOVEMENT_THRESHOLD = 0.5  # Re-calculate geometry only if sun moves > 0.5 degrees
SENSOR_REFRESH_THRESHOLD = 5.0 # Re-calculate if input changes significantly

def getConvertedValue(hass: HomeAssistant, entityId: str, targetType: str, defaultValue: float = 0.0) -> float:
    """Fetch state and convert to target internal units (Celsius, m/s, W/m2)."""
    if not entityId:
        return defaultValue
    state = hass.states.get(entityId)
    if not state or state.state in ["unavailable", "unknown"]:
        return defaultValue
        
    try:
        val = float(state.state)
        unit = (state.attributes.get("unit_of_measurement") or "").lower().strip()
        
        # 1. TEMPERATURE (Target: Celsius)
        if targetType == "temperature":
            if unit in ["°f", "f"]: 
                return (val - 32) * 5 / 9
            if unit == "k": 
                return val - 273.15
            return val 
            
        # 2. SPEED (Target: m/s)
        if targetType == "speed":
            if unit == "km/h": return val / 3.6
            if unit == "mph": return val / 2.23694
            if unit == "kn": return val / 1.94384
            if unit == "ft/s": return val / 3.28084
            if unit == "bft":
                bftMap = [0, 0.45, 2.45, 4.4, 6.7, 9.35, 12.3, 15.5, 18.95, 22.6, 26.45, 30.55, 32.7]
                index = int(min(max(0, val), 12))
                return bftMap[index]
            return val
            
        # 3. IRRADIANCE (Target: W/m²)
        if targetType == "irradiance":
            if "kw/m" in unit: return val * 1000.0
            return val

        # 4. ILLUMINANCE (Target: lux)
        if targetType == "illuminance":
            return val
            
        return val
    except Exception as e:
        _LOGGER.debug(f"Error converting value for {entityId}: {e}")
        return defaultValue

# --- SENSOR CLASSES ---
class SolarStringSensor(SensorEntity):
    def __init__(self, hass: HomeAssistant, configEntryData: dict[str, Any], db: Any, sensorGroupData: Any):
        self.hass = hass
        self._config = configEntryData
        self._db = db
        self._sensorGroup = sensorGroupData
        
        modelName = self._config.get(CONF_PANEL_MODEL)
        self._panelData = db.data.get(slugify(modelName)) if db and db.data else None
        
        stringNameRaw = self._config.get(CONF_STRING_NAME)
        self._attr_has_entity_name = True
        self._attr_name = f"{stringNameRaw} Potencia"
        self._attr_unique_id = f"str_{slugify(stringNameRaw)}"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {}

        realSensorId = self._config.get(CONF_REAL_PRODUCTION_SENSOR)
        deviceIdentifiers = None
        deviceName = None
        
        # Use the roof hub as via_device when available
        roofHubIdentifier = self._config.get("_roof_hub_identifier")
        
        if realSensorId:
             entityRegistry = er.async_get(hass)
             entityEntry = entityRegistry.async_get(realSensorId)
             if entityEntry and entityEntry.device_id:
                 deviceRegistry = dr.async_get(hass)
                 device = deviceRegistry.async_get(entityEntry.device_id)
                 if device:
                     deviceIdentifiers = device.identifiers

        if not deviceIdentifiers:
            deviceIdentifiers = {(DOMAIN, f"str_{slugify(stringNameRaw)}")}
            deviceName = stringNameRaw

        self._attr_device_info = DeviceInfo(
            identifiers=deviceIdentifiers,
            name=deviceName if not realSensorId else None,
            manufacturer=(self._panelData.brand if self._panelData else "Generic") if not realSensorId else None,
            model=modelName if not realSensorId else None,
            via_device=roofHubIdentifier if roofHubIdentifier else (
                (DOMAIN, self._sensorGroup.name if self._sensorGroup else "Unknown") if not realSensorId else None
            )
        )
        
        # Performance caching
        self._lastSunAzimuth = -100.0
        self._lastSunElevation = -100.0
        self._cachedGeometricFactor = 0.0
        self._cachedCloudInfo = (0.0, "None", 1.0) # (coverage, source, kt)
        self._lastIrradianceRef = -1.0
        self._lastAmbientTemp = -100.0

    @property
    def checkConfig(self) -> bool:
        return self._panelData is not None and self._sensorGroup is not None

    def calculateCosIncidence(self, sunAzimuth: float, sunElevation: float, panelAzimuth: float, panelTilt: float) -> float:
        solZenithRad = math.radians(90 - sunElevation)
        solAzRad = math.radians(sunAzimuth)
        panelTiltRad = math.radians(panelTilt)
        panelAzRad = math.radians(panelAzimuth)
        cosTheta = (math.cos(solZenithRad) * math.cos(panelTiltRad)) + \
                    (math.sin(solZenithRad) * math.sin(panelTiltRad) * math.cos(solAzRad - panelAzRad))
        return max(0, cosTheta)

    @callback
    def _updateLogic(self, event=None):
        if not self.checkConfig: return
        sunState = self.hass.states.get("sun.sun")
        if not sunState: return
        sunAzimuth = float(sunState.attributes.get("azimuth", 180))
        sunElevation = float(sunState.attributes.get("elevation", 0))

        if sunElevation <= 0:
            if self._attr_native_value != 0:
                self._attr_native_value = 0
                self._attr_extra_state_attributes = {"estado_solar": "Noche", "sun_elevation": sunElevation}
                self.async_write_ha_state()
            return

        # 1. Inputs Check
        refSensor = self._sensorGroup.refSensor
        irradianceReference = getConvertedValue(self.hass, refSensor, "irradiance", 0.0)
        ambientTemp = getConvertedValue(self.hass, self._sensorGroup.tempSensor, "temperature", 25.0)
        
        # 2. Geometric & Cloud Update (Throttled)
        sunMoved = (abs(sunAzimuth - self._lastSunAzimuth) > SUN_MOVEMENT_THRESHOLD or 
                     abs(sunElevation - self._lastSunElevation) > SUN_MOVEMENT_THRESHOLD)
        
        if sunMoved:
            targetAzimuth = self._config.get(CONF_AZIMUTH)
            targetTilt = self._config.get(CONF_TILT)
            cosThetaTarget = self.calculateCosIncidence(sunAzimuth, sunElevation, targetAzimuth, targetTilt)
            cosThetaRef = self.calculateCosIncidence(sunAzimuth, sunElevation, self._sensorGroup.refOrientation, self._sensorGroup.refTilt)
            
            try:
                self._cachedGeometricFactor = 0 if cosThetaRef < 0.05 else cosThetaTarget / cosThetaRef
            except ZeroDivisionError:
                self._cachedGeometricFactor = 0

            # Cloud & KT calculation (also depends on sunElevation)
            ktFactor, cloudSource, cloudCoverage = 1.0, "None", 0.0
            illSensor = self._sensorGroup.illuminanceSensor
            if illSensor:
                luxReal = getConvertedValue(self.hass, illSensor, "illuminance", -1)
                if luxReal >= 0 and sunElevation > 2:
                    luxTheoretical = 120000 * math.sin(math.radians(sunElevation))
                    if luxTheoretical > 10:
                        try:
                            ktFactor = max(0.05, min(1.2, luxReal / luxTheoretical))
                            cloudCoverage = max(0, min(100, 100 * (1 - ktFactor)))
                            cloudSource = "Lux Sensor"
                        except ZeroDivisionError: pass
            
            if cloudSource == "None":
                weatherEntity = self._sensorGroup.weatherEntity
                if weatherEntity:
                    weatherState = self.hass.states.get(weatherEntity)
                    if weatherState and weatherState.state not in ["unavailable", "unknown"]:
                        if weatherState.domain == "sensor":
                            try: cloudCoverage = float(weatherState.state)
                            except: pass
                        elif weatherState.domain == "weather":
                            c = weatherState.attributes.get("cloud_coverage")
                            if c is not None:
                               try: cloudCoverage = float(c)
                               except: pass
                            else:
                                condition = weatherState.state
                                if condition in ["sunny", "clear-night"]: cloudCoverage = 0
                                elif condition in ["partlycloudy"]: cloudCoverage = 40
                                elif condition in ["cloudy"]: cloudCoverage = 90
                                else: cloudCoverage = 100
                        ktFactor = 1.0 - (cloudCoverage / 100.0)
                        cloudSource = "Weather Entity"
            
            self._cachedCloudInfo = (cloudCoverage, cloudSource, ktFactor)
            self._lastSunAzimuth, self._lastSunElevation = sunAzimuth, sunElevation

        # 3. Final Power Calculation (Always uses current inputs)
        cloudCoverage, cloudSource, ktFactor = self._cachedCloudInfo
        kCoeff = 0.1 + (0.8 * (cloudCoverage / 100.0))
        combinedFactor = ((1 - kCoeff) * self._cachedGeometricFactor) + (kCoeff * 1.0)
        irradianceTarget = irradianceReference * combinedFactor

        try:
            pSTC = self._panelData.pStc if self._panelData else 450
            gammaVal = (self._panelData.gamma if self._panelData else -0.35) / 100.0
            noctVal = self._panelData.noct if self._panelData else 45
            
            cellTemperature = ambientTemp + (irradianceTarget / 800) * (noctVal - 20)
            powerUnit = pSTC * (irradianceTarget / 1000.0) * (1 + (gammaVal * (cellTemperature - 25)))
            totalPower = max(0, powerUnit * self._config.get(CONF_NUM_PANELS, 1) * self._config.get(CONF_NUM_STRINGS, 1))
        except Exception as e:
            _LOGGER.error(f"Error calculating solar power for {self.name}: {e}")
            totalPower, irradianceTarget, cellTemperature = 0, 0, ambientTemp

        self._attr_native_value = round(totalPower, 2)
        self._attr_extra_state_attributes = {
            "irradiancia_incidente_estimada": round(irradianceTarget, 1),
            "factor_transposicion": round(self._cachedGeometricFactor, 3), # FIXED BUG HERE
            "temperatura_celula": round(cellTemperature, 1),
            "cloud_coverage_estimated": round(cloudCoverage, 1),
            "cloud_source": cloudSource
        }
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Suscribirse a actualizaciones."""
        entities = ["sun.sun", self._sensorGroup.refSensor, self._sensorGroup.tempSensor]
        if self._sensorGroup.weatherEntity: entities.append(self._sensorGroup.weatherEntity)
        if self._sensorGroup.illuminanceSensor: entities.append(self._sensorGroup.illuminanceSensor)
        self.async_on_remove(async_track_state_change_event(self.hass, entities, self._updateLogic))

class SensorGroupVirtualSensor(SensorEntity):
    def __init__(self, hass, configEntry, targetDeviceIdentifiers=None):
        self.hass = hass
        self._config = configEntry.data
        self._name = self._config.get(CONF_SENSOR_GROUP_NAME)
        self._attr_name = self._name
        self._attr_unique_id = f"sg_{slugify(self._name)}_status"
        self._attr_icon = "mdi:link-variant"
        
        if targetDeviceIdentifiers:
            self._attr_device_info = DeviceInfo(identifiers=targetDeviceIdentifiers)
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, configEntry.entry_id)},
                name=self._name,
                manufacturer="Accurate Solar Forecast",
                model="Sensor Group",
                entry_type=dr.DeviceEntryType.SERVICE
            )

    async def async_added_to_hass(self) -> None:
        sensors = [v for k,v in self._config.items() if "sensor" in k or k == CONF_WEATHER_ENTITY]
        self.async_on_remove(async_track_state_change_event(self.hass, sensors, self._updateState))
        self._updateState()

    @callback
    def _updateState(self, event: Any = None) -> None:
        attributes = {}
        status = "OK"
        for k, attr in [(CONF_REF_SENSOR, "irradiance"), (CONF_TEMP_SENSOR, "temperature")]:
            entityId = self._config.get(k)
            if entityId:
                state = self.hass.states.get(entityId)
                if state:
                    attributes[attr] = state.state
                    if state.state in ["unavailable", "unknown"]: status = "Partial"
                else: status = "Error"
        
        if attributes.get("irradiance") in ["unavailable", "unknown", None]: status = "Unavailable"
        self._attr_native_value = status
        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()

class SensorGroupCloudinessSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "cloud_coverage"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cloud-percent"

    def __init__(self, hass: HomeAssistant, configEntry: Any, targetDeviceIdentifiers: Any = None):
        self.hass = hass
        self._config = configEntry.data
        self._name = self._config.get(CONF_SENSOR_GROUP_NAME)
        self._attr_unique_id = f"sg_{slugify(self._name)}_cloudiness"
        self._attr_device_info = DeviceInfo(identifiers=targetDeviceIdentifiers) if targetDeviceIdentifiers else DeviceInfo(
            identifiers={(DOMAIN, configEntry.entry_id)}, name=self._name, entry_type=dr.DeviceEntryType.SERVICE
        )
        self._lastSunElevation = -100.0
        self._cachedValue = 0.0

    async def async_added_to_hass(self):
        entities = ["sun.sun"]
        if self._config.get(CONF_ILLUMINANCE_SENSOR): entities.append(self._config[CONF_ILLUMINANCE_SENSOR])
        if self._config.get(CONF_WEATHER_ENTITY): entities.append(self._config[CONF_WEATHER_ENTITY])
        self.async_on_remove(async_track_state_change_event(self.hass, entities, self._updateLogic))
        self._updateLogic()

    @callback
    def _updateLogic(self, event=None):
        sunState = self.hass.states.get("sun.sun")
        if not sunState: return
        sunElevation = float(sunState.attributes.get("elevation", 0))
        
        # Throttling
        if abs(sunElevation - self._lastSunElevation) < SUN_MOVEMENT_THRESHOLD:
            # Check if source sensors changed (if event is from a sensor change, we should probably re-calc)
            if event and event.data.get("entity_id") == "sun.sun":
                return

        cloudCoverage = 0.0
        if sunElevation > 0:
            illSensor = self._config.get(CONF_ILLUMINANCE_SENSOR)
            if illSensor:
                luxReal = getConvertedValue(self.hass, illSensor, "illuminance", -1)
                if luxReal >= 0 and sunElevation > 2:
                    luxTheoretical = 120000 * math.sin(math.radians(sunElevation))
                    if luxTheoretical > 10:
                        cloudCoverage = max(0, min(100, 100 * (1 - (luxReal / luxTheoretical))))
        
        self._lastSunElevation = sunElevation
        self._attr_native_value = round(cloudCoverage, 1)
        self.async_write_ha_state()

class SolarStringPerformanceSensor(SensorEntity):
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-line"

    def __init__(self, hass, configEntryData, db, sensorGroupData):
        self.hass = hass
        self._config = configEntryData
        self._stringName = self._config.get(CONF_STRING_NAME)
        self._attr_has_entity_name = True
        self._attr_name = f"{self._stringName} Rendimiento"
        self._attr_unique_id = f"str_{slugify(self._stringName)}_performance"
        realSensorId = self._config.get(CONF_REAL_PRODUCTION_SENSOR)
        deviceIdentifiers = None
        if realSensorId:
             entityEntry = er.async_get(hass).async_get(realSensorId)
             if entityEntry and entityEntry.device_id:
                 device = dr.async_get(hass).async_get(entityEntry.device_id)
                 if device: deviceIdentifiers = device.identifiers
        self._attr_device_info = DeviceInfo(identifiers=deviceIdentifiers or {(DOMAIN, f"str_{slugify(self._stringName)}")})
        self.realSensorId = realSensorId

    async def async_added_to_hass(self):
        if self.realSensorId:
            self.async_on_remove(async_track_state_change_event(self.hass, [self.realSensorId], self._updateState))
        
    @callback
    def _updateState(self, event=None):
        if not self.realSensorId: return
        realState = self.hass.states.get(self.realSensorId)
        if not realState or realState.state in ["unavailable", "unknown"]: return
        try: realValue = float(realState.state)
        except: return
        siblingUniqueId = f"str_{slugify(self._stringName)}"
        siblingEntry = er.async_get(self.hass).async_get_entity_id("sensor", DOMAIN, siblingUniqueId)
        forecastValue = 1 
        if siblingEntry:
            sState = self.hass.states.get(siblingEntry)
            if sState and sState.state not in ["unavailable", "unknown"]:
                try: forecastValue = float(sState.state)
                except: pass
        if forecastValue < 1: forecastValue = 1
        self._attr_native_value = round((realValue / forecastValue) * 100, 1)
        self.async_write_ha_state()

class AccurateSolarSensorDBSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "pv_db_status"
    _attr_unique_id = "pv_database_status"
    _attr_icon = "mdi:database"
    _attr_native_unit_of_measurement = "items"

    def __init__(self, hass, db):
        self.hass = hass
        self._db = db
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "pv_models_library")},
        )
        models = self._db.listModels()
        self._attr_native_value = len(models)

    def _updateState(self):
        models = self._db.listModels()
        self._attr_native_value = len(models)
        if self.hass and self.entity_id:
            self.async_write_ha_state()
    
    async def async_added_to_hass(self):
        self._updateState()


class PVModelCountSensor(SensorEntity):
    """Sensor showing the number of saved PV panel models in the database."""
    _attr_has_entity_name = True
    _attr_unique_id = "pv_model_count"
    _attr_icon = "mdi:solar-panel"
    _attr_native_unit_of_measurement = "models"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_name = "Modelos guardados"

    def __init__(self, hass: HomeAssistant, db: Any):
        self.hass = hass
        self._db = db
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "pv_models_library")},
        )
        self._attr_native_value = len(self._db.listModels()) if self._db else 0

    @property
    def native_value(self) -> int:
        return len(self._db.listModels()) if self._db else 0

    async def async_update(self) -> None:
        """HA will poll this sensor; DB updates are in-memory."""
        self._attr_native_value = len(self._db.listModels()) if self._db else 0
