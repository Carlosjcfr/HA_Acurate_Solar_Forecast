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
        self.roofs: dict[str, Roof] = {}

    async def async_load(self) -> None:
        """Load DB from disk."""
        # Check if we are in a middle of a removal to avoid recreating after a wipe
        if self.hass.data.get(DOMAIN, {}).get("is_removing_all"):
            _LOGGER.debug("DB async_load: skip load because global removal is in progress")
            return

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
            self.roofs = {}
            await self.async_save()
        else:
            modelsRaw = data.get("models", {})
            self.data = {k: PvModel.from_dict(v) for k, v in modelsRaw.items() if isinstance(v, dict)}
            
            groupsRaw = data.get("sensor_groups", {})
            self.sensor_groups = {k: SensorGroup.from_dict(v) for k, v in groupsRaw.items() if isinstance(v, dict)}
            
            roofsRaw = data.get("roofs", {})
            self.roofs = {k: Roof.from_dict(v) for k, v in roofsRaw.items() if isinstance(v, dict)}


    async def async_save(self) -> None:
        """Guarda la DB al disco serializando los objetos a diccionarios."""
        if self.hass.data.get(DOMAIN, {}).get("is_removing_all"):
            _LOGGER.debug("DB async_save: skip save because global removal is in progress")
            return

        saveData = {
            "models": {k: v.to_dict() for k, v in self.data.items()},
            "sensor_groups": {k: v.to_dict() for k, v in self.sensor_groups.items()},
            "roofs": {k: v.to_dict() for k, v in self.roofs.items()}
        }
        await self._store.async_save(saveData)

    async def async_clear(self) -> None:
        """Wipe all data and delete the storage file content."""
        # Force the flag in hass data to block parallel saves/loads
        self.hass.data.setdefault(DOMAIN, {})["is_removing_all"] = True
        
        self.data = {}
        self.sensor_groups = {}
        self.roofs = {}
        await self._store.async_remove()
        _LOGGER.warning("DATABASE WIPED: storage file deleted and protection flag set.")

    # --- ROOF METHODS ---
    async def addRoof(self, name: str, tilt: Optional[float] = None, azimuth: Optional[float] = None, sensorGroupId: str = "", strings: Optional[dict] = None) -> None:
        """Adds or updates a roof in the database."""
        roofId = slugify(name)
        existing = self.roofs.get(roofId)
        
        self.roofs[roofId] = Roof(
            name=name,
            tilt=float(tilt) if tilt is not None else (existing.tilt if existing else 30.0),
            azimuth=float(azimuth) if azimuth is not None else (existing.azimuth if existing else 180.0),
            sensorGroupId=sensorGroupId if sensorGroupId else (existing.sensorGroupId if existing else ""),
            strings=strings if strings is not None else (existing.strings if existing else {})
        )
        await self.async_save()

    async def addStringToRoof(self, roofId: str, stringId: str, stringData: Any) -> bool:
        if roofId in self.roofs:
            if isinstance(stringData, dict):
                 stringData = SolarString.from_dict(stringData)
            self.roofs[roofId].strings[stringId] = stringData
            await self.async_save()
            return True
        return False
        
    async def deleteStringFromRoof(self, roofId: str, stringId: str) -> bool:
        if roofId in self.roofs:
            if stringId in self.roofs[roofId].strings:
                del self.roofs[roofId].strings[stringId]
                await self.async_save()
                return True
        return False
        
    def getRoofStrings(self, roofId) -> dict[str, SolarString]:
        roof = self.roofs.get(roofId)
        return roof.strings if roof else {}

    def listRoofs(self) -> dict[str, str]:
        """Returns a dict {id: name} of roofs."""
        return {k: v.name for k, v in self.roofs.items()}
    
    def getRoof(self, roofId: str) -> Optional[Roof]:
        return self.roofs.get(roofId)

    async def deleteRoof(self, roofId: str) -> bool:
        """Removes a roof from the database."""
        if roofId in self.roofs:
            del self.roofs[roofId]
            await self.async_save()
            return True
        return False

    def getSensorGroupForRoof(self, roofId: str) -> Optional[SensorGroup]:
        """Returns the SensorGroup object associated with a roof."""
        roof = self.roofs.get(roofId)
        if roof and roof.sensorGroupId:
            return self.sensor_groups.get(roof.sensorGroupId)
        return None

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
