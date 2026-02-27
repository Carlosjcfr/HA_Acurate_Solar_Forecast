# Release Notes - Accurate Solar Forecast

## [v1.3.0] - Structural Refactor & Optimization

This release focuses on a complete internal restructuring of the integration to improve maintainability, performance, and naming consistency.

### 🌟 Major Changes

* **Project Restructuring**: Core logic has been moved from the root directory to a specialized `core/` package.
  * `core/engine.py`: Handles complex solar transposition and sensor logic.
  * `core/number.py` & `core/select.py`: Entities for configuration.
  * `core/helpers.py`: Shared utility functions.
* **Renaming & Consistency**: Fixed spelling of "Accurate" across the entire codebase (previously "Acurate").
  * Updated folder names, class names, and GitHub repository links.
  * *Note*: Database compatibility is maintained; your existing configurations will continue to work.
* **New Config Navigation**: Improved the configuration flow using the "pill" button system for quick actions (PV Models, Roofs, Sensor Groups, Strings).
* **Centralized ID Engine**: Introduced a unified `slugify` helper to ensure consistent ID generation across sensors, roofs, and database keys.

### 🚀 Performance Improvements

* **Night Short-circuit**: Solar sensors now skip heavy geometric calculations during nighttime (elevation <= 0), reducing CPU load.
* **UI Optimization**: Streamlined schema generation in the configuration flow to be more responsive.
* **Package API**: Implemented proper Python `__init__.py` exports to reduce import overhead and memory footprint.

### 🩹 Bug Fixes & Refinements

* **Device Cleanup**: Fixed a critical bug that prevented automatic database cleanup when removing devices from the Home Assistant UI.
* **Consistent Units**: Improved `get_converted_value` to support more units of measurement (Wind Speed, Irradiance, Temperature).
* **Clean Imports**: Removed dead code and unused imports across all modules.

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

## 🚀 Plan de Acción (Action Plan)

### 1. Estabilidad y Robustez (Prioridad Alta)

Validación de Base de Datos: Implementar un esquema (usando Dataclasses) para los modelos de paneles. Actualmente, si el JSON se edita mal a mano, la integración podría fallar al cargar.
Manejo de Errores en Sensores: Añadir bloques try-except más específicos en los cálculos matemáticos para manejar valores NaN o None de sensores externos de forma elegante.

### 2. Optimización de Rendimiento (Prioridad Media)

Throttling de Posición Solar: El sol se mueve constantemente, disparando actualizaciones cada segundo. Implementaremos un umbral (ej: solo recalcular si el sol se mueve más de 0.2 grados) para ahorrar ciclos de CPU.
Cache de Cálculos: Almacenar los resultados intermedios de la transposición geométrica para no repetirlos si no han cambiado los inputs.

### 3. Experiencia de Usuario - UX (Prioridad Media)

Validación proactively: En el formulario de creación de sensores, añadir una validación inmediata que avise si el sensor seleccionado no tiene una unidad de medida compatible (W/m², LUX, etc.).
Diagnósticos: Crear una plataforma binary_sensor.py que indique si la base de datos está cargada correctamente o si hay algún string "huérfano" sin modelo de panel.

### 4. Documentación y Estándares (Mantenimiento)

Type Hinting: Completar el tipado de todas las funciones para que el editor de código pueda detectar errores antes de ejecutar.
Wiki/README: Actualizar los diagramas de flujo para reflejar la nueva estructura modular
---

*Developed by Carlosjcfr*
