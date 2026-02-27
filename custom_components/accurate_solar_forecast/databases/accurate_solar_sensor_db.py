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
            modelsRaw = data.get("models", {})
            # Migration check: if "models" is empty but data has values, it might be old structure
            if not modelsRaw and data:
                 if "default_450w" in data or any("brand" in v for v in data.values()):
                     modelsRaw = data
            
            self.data = {k: PvModel.from_dict(v) for k, v in modelsRaw.items() if isinstance(v, dict)}
            
            groupsRaw = data.get("sensor_groups", {})
            self.sensor_groups = {k: SensorGroup.from_dict(v) for k, v in groupsRaw.items() if isinstance(v, dict)}
            
            roofsRaw = data.get("roofs", {})
            self.roofs = {k: Roof.from_dict(v) for k, v in roofsRaw.items() if isinstance(v, dict)}
            
            # Save if we cleared old "default" roofs or fixed structure
            await self.async_save()

    async def async_save(self) -> None:
        """Guarda la DB al disco serializando los objetos a diccionarios."""
        saveData = {
            "models": {k: v.to_dict() for k, v in self.data.items()},
            "sensor_groups": {k: v.to_dict() for k, v in self.sensor_groups.items()},
            "roofs": {k: v.to_dict() for k, v in self.roofs.items()}
        }
        await self._store.async_save(saveData)

    # --- ROOF METHODS ---
    def addRoof(self, name: str, tilt: Optional[float] = None, azimuth: Optional[float] = None, strings: Optional[dict[str, SolarString]] = None) -> Coroutine:
        """Adds a roof to the database."""
        roofId = slugify(name)
        existing = self.roofs.get(roofId)
        
        self.roofs[roofId] = Roof(
            name=name,
            tilt=float(tilt) if tilt is not None else (existing.tilt if existing else 30.0),
            azimuth=float(azimuth) if azimuth is not None else (existing.azimuth if existing else 180.0),
            strings=strings if strings is not None else (existing.strings if existing else {})
        )
        return self.async_save()

    def addStringToRoof(self, roofId: str, stringId: str, stringData: Any) -> Coroutine | bool:
        if roofId in self.roofs:
            if isinstance(stringData, dict):
                 stringData = SolarString.from_dict(stringData)
            self.roofs[roofId].strings[stringId] = stringData
            return self.async_save()
        return False
        
    def deleteStringFromRoof(self, roofId: str, stringId: str) -> Coroutine | bool:
        if roofId in self.roofs:
            if stringId in self.roofs[roofId].strings:
                del self.roofs[roofId].strings[stringId]
                return self.async_save()
        return False
        
    def getRoofStrings(self, roofId) -> dict[str, SolarString]:
        roof = self.roofs.get(roofId)
        return roof.strings if roof else {}

    def listRoofs(self) -> dict[str, str]:
        """Returns a dict {id: name} of roofs."""
        return {k: v.name for k, v in self.roofs.items()}
    
    def getRoof(self, roofId: str) -> Optional[Roof]:
        return self.roofs.get(roofId)

    def deleteRoof(self, roofId: str) -> Coroutine | bool:
        """Removes a roof from the database."""
        if roofId in self.roofs:
            del self.roofs[roofId]
            return self.async_save()
        return False

    # --- PV MODEL METHODS ---
    def addModel(self, name: str, brand: str, pStc: float, gamma: float, noct: float, voc: float, isc: float, vmp: float, imp: float) -> Coroutine:
        modelId = slugify(name)
        self.data[modelId] = PvModel(
            name=name, brand=brand, pStc=float(pStc), gamma=float(gamma),
            noct=float(noct), voc=float(voc), isc=float(isc), vmp=float(vmp), imp=float(imp)
        )
        return self.async_save()

    async def deleteModel(self, modelId: str) -> bool:
        """Elimina un modelo de la DB."""
        if modelId == "default_450w":
            return False
        if modelId in self.data:
            del self.data[modelId]
            return await self.async_save()
        return False

    def getModel(self, modelId: str) -> Optional[PvModel]:
        return self.data.get(modelId)

    def listBrands(self) -> list[str]:
        """Devuelve lista de marcas únicas."""
        brands = {v.brand for v in self.data.values()}
        return sorted(list(brands)) if brands else ["Generic"]

    def listModelsByBrand(self, brand: str) -> dict[str, str]:
        """Devuelve dict {id: nombre} filtrado por marca."""
        return {
            k: v.name 
            for k, v in self.data.items() 
            if v.brand == brand
        }

    def listModels(self) -> dict[str, str]:
        """Devuelve dict {id: nombre} para el selector."""
        return {k: v.name for k, v in self.data.items()}

    # --- SENSOR GROUP METHODS ---
    def addSensorGroup(self, name: str, irradianceSensor: str, tempSensor: str, tempPanelSensor: Optional[str], windSensor: Optional[str], refTilt: float, refOrientation: float, weatherEntity: Optional[str] = None, illuminanceSensor: Optional[str] = None) -> Coroutine:
        groupId = slugify(name)
        self.sensor_groups[groupId] = SensorGroup(
            name=name,
            ref_sensor=irradianceSensor,
            ref_tilt=float(refTilt),
            ref_orientation=float(refOrientation),
            temp_sensor=tempSensor,
            temp_panel_sensor=tempPanelSensor,
            wind_sensor=windSensor,
            weather_entity=weatherEntity,
            illuminance_sensor=illuminanceSensor
        )
        return self.async_save()
        
    def getSensorGroup(self, groupId: str) -> Optional[SensorGroup]:
        return self.sensor_groups.get(groupId)

    def listSensorGroups(self) -> dict[str, str]:
        """Devuelve dict {id: nombre} para selectores."""
        return {k: v.name for k, v in self.sensor_groups.items()}
    
    def deleteSensorGroup(self, groupId: str) -> Coroutine | bool:
        if groupId in self.sensor_groups:
            del self.sensor_groups[groupId]
            return self.async_save()
        return False
