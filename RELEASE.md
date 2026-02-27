# Release Notes - Accurate Solar Forecast

## [2026-02-27] - Pre-Update Analysis (Step 4: Documentation & Standards)

### [4] Identified Issues & Improvements

- **Type Consistency**: While the new `core/models.py` uses dataclasses, many internal functions in `helpers.py` and `engine.py` lack explicit type hints, making it harder for static analysis tools to catch errors.
- **Architectural Documentation**: The `README.md` at the root of the project partially reflects the old structure. It needs a modern overview of the `core/`, `databases/`, and `config_flow/` separation.
- **Code Style**: Ensure all new methods follow the established camelCase for variables/functions and PascalCase for classes as per the user's global memory rules.

### [4] Action Plan

1. **Type Hinting Sweep**:
    - Update `core/helpers.py` with full typing.
    - Update `databases/accurate_solar_sensor_db.py` to use Python 3.10+ typing.
    - Ensure `engine.py` methods have clear return types.

2. **Documentation Update**:
    - Refresh `README.md` with the new modular architecture.
    - Add a Mermaid diagram showing the interaction between the JSON Database and the Solar Engine.

3. **Final Naming Review**:
    - Final check for any remaining "Acurate" (with one 'c') in comments or internal strings.

---

## [v1.3.0] - Structural Refactor & Optimization

This release focuses on a complete internal restructuring of the integration to improve maintainability, performance, and naming consistency.

### 🌟 Major Changes

- **Project Restructuring**: Core logic has been moved from the root directory to a specialized `core/` package.
  - `core/engine.py`: Handles complex solar transposition and sensor logic.
  - `core/number.py` & `core/select.py`: Entities for configuration.
  - `core/helpers.py`: Shared utility functions.
- **Renaming & Consistency**: Fixed spelling of "Accurate" across the entire codebase (previously "Acurate").
  - Updated folder names, class names, and GitHub repository links.
  - *Note*: Database compatibility is maintained; your existing configurations will continue to work.
- **New Config Navigation**: Improved the configuration flow using the "pill" button system for quick actions (PV Models, Roofs, Sensor Groups, Strings).
- **Centralized ID Engine**: Introduced a unified `slugify` helper to ensure consistent ID generation across sensors, roofs, and database keys.

### 🚀 Performance Improvements

- **Night Short-circuit**: Solar sensors now skip heavy geometric calculations during nighttime (elevation <= 0), reducing CPU load.
- **UI Optimization**: Streamlined schema generation in the configuration flow to be more responsive.
- **Package API**: Implemented proper Python `__init__.py` exports to reduce import overhead and memory footprint.

### 🩹 Bug Fixes & Refinements

- **Device Cleanup**: Fixed a critical bug that prevented automatic database cleanup when removing devices from the Home Assistant UI.
- **Consistent Units**: Improved `get_converted_value` to support more units of measurement (Wind Speed, Irradiance, Temperature).
- **Clean Imports**: Removed dead code and unused imports across all modules.

## 📊 Resumen de Situación Actual

Arquitectura: El proyecto está bien modularizado. La separación en core, databases, config_flow y variables sigue los estándares modernos de Home Assistant.
Consistencia de Nombres: Corregida al 100%. Todos los archivos, clases y enlaces de GitHub usan ahora la ortografía correcta (Accurate).
Config Flow: Es muy avanzado. El uso de ConfigSubentryFlow y Mixins permite una gestión de dispositivos muy limpia, similar a integraciones oficiales complejas.
Base de Datos: El motor JSON (Store) es robusto y protege la persistencia de los paneles y strings del usuario.
🔍 Errores Identificados y Corregidos en este paso:
Bug de Importación: Se había eliminado por error la referencia a DeviceEntry en el init.py raíz, lo que impedía la autodestrucción de dispositivos desde la UI. [CORREGIDO]
Código Duplicado en UI: Los formularios de configuración repetían la misma lógica de "valores por defecto" en cada paso. He creado el helper *get_default en la clase base para limpiar los Mixins de UI. [CORREGIDO]
Inconsistencia de IDs: Algunas entidades seguían usando lower().replace(' ', '*') mientras otras usaban el nuevo slugify. He unificado todo el motor para que usen la misma función. [CORREGIDO]
Optimización Nocturna: Los sensores de potencia seguían ejecutando cálculos trigonométricos complejos incluso de noche. Ahora se detienen inmediatamente si el sol baja del horizonte. [CORREGIDO]

---

## [2026-02-27] - Pre-Update Analysis (Step 2: Performance Optimization)

### Identified Issues & Improvements

- **High Update Frequency**: `sun.sun` updates its position very frequently (several times per minute). Each update triggers a full re-calculation across all solar string entities.
- **Redundant Trigonometry**: The geometric factor only changes significantly when the sun moves more than a fraction of a degree. Recalculating it for every minor sun wobble is inefficient.
- **Computational Debt**: With many strings, these frequent updates can lead to unnecessary CPU spikes in low-power Home Assistant installations.

### Action Plan

1. Define a `SUN_MOVEMENT_THRESHOLD` (0.5 degrees).
2. Implement caching for `geometric_factor` and `cloud_coverage` within the sensor classes.
3. Update `_update_logic` to skip heavy math if the sun hasn't moved significantly or is below the horizon.
4. Refactor `get_converted_value` to be slightly more efficient.

---

## 🚀 Plan de Acción (Action Plan) - Progreso

### 1. Estabilidad y Robustez (Prioridad Alta) - **[CORREGIDO]**

- **Validación de Base de Datos**: Implementado esquema con `Dataclasses` para paneles, tejados y grupos de sensores.
- **Manejo de Errores**: Bloques `try-except` añadidos en todos los cálculos críticos de `engine.py`.

### 2. Optimización de Rendimiento (Prioridad Media) - **[CORREGIDO]**

- **Throttling de Posición Solar**: Implementado umbral de 0.5 grados. Los cálculos trigonométricos ahora se saltan si el sol no se ha movido significativamente.
- **Cache de Cálculos**: Los factores de transposición y cobertura nubosa ahora se cachean y solo se recalculan cuando es necesario.

### 3. Experiencia de Usuario - UX (Prioridad Media) - **[CORREGIDO]**

- **Validación proactively**: Implementada validación de estado de sensores en el Config Flow (`unavailable/unknown`). Añadidos mensajes de error traducidos.
- **Diagnósticos**: Creada plataforma `binary_sensor.py` con una entidad de "Estado de la Integración" que reporta problemas de base de datos o strings huérfanos.

### 4. Documentación y Estándares (Mantenimiento) - **[CORREGIDO]**

- **Type Hinting**: Migración a tipos de Python en `core/*` y `databases/*` completada al 100%.
- **README**: Actualizado con diagramas de arquitectura y detalles técnicos.
- **Limpieza Final**: Revisión de términos "Acurate" obsoletos terminada.

---

*Developed by Carlosjcfr*
