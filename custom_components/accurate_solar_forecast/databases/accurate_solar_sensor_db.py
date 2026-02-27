from typing import Any, Optional, Coroutine
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from ..variables.const import *
from ..core import slugify, PvModel, Roof, SensorGroup, SolarString
import logging

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "accurate_forecast_pv_models"

class AccurateSolarSensorDB:
    def __init__(self, hass: HomeAssistant):
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, PvModel] = {}
        self.sensor_groups: dict[str, SensorGroup] = {}
        self.roofs: dict[str, Roof] = {}

    async def async_load(self) -> None:
        """Carga la DB del disco."""
        data = await self._store.async_load()
        if data is None:
            # Datos por defecto si está vacío
            self.data = {
                "default_450w": PvModel.from_dict({
                    "name": "Generico 450W",
                    "brand": "Generic",
                    "p_stc": 450,
                    "gamma": -0.35,
                    "noct": 45,
                    "voc": 49.0,
                    "isc": 11.5,
                    "vmp": 41.5,
                    "imp": 10.85
                })
            }
            self.sensor_groups = {}
            self.roofs = {}
            await self.async_save()
        else:
            models_raw = data.get("models", {})
            # Migration check: if "models" is empty but data has values, it might be old structure
            if not models_raw and data:
                 if "default_450w" in data or any("brand" in v for v in data.values()):
                     models_raw = data
            
            self.data = {k: PvModel.from_dict(v) for k, v in models_raw.items() if isinstance(v, dict)}
            
            groups_raw = data.get("sensor_groups", {})
            self.sensor_groups = {k: SensorGroup.from_dict(v) for k, v in groups_raw.items() if isinstance(v, dict)}
            
            roofs_raw = data.get("roofs", {})
            self.roofs = {k: Roof.from_dict(v) for k, v in roofs_raw.items() if isinstance(v, dict)}
            
            # Save if we cleared old "default" roofs or fixed structure
            await self.async_save()

    async def async_save(self) -> None:
        """Guarda la DB al disco serializando los objetos a diccionarios."""
        save_data = {
            "models": {k: v.to_dict() for k, v in self.data.items()},
            "sensor_groups": {k: v.to_dict() for k, v in self.sensor_groups.items()},
            "roofs": {k: v.to_dict() for k, v in self.roofs.items()}
        }
        await self._store.async_save(save_data)

    # --- ROOF METHODS ---
    def add_roof(self, name: str, tilt: Optional[float] = None, azimuth: Optional[float] = None, strings: Optional[dict[str, SolarString]] = None) -> Coroutine:
        """Adds a roof to the database."""
        roof_id = slugify(name)
        existing = self.roofs.get(roof_id)
        
        self.roofs[roof_id] = Roof(
            name=name,
            tilt=float(tilt) if tilt is not None else (existing.tilt if existing else 30.0),
            azimuth=float(azimuth) if azimuth is not None else (existing.azimuth if existing else 180.0),
            strings=strings if strings is not None else (existing.strings if existing else {})
        )
        return self.async_save()

    def add_string_to_roof(self, roof_id: str, string_id: str, string_data: Any) -> Coroutine | bool:
        if roof_id in self.roofs:
            if isinstance(string_data, dict):
                 string_data = SolarString.from_dict(string_data)
            self.roofs[roof_id].strings[string_id] = string_data
            return self.async_save()
        return False
        
    def delete_string_from_roof(self, roof_id: str, string_id: str) -> Coroutine | bool:
        if roof_id in self.roofs:
            if string_id in self.roofs[roof_id].strings:
                del self.roofs[roof_id].strings[string_id]
                return self.async_save()
        return False
        
    def get_roof_strings(self, roof_id) -> dict[str, SolarString]:
        roof = self.roofs.get(roof_id)
        return roof.strings if roof else {}

    def list_roofs(self) -> dict[str, str]:
        """Returns a dict {id: name} of roofs."""
        return {k: v.name for k, v in self.roofs.items()}
    
    def get_roof(self, roof_id: str) -> Optional[Roof]:
        return self.roofs.get(roof_id)

    def delete_roof(self, roof_id: str) -> Coroutine | bool:
        """Removes a roof from the database."""
        if roof_id in self.roofs:
            del self.roofs[roof_id]
            return self.async_save()
        return False

    # --- PV MODEL METHODS ---
    def add_model(self, name: str, brand: str, p_stc: float, gamma: float, noct: float, voc: float, isc: float, vmp: float, imp: float) -> Coroutine:
        model_id = slugify(name)
        self.data[model_id] = PvModel(
            name=name, brand=brand, p_stc=float(p_stc), gamma=float(gamma),
            noct=float(noct), voc=float(voc), isc=float(isc), vmp=float(vmp), imp=float(imp)
        )
        return self.async_save()

    async def delete_model(self, model_id: str) -> bool:
        """Elimina un modelo de la DB."""
        if model_id == "default_450w":
            return False
        if model_id in self.data:
            del self.data[model_id]
            return await self.async_save()
        return False

    def get_model(self, model_id: str) -> Optional[PvModel]:
        return self.data.get(model_id)

    def list_brands(self) -> list[str]:
        """Devuelve lista de marcas únicas."""
        brands = {v.brand for v in self.data.values()}
        return sorted(list(brands)) if brands else ["Generic"]

    def list_models_by_brand(self, brand: str) -> dict[str, str]:
        """Devuelve dict {id: nombre} filtrado por marca."""
        return {
            k: v.name 
            for k, v in self.data.items() 
            if v.brand == brand
        }

    def list_models(self) -> dict[str, str]:
        """Devuelve dict {id: nombre} para el selector."""
        return {k: v.name for k, v in self.data.items()}

    # --- SENSOR GROUP METHODS ---
    def add_sensor_group(self, name: str, irradiance_sensor: str, temp_sensor: str, temp_panel_sensor: Optional[str], wind_sensor: Optional[str], ref_tilt: float, ref_orientation: float, weather_entity: Optional[str] = None, illuminance_sensor: Optional[str] = None) -> Coroutine:
        group_id = slugify(name)
        self.sensor_groups[group_id] = SensorGroup(
            name=name,
            ref_sensor=irradiance_sensor,
            ref_tilt=float(ref_tilt),
            ref_orientation=float(ref_orientation),
            temp_sensor=temp_sensor,
            temp_panel_sensor=temp_panel_sensor,
            wind_sensor=wind_sensor,
            weather_entity=weather_entity,
            illuminance_sensor=illuminance_sensor
        )
        return self.async_save()
        
    def get_sensor_group(self, group_id: str) -> Optional[SensorGroup]:
        return self.sensor_groups.get(group_id)

    def list_sensor_groups(self) -> dict[str, str]:
        """Devuelve dict {id: nombre} para selectores."""
        return {k: v.name for k, v in self.sensor_groups.items()}
    
    def delete_sensor_group(self, group_id: str) -> Coroutine | bool:
        if group_id in self.sensor_groups:
            del self.sensor_groups[group_id]
            return self.async_save()
        return False
