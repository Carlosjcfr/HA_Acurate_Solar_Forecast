# Correcciones y Refabricación de Arquitectura

## [2026-03-02] - Refactor de Almacenamiento de Tejados (Subentries API)

Se ha realizado una simplificación estructural profunda para eliminar la redundancia de datos y mejorar la fiabilidad de la integración.

### Problemas Solucionados

- **Redundancia de datos**: Los tejados y las strings solares se almacenaban tanto en una base de datos JSON propia como en los objetos `ConfigSubentry` de Home Assistant. Esto generaba riesgos de desincronización.
- **Condiciones de carrera**: La configuración de entidades a veces fallaba en el arranque porque la base de datos JSON no se terminaba de cargar antes del setup de HA.
- **Fallos en la creación dinámica**: Las nuevas subentries (tejados) a veces no aparecían correctamente en la interfaz sin un reinicio completo.
- **Complejidad innecesaria**: El uso de `slugify` como clave primaria para tejados era propenso a errores si el nombre contenía caracteres especiales.

### Cambios de Arquitectura

- **Eliminación de la tabla `roofs`**: El objeto `AccurateSolarSensorDB` ya no gestiona tejados ni strings.
- **Subentry data como Fuente de Verdad**: Todos los parámetros de configuración (inclinación, orientación, grupo de sensores y lista de strings) se guardan directamente en el campo `data` de cada `ConfigSubentry`.
- **Setup de plataformas basado en Subentry**: `sensor.py`, `select.py` y `number.py` ahora leen la configuración directamente desde el objeto `subentry` que HA les proporciona al iniciarse.

### Mejoras en el Config Flow y UI

- **Flujo guiado consolidado**: Al crear un tejado nuevo, se recogen todos los datos y se crea la subentry de una sola vez al finalizar el asistente.
- **Gestión de Strings dinámica**: Las strings se añaden o modifican editando directamente el diccionario de datos de la subentry, lo que refleja los cambios al instante.
- **Movilidad entre tejados**: Se ha implementado la capacidad de mover una string de un tejado a otro mediante un selector (`select.py`), actualizando automáticamente ambas subentries vinculadas.
- **Gestión de dispositivos integrada**: Borrar un dispositivo de string desde la UI de HA ahora provoca su eliminación automática de la configuración interna de la subentry.

### Beneficios obtenidos

- Mayor robustez ante reinicios y cargas dinámicas.
- Código más limpio y fácil de mantener (DRY).
- Menor uso de E/S de disco al evitar duplicar guardados en la base de datos JSON.
