from typing import Any, Optional, Coroutine
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from ..variables.const import *
from ..core import slugify, PvModel, Roof, SensorGroup, SolarString
import logging

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "accurate_solar_forecast_data"

class AccurateSolarSensorDB:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, PvModel] = {}
        self.sensor_groups: dict[str, SensorGroup] = {}

    async def async_load(self) -> None:
        """Load DB from disk."""
        _LOGGER.info(f"DB: Loading storage key '{STORAGE_KEY}' from HA .storage...")
        data = await self._store.async_load()
        if data is None:

            # Default data if completely empty
            defName = "Generico 450W"
            self.data = {
                slugify(defName): PvModel.from_dict({
                    "name": defName,
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
            await self.async_save()
        else:
            modelsRaw = data.get("models", {})
            self.data = {k: PvModel.from_dict(v) for k, v in modelsRaw.items() if isinstance(v, dict)}
            
            groupsRaw = data.get("sensor_groups", {})
            self.sensor_groups = {k: SensorGroup.from_dict(v) for k, v in groupsRaw.items() if isinstance(v, dict)}


    async def async_save(self) -> None:
        """Guarda la DB al disco serializando los objetos a diccionarios."""
        _LOGGER.info(f"DB: Saving data to HA storage (key: {STORAGE_KEY})...")

        saveData = {
            "models": {k: v.to_dict() for k, v in self.data.items()},
            "sensor_groups": {k: v.to_dict() for k, v in self.sensor_groups.items()},
        }
        await self._store.async_save(saveData)
        _LOGGER.info("DB: Save completed successfully.")

    async def async_clear(self) -> None:
        """Wipe all data and delete the storage file content."""
        self.data = {}
        self.sensor_groups = {}
        await self._store.async_remove()
        _LOGGER.warning("DATABASE WIPED: storage file deleted from .storage.")

    # --- PV MODEL METHODS ---
    async def addModel(self, name: str, brand: str, pStc: float, gamma: float, noct: float, voc: float, isc: float, vmp: float, imp: float) -> None:
        modelId = slugify(name)
        self.data[modelId] = PvModel(
            name=name, brand=brand, pStc=float(pStc), gamma=float(gamma),
            noct=float(noct), voc=float(voc), isc=float(isc), vmp=float(vmp), imp=float(imp)
        )
        await self.async_save()

    async def deleteModel(self, modelId: str) -> bool:
        """Elimina un modelo de la DB."""
        if modelId == slugify("Generico 450W"):
            return False
        if modelId in self.data:
            del self.data[modelId]
            await self.async_save()
            return True
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
    async def addSensorGroup(self, name: str, irradianceSensor: str, tempSensor: str, tempPanelSensor: Optional[str], windSensor: Optional[str], refTilt: float, refOrientation: float, weatherEntity: Optional[str] = None, illuminanceSensor: Optional[str] = None) -> str:
        groupId = slugify(name)
        self.sensor_groups[groupId] = SensorGroup(
            name=name,
            refSensor=irradianceSensor,
            refTilt=float(refTilt),
            refOrientation=float(refOrientation),
            tempSensor=tempSensor,
            tempPanelSensor=tempPanelSensor,
            windSensor=windSensor,
            weatherEntity=weatherEntity,
            illuminanceSensor=illuminanceSensor
        )
        await self.async_save()
        return groupId
        
    def getSensorGroup(self, groupId: str) -> Optional[SensorGroup]:
        return self.sensor_groups.get(groupId)

    def listSensorGroups(self) -> dict[str, str]:
        """Devuelve dict {id: nombre} para selectores."""
        return {k: v.name for k, v in self.sensor_groups.items()}
    
    async def deleteSensorGroup(self, groupId: str) -> bool:
        if groupId in self.sensor_groups:
            del self.sensor_groups[groupId]
            await self.async_save()
            return True
        return False
