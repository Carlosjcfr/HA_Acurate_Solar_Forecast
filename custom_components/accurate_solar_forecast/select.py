import logging
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from .variables.const import DOMAIN, CONF_STRING_NAME, CONF_TILT, CONF_AZIMUTH, CONF_ROOF_NAME, CONF_REAL_PRODUCTION_SENSOR

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Accurate Solar Forecast select entities."""
    if CONF_ROOF_NAME in config_entry.data:
        db = hass.data[DOMAIN]["db"]
        roof_name = config_entry.data.get(CONF_ROOF_NAME)
        roof_id = roof_name.lower().replace(" ", "_") if roof_name else "default"
        roof_strings = db.get_roof_strings(roof_id)
        
        entities = []
        for string_id, string_data in roof_strings.items():
            combined_data = dict(string_data)
            combined_data[CONF_ROOF_NAME] = roof_name
            entities.append(SolarStringRoofSelect(hass, combined_data, db, config_entry, string_id, roof_id))
            
        if entities:
            async_add_entities(entities)


class SolarStringRoofSelect(SelectEntity):
    """Select entity for choosing the roof of a solar string."""

    _attr_has_entity_name = True
    _attr_translation_key = "roof"
    _attr_icon = "mdi:home-roof"

    def __init__(self, hass, string_data, db, config_entry, string_id, roof_id):
        self.hass = hass
        self._config_entry = config_entry
        self._data = string_data
        self._string_id = string_id
        self._roof_id = roof_id
        self._string_name = self._data.get(CONF_STRING_NAME)
        self._attr_unique_id = f"str_{self._string_id}_roof_select"
        self._db = db
        self._sensor_group = db.get_sensor_group(self._data.get("selected_sensor_group"))

        # Recuperar datos del modelo
        model_name = self._data.get("panel_model")
        self._panel_data = {}
        if db and db.data:
            for v in db.data.values():
                if v.get("name") == model_name:
                    self._panel_data = v
                    break
        self.found_device = False

    @property
    def options(self):
        """Return a list of available roofs."""
        return list(self._db.list_roofs().values())

    @property
    def current_option(self):
        """Return the current selected roof."""
        return self._data.get(CONF_ROOF_NAME)

    @property
    def device_info(self):
        """Return device info linked to the String."""
        string_id = f"str_{self._string_name.lower().replace(' ', '_')}"
        device_identifiers = {(DOMAIN, string_id)}
        
        # Try to link to Real Production Sensor's device if configured

        from homeassistant.helpers import device_registry as dr, entity_registry as er
        
        real_sensor_id = self._data.get(CONF_REAL_PRODUCTION_SENSOR)
        found_device = False
        if real_sensor_id:
             ent_reg = er.async_get(self.hass)
             entity_entry = ent_reg.async_get(real_sensor_id)
             if entity_entry and entity_entry.device_id:
                 dev_reg = dr.async_get(self.hass)
                 device = dev_reg.async_get(entity_entry.device_id)
                 if device:
                     device_identifiers = device.identifiers
                     found_device = True

        if not found_device:
             device_identifiers = {(DOMAIN, f"str_{self._string_id}")}

        return DeviceInfo(
            identifiers=device_identifiers,
            name=self._string_name if not found_device else None,
            manufacturer=self._panel_data.get("brand", "Generic") if not found_device else None,
            model=self._panel_data.get("panel_model") if not found_device else None,
            via_device=(DOMAIN, self._sensor_group.get(CONF_SENSOR_GROUP_NAME)) if (not found_device and self._sensor_group) else None
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Find roof ID by name
        roof_id = None
        for rid, rname in self._db.list_roofs().items():
            if rname == option:
                roof_id = rid
                break
        
        if not roof_id:
            _LOGGER.error(f"Selected roof '{option}' not found in database.")
            return

        # Get Roof Data
        roof_data = self._db.get_roof(roof_id)
        
        # Prepare new data
        new_data = self._config_entry.data.copy()
        new_data[CONF_ROOF_NAME] = option
        
        # Update Tilt/Azimuth if available in roof
        # (We overwrite assuming user wants to align with the new roof)
        if roof_data:
            if "tilt" in roof_data and roof_data["tilt"] is not None:
                new_data[CONF_TILT] = roof_data["tilt"]
            if "azimuth" in roof_data and roof_data["azimuth"] is not None:
                new_data[CONF_AZIMUTH] = roof_data["azimuth"]

        # Update Config Entry
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
        
        # Reload to propagate changes
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

# We will implement this later if needed or if user enables cover management again.
