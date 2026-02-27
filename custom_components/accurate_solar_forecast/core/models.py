"""Data models for Accurate Solar Forecast."""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional

@dataclass
class PvModel:
    """Represents a Photovoltaic Panel model."""
    name: str
    brand: str
    pStc: float
    gamma: float
    noct: float
    voc: float
    isc: float
    vmp: float
    imp: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PvModel":
        """Create a PvModel from a dictionary."""
        return cls(
            name=data.get("name", "Generic"),
            brand=data.get("brand", "Generic"),
            pStc=float(data.get("p_stc", 450)),
            gamma=float(data.get("gamma", -0.35)),
            noct=float(data.get("noct", 45)),
            voc=float(data.get("voc", 49.0)),
            isc=float(data.get("isc", 11.5)),
            vmp=float(data.get("vmp", 41.5)),
            imp=float(data.get("imp", 10.85)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "brand": self.brand,
            "p_stc": self.pStc,
            "gamma": self.gamma,
            "noct": self.noct,
            "voc": self.voc,
            "isc": self.isc,
            "vmp": self.vmp,
            "imp": self.imp
        }

@dataclass
class SolarString:
    """Represents a string of PV panels."""
    name: str
    panelModel: str
    numPanels: int
    numStrings: int
    tilt: float
    azimuth: float
    selectedSensorGroup: str
    realProductionSensor: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SolarString":
        return cls(
            name=data.get("name", "Unknown String"),
            panelModel=data.get("panel_model", "Generic"),
            numPanels=int(data.get("num_panels", 1)),
            numStrings=int(data.get("num_strings", 1)),
            tilt=float(data.get("tilt", 30.0)),
            azimuth=float(data.get("azimuth", 180.0)),
            selectedSensorGroup=data.get("selected_sensor_group", ""),
            realProductionSensor=data.get("real_production_sensor"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "panel_model": self.panelModel,
            "num_panels": self.numPanels,
            "num_strings": self.numStrings,
            "tilt": self.tilt,
            "azimuth": self.azimuth,
            "selected_sensor_group": self.selectedSensorGroup,
            "real_production_sensor": self.realProductionSensor
        }

@dataclass
class Roof:
    """Represents a roof containing multiple solar strings."""
    name: str
    tilt: float
    azimuth: float
    strings: Dict[str, SolarString] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Roof":
        strings_data = data.get("strings", {})
        strings = {k: SolarString.from_dict(v) for k, v in strings_data.items()}
        return cls(
            name=data.get("name", "Generic Roof"),
            tilt=float(data.get("tilt", 30.0)),
            azimuth=float(data.get("azimuth", 180.0)),
            strings=strings,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "tilt": self.tilt,
            "azimuth": self.azimuth,
            "strings": {k: asdict(v) for k, v in self.strings.items()}
        }

@dataclass
class SensorGroup:
    """Represents a physical sensor group (irradiance, temp, etc)."""
    name: str
    refSensor: str
    refTilt: float
    refOrientation: float
    tempSensor: str
    tempPanelSensor: Optional[str] = None
    windSensor: Optional[str] = None
    weatherEntity: Optional[str] = None
    illuminanceSensor: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SensorGroup":
        from ..variables.const import (
            CONF_SENSOR_GROUP_NAME, CONF_REF_SENSOR, CONF_REF_TILT, 
            CONF_REF_ORIENTATION, CONF_TEMP_SENSOR, CONF_WIND_SENSOR, 
            CONF_TEMP_PANEL_SENSOR, CONF_WEATHER_ENTITY, CONF_ILLUMINANCE_SENSOR
        )
        return cls(
            name=data.get(CONF_SENSOR_GROUP_NAME, "Default Group"),
            refSensor=data.get(CONF_REF_SENSOR, ""),
            refTilt=float(data.get(CONF_REF_TILT, 0.0)),
            refOrientation=float(data.get(CONF_REF_ORIENTATION, 180.0)),
            tempSensor=data.get(CONF_TEMP_SENSOR, ""),
            tempPanelSensor=data.get(CONF_TEMP_PANEL_SENSOR),
            windSensor=data.get(CONF_WIND_SENSOR),
            weatherEntity=data.get(CONF_WEATHER_ENTITY),
            illuminanceSensor=data.get(CONF_ILLUMINANCE_SENSOR),
        )

    def to_dict(self) -> Dict[str, Any]:
        from ..variables.const import (
            CONF_SENSOR_GROUP_NAME, CONF_REF_SENSOR, CONF_REF_TILT, 
            CONF_REF_ORIENTATION, CONF_TEMP_SENSOR, CONF_WIND_SENSOR, 
            CONF_TEMP_PANEL_SENSOR, CONF_WEATHER_ENTITY, CONF_ILLUMINANCE_SENSOR
        )
        return {
            CONF_SENSOR_GROUP_NAME: self.name,
            CONF_REF_SENSOR: self.refSensor,
            CONF_REF_TILT: self.refTilt,
            CONF_REF_ORIENTATION: self.refOrientation,
            CONF_TEMP_SENSOR: self.tempSensor,
            CONF_TEMP_PANEL_SENSOR: self.tempPanelSensor,
            CONF_WIND_SENSOR: self.windSensor,
            CONF_WEATHER_ENTITY: self.weatherEntity,
            CONF_ILLUMINANCE_SENSOR: self.illuminanceSensor,
        }
