# ☀️ Accurate Solar Forecast for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Maintainer](https://img.shields.io/badge/maintainer-Carlosjcfr-blue)](https://github.com/Carlosjcfr)
[![version](https://img.shields.io/badge/version-1.0.0-green)]()

**Accurate Solar Forecast** es una integración personalizada para Home Assistant diseñada para estimar la producción fotovoltaica con alta precisión física y geométrica.

A diferencia de las estimaciones simples, este componente utiliza **motores de transposición de irradiancia**, permitiendo simular múltiples strings con diferentes orientaciones utilizando **un único sensor de referencia** (piranómetro o sensor solar).

## ✨ Características Principales

### 📐 Motor de Transposición Geométrica

Olvídate de comprar múltiples sensores de irradiancia.

* Calcula la radiación incidente en cualquier superficie (orientación/inclinación).
* Utiliza la posición solar en tiempo real (Azimut y Elevación) para calcular el **Ángulo de Incidencia (AOI)**.
* **Gestión Geométrica Completa:** Configura la orientación e inclinación tanto de tus paneles como de tus sensores de referencia (ej: una estación meteorológica horizontal o un sensor en el tejado).

### ⚙️ Arquitectura Modular (Nuevo)

Diseñado para instalaciones complejas:

* **Grupos de Sensores:** Configura tus estaciones meteorológicas o conjuntos de sensores *una sola vez*. Se crearán como Dispositivos en Home Assistant.
* **Strings Flexibles:** Crea múltiples strings virtuales (ej: Este, Oeste, Pérgola) usando el mismo grupo de sensores como fuente.

### 💾 Base de Datos de Paneles (PV Database)

Sistema de gestión de inventario integrado.

* **Define una vez, usa siempre:** Crea modelos de tus placas solares (Potencia, Coeficientes, NOCT, Voc, Isc, Vmp, Imp) y guárdalos en la base de datos interna.
* **Reutilizable:** Asigna el mismo modelo de panel a diferentes strings sin volver a introducir fichas técnicas.

---

## 🚀 Instalación

### Opción 1: HACS (Recomendado)

1. Añade este repositorio como **Custom Repository** en HACS.
2. Busca "Accurate Solar Forecast" e instala.
3. Reinicia Home Assistant.

### Opción 2: Manual

1. Descarga la carpeta `custom_components/accurate_solar_forecast`.
2. Cópiala dentro de `config/custom_components/` en tu instalación de HA.
3. Reinicia Home Assistant.

---

## 📖 Uso y Configuración

Ve a **Ajustes** > **Dispositivos y Servicios** > **Añadir Integración** > **Accurate Solar Forecast**.

### Paso 1: Crear un Modelo de Panel (PV Model)

Selecciona la opción **"Nuevo Módulo Fotovoltaico"**. Necesitarás la ficha técnica de tu placa:

* **Modelo:** Nombre identificativo (Ej: `Longi 450W Hi-MO`).
* **Fabricante:** Marca del panel (Ej: `Longi`, `Jinko`...).
* **Especificaciones:** Potencia (STC), Gamma (%/°C), NOCT, Voc, Isc, Vmp, Imp.

### Paso 2: Configurar Sensores (Sensor Group)

Antes de crear strings, define qué sensores tienes disponibles. Selecciona **"Configurar Sensores"** > **"Crear Grupo"**:

1. **Nombre:** Identificador del grupo (Ej: "Estación Metereológica Tejado").
2. **Sensores Físicos:**
    * **Irradiancia (Obligatorio)**.
    * **Temperatura Ambiental (Obligatorio)**.
    * **Temp. Panel / Viento (Opcionales)**.
3. **Geometría del Sensor:**
    * Defines cómo está instalado tu sensor de irradiancia (Tilt y Orientación). Esto es vital para calcular la transposición correctamente.

*Resultado:* Se creará un **Dispositivo** en Home Assistant con las entidades de los sensores configurados.

### Paso 3: Crear un String

Selecciona **"Nuevo String"**. El proceso ahora es muy rápido:

1. **Selecciona Grupo de Sensores:** Elige la estación meteorológica que alimentará los cálculos de este string.
2. **Selecciona Fabricante del Panel:** Elige la marca.
3. **Configura Detalles del String:**
    * **Nombre:** (Ej: "String Pérgola").
    * **Módulo FV:** Selecciona el modelo específico.
    * **Configuración Eléctrica:** Número de paneles en serie y strings en paralelo.
    * **Geometría del Panel:** Inclinación (Tilt) y Orientación (Azimut) de las placas.

---

## 🧠 Cómo funciona (La Ciencia)

El componente realiza los siguientes cálculos en cada actualización:

1. **Geometría Solar:** Obtiene la posición del sol (`sun.sun`).
2. **Cálculo AOI:** Determina el ángulo de incidencia solar tanto para el **sensor de referencia** (definido en el Grupo de Sensores) como para el **panel objetivo** (definido en el String).
3. **Factor Geométrico:** Transpone la irradiancia medida a la superficie del panel:
    `Irradiancia_Target = Irradiancia_Ref * (cos(θ_target) / cos(θ_ref))`
4. **Modelo Térmico:** Calcula la temperatura de la célula ($T_{cell}$) basándose en los datos del Grupo de Sensores.
5. **Potencia Final:** Aplica el coeficiente de pérdidas por temperatura (Gamma) a la potencia base generada.

---

## 📄 Licencia

PolyForm Strict License 1.0.0 ->
<https://polyformproject.org/licenses/strict/1.0.0>
