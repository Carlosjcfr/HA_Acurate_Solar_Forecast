import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import *
from .pv_database import PVDatabase

class AccurateForecastFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._db = None
        self.selected_brand = None
        self.string_data = {}
        # New variable to track edit mode
        self.editing_group_id = None

    async def async_step_user(self, user_input=None):
        """Menú Principal: ¿Qué quieres hacer?"""
        # Asegurar que DOMAIN existe en hass.data
        self.hass.data.setdefault(DOMAIN, {})

        # Inicializar la base de datos si no existe
        if "db" not in self.hass.data[DOMAIN]:
            self._db = PVDatabase(self.hass)
            await self._db.async_load()
            self.hass.data[DOMAIN]["db"] = self._db
        else:
            self._db = self.hass.data[DOMAIN]["db"]
        
        return self.async_show_menu(
            step_id="user",
            menu_options=["add_pv_model", "add_string", "configure_sensors"]
        )

    # --- OPCIÓN A: AÑADIR MODELO A LA BASE DE DATOS ---
    async def async_step_add_pv_model(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Guardar en la DB
            await self._db.add_model(
                user_input["name"],
                user_input[CONF_BRAND],
                user_input["p_stc"],
                user_input["gamma"],
                user_input["noct"],
                user_input[CONF_VOC],
                user_input[CONF_ISC],
                user_input[CONF_VMP],
                user_input[CONF_IMP]
            )
            # Volver al menú o cerrar
            return self.async_create_entry(title=user_input["name"], data={})

        # Get existing brands to populate the list
        brands_list = self._db.list_brands()

        schema = vol.Schema({
            vol.Required("name"): str,
            # Seleccionable de Marca con opción de escribir nueva
            vol.Required(CONF_BRAND, default="Generic"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=brands_list, 
                    custom_value=True, 
                    mode="dropdown"
                )
            ),
            vol.Required("p_stc", default=450): vol.Coerce(float),
            vol.Required("gamma", default=-0.35): vol.Coerce(float), # %/C
            vol.Required("noct", default=45): vol.Coerce(float),
            vol.Required(CONF_VOC, default=50.0): vol.Coerce(float),
            vol.Required(CONF_ISC, default=13.0): vol.Coerce(float), # Default 13 from diagram
            vol.Required(CONF_VMP, default=41.0): vol.Coerce(float),
            vol.Required(CONF_IMP, default=12.0): vol.Coerce(float), # Default 12 from diagram
        })

        return self.async_show_form(step_id="add_pv_model", data_schema=schema, errors=errors)

    # --- OPCIÓN B: CONFIGURAR SENSORES (GRUPOS) ---
    async def async_step_configure_sensors(self, user_input=None):
        return self.async_show_menu(
            step_id="configure_sensors",
            menu_options=["create_sensor_group", "edit_sensor_group_select"]
        )

    async def async_step_create_sensor_group(self, user_input=None):
        """Crear un nuevo grupo de sensores."""
        errors = {}
        if user_input is not None:
            name = user_input[CONF_SENSOR_GROUP_NAME]
            
            # Save to DB (optional, mainly for internal tracking or reuse logic if needed)
            await self._db.add_sensor_group(
                name,
                user_input[CONF_REF_SENSOR],
                user_input[CONF_TEMP_SENSOR],
                user_input.get(CONF_TEMP_PANEL_SENSOR),
                user_input.get(CONF_WIND_SENSOR),
                user_input[CONF_REF_TILT],
                user_input[CONF_REF_ORIENTATION]
            )
            
            # CREATE CONFIG ENTRY for this Sensor Group
            # This creates a Device in HA
            return self.async_create_entry(
                title=name,
                data=user_input
            )

        # Buscar sensores válidos de irradiancia
        valid_irradiance_sensors = []
        for state in self.hass.states.async_all("sensor"):
            attributes = state.attributes
            if (attributes.get("device_class") == "irradiance" or 
                attributes.get("unit_of_measurement") in ["W/m²", "W/m2"]):
                valid_irradiance_sensors.append(state.entity_id)
        valid_irradiance_sensors.sort()

        schema = vol.Schema({
            vol.Required(CONF_SENSOR_GROUP_NAME): str,
            
            # Sensores
            vol.Required(CONF_REF_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=valid_irradiance_sensors)
            ),
            vol.Required(CONF_TEMP_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_TEMP_PANEL_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_WIND_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="wind_speed")
            ),
            
            # Geometría del Sensor de Referencia
            vol.Required(CONF_REF_TILT, default=0): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_REF_ORIENTATION, default=180): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })

        return self.async_show_form(step_id="create_sensor_group", data_schema=schema, errors=errors)

    async def async_step_edit_sensor_group_select(self, user_input=None):
        """Seleccionar grupo para editar."""
        if user_input is not None:
            # We don't really support full editing of ConfigEntry data via flow easily re-entrant without re-creating
            # But we can simulate it by updating the DB and maybe OptionsFlow later.
            # For now, let's assume we invoke a form with pre-filled values
            # However, ConfigFlow is for creation. Editing usually happens in OptionsFlow.
            # Given the request flow diagram, it looks like a "wizard" style.
            # To actually "EDIT" an existing HA ConfigEntry, we need OptionsFlow.
            # BUT, the user prompt implies this is part of the initial setup flow logic or a management menu.
            # Since we are in the main ConfigFlow class, this creates NEW entries.
            # To edit existing ones, we'd typically use the "Configure" button on the integration page.
            
            # For this implementation, I will treat "Edit" here as modifying the DB record
            # but note that updating the actual running entity won't happen automatically unless we reload it.
            # Let's stick to the prompt's flow: Select Group -> Edit Form.
            self.editing_group_id = user_input["selected_group"]
            return await self.async_step_edit_sensor_group_form()

        groups = self._db.list_sensor_groups()
        if not groups:
            return self.async_abort(reason="no_sensor_groups")

        schema = vol.Schema({
            vol.Required("selected_group"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(groups.keys()), mode="dropdown")
            )
        })
        return self.async_show_form(step_id="edit_sensor_group_select", data_schema=schema)

    async def async_step_edit_sensor_group_form(self, user_input=None):
        """Formulario de edición de grupo."""
        if user_input is not None:
            # Update DB
            name = user_input[CONF_SENSOR_GROUP_NAME]
            # Ideally we should update the existing ConfigEntry if it matches this group,
            # but mapping DB logic to ConfigEntries is tricky. 
            # For now, we update the DB. User might need to reload integration.
            await self._db.add_sensor_group(
                name,
                user_input[CONF_REF_SENSOR],
                user_input[CONF_TEMP_SENSOR],
                user_input.get(CONF_TEMP_PANEL_SENSOR),
                user_input.get(CONF_WIND_SENSOR),
                user_input[CONF_REF_TILT],
                user_input[CONF_REF_ORIENTATION]
            )
            # We can't return create_entry for an edit.
            return self.async_create_entry(title=f"Updated: {name}", data={}) 

        # Load current data
        group_data = self._db.get_sensor_group(self.editing_group_id)
        
        # Valid Sensors search (reuse logic)
        valid_irradiance_sensors = []
        for state in self.hass.states.async_all("sensor"):
            attr = state.attributes
            if (attr.get("device_class") == "irradiance" or 
                attr.get("unit_of_measurement") in ["W/m²", "W/m2"]):
                valid_irradiance_sensors.append(state.entity_id)
        valid_irradiance_sensors.sort()

        schema = vol.Schema({
            vol.Required(CONF_SENSOR_GROUP_NAME, default=group_data[CONF_SENSOR_GROUP_NAME]): str,
            vol.Required(CONF_REF_SENSOR, default=group_data[CONF_REF_SENSOR]): selector.EntitySelector(
                selector.EntitySelectorConfig(include_entities=valid_irradiance_sensors)
            ),
            vol.Required(CONF_TEMP_SENSOR, default=group_data[CONF_TEMP_SENSOR]): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_TEMP_PANEL_SENSOR, default=group_data.get(CONF_TEMP_PANEL_SENSOR, vol.UNDEFINED)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_WIND_SENSOR, default=group_data.get(CONF_WIND_SENSOR, vol.UNDEFINED)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="wind_speed")
            ),
            vol.Required(CONF_REF_TILT, default=group_data[CONF_REF_TILT]): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_REF_ORIENTATION, default=group_data[CONF_REF_ORIENTATION]): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })

        return self.async_show_form(step_id="edit_sensor_group_form", data_schema=schema)


    # --- OPCIÓN C: CREAR UN STRING (SENSOR) - PASO 1: SELECCIONAR PROVEEDOR (GRUPO SENSORES) y MARCA ---
    async def async_step_add_string(self, user_input=None):
        if user_input is not None:
            self.selected_brand = user_input[CONF_BRAND]
            self.string_data = user_input # Contains string_name and selected_sensor_group
            return await self.async_step_add_string_details()

        brands_list = self._db.list_brands()
        sensor_groups = self._db.list_sensor_groups() # {id: name}
        
        # Check if we have groups
        if not sensor_groups:
             return self.async_abort(reason="no_sensor_groups_available")
        
        # Get list of group names for selector
        group_options = list(sensor_groups.keys())

        schema = vol.Schema({
            vol.Required(CONF_STRING_NAME): str,
            vol.Required("selected_sensor_group"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=group_options, mode="dropdown")
            ),
            vol.Required(CONF_BRAND, default="Generic"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=brands_list, mode="dropdown")
            )
        })

        return self.async_show_form(step_id="add_string", data_schema=schema)

    # --- PASO 2: DETALLES DEL STRING ---
    async def async_step_add_string_details(self, user_input=None):
        if user_input is not None:
            # Combine data
            final_data = {**self.string_data, **user_input}
            # Add sensor group data to the string config so it's self-contained or linked
            # We store the Group ID. The Sensor component will look it up from DB or Entity Registry.
            # final_data["sensor_group_id"] = ... (already in selected_sensor_group)
            
            return self.async_create_entry(
                title=self.string_data[CONF_STRING_NAME], 
                data=final_data
            )

        # Gets models for the selected brand
        models_filtered = self._db.list_models_by_brand(self.selected_brand)
        
        schema = vol.Schema({
            # --- SECCION DATOS DEL STRING ---
            # Selector de Modelo FILTRADO
            vol.Required(CONF_PANEL_MODEL): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(models_filtered.values()), mode="dropdown")
            ),
            vol.Required(CONF_NUM_PANELS, default=1): int,
            vol.Required(CONF_NUM_STRINGS, default=1): int,
            
            # Geometría
            vol.Required(CONF_TILT, default=30): vol.All(vol.Coerce(float), vol.Range(min=0, max=90)),
            vol.Required(CONF_AZIMUTH, default=180): vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
        })

        return self.async_show_form(step_id="add_string_details", data_schema=schema)