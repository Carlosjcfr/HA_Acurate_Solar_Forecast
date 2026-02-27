"""Data models for Accurate Solar Forecast."""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional

@dataclass
class PvModel:
    """Represents a Photovoltaic Panel model."""
    name: str
    brand: str
    p_stc: float
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
            p_stc=float(data.get("p_stc", 450)),
            gamma=float(data.get("gamma", -0.35)),
            noct=float(data.get("noct", 45)),
            voc=float(data.get("voc", 49.0)),
            isc=float(data.get("isc", 11.5)),
            vmp=float(data.get("vmp", 41.5)),
            imp=float(data.get("imp", 10.85)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

@dataclass
class SolarString:
    """Represents a string of PV panels."""
    name: str
    panel_model: str
    num_panels: int
    num_strings: int
    tilt: float
    azimuth: float
    selected_sensor_group: str
    real_production_sensor: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SolarString":
        return cls(
            name=data.get("name", "Unknown String"),
            panel_model=data.get("panel_model", "Generic"),
            num_panels=int(data.get("num_panels", 1)),
            num_strings=int(data.get("num_strings", 1)),
            tilt=float(data.get("tilt", 30.0)),
            azimuth=float(data.get("azimuth", 180.0)),
            selected_sensor_group=data.get("selected_sensor_group", ""),
            real_production_sensor=data.get("real_production_sensor"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

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
    ref_sensor: str
    ref_tilt: float
    ref_orientation: float
    temp_sensor: str
    temp_panel_sensor: Optional[str] = None
    wind_sensor: Optional[str] = None
    weather_entity: Optional[str] = None
    illuminance_sensor: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SensorGroup":
        from ..variables.const import (
            CONF_SENSOR_GROUP_NAME, CONF_REF_SENSOR, CONF_REF_TILT, 
            CONF_REF_ORIENTATION, CONF_TEMP_SENSOR, CONF_WIND_SENSOR, 
            CONF_TEMP_PANEL_SENSOR, CONF_WEATHER_ENTITY, CONF_ILLUMINANCE_SENSOR
        )
        return cls(
            name=data.get(CONF_SENSOR_GROUP_NAME, "Default Group"),
            ref_sensor=data.get(CONF_REF_SENSOR, ""),
            ref_tilt=float(data.get(CONF_REF_TILT, 0.0)),
            ref_orientation=float(data.get(CONF_REF_ORIENTATION, 180.0)),
            temp_sensor=data.get(CONF_TEMP_SENSOR, ""),
            temp_panel_sensor=data.get(CONF_TEMP_PANEL_SENSOR),
            wind_sensor=data.get(CONF_WIND_SENSOR),
            weather_entity=data.get(CONF_WEATHER_ENTITY),
            illuminance_sensor=data.get(CONF_ILLUMINANCE_SENSOR),
        )

    def to_dict(self) -> Dict[str, Any]:
        from ..variables.const import (
            CONF_SENSOR_GROUP_NAME, CONF_REF_SENSOR, CONF_REF_TILT, 
            CONF_REF_ORIENTATION, CONF_TEMP_SENSOR, CONF_WIND_SENSOR, 
            CONF_TEMP_PANEL_SENSOR, CONF_WEATHER_ENTITY, CONF_ILLUMINANCE_SENSOR
        )
        return {
            CONF_SENSOR_GROUP_NAME: self.name,
            CONF_REF_SENSOR: self.ref_sensor,
            CONF_REF_TILT: self.ref_tilt,
            CONF_REF_ORIENTATION: self.ref_orientation,
            CONF_TEMP_SENSOR: self.temp_sensor,
            CONF_TEMP_PANEL_SENSOR: self.temp_panel_sensor,
            CONF_WIND_SENSOR: self.wind_sensor,
            CONF_WEATHER_ENTITY: self.weather_entity,
            CONF_ILLUMINANCE_SENSOR: self.illuminance_sensor,
        }
