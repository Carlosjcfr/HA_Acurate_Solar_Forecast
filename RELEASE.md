# Release Notes - Accurate Solar Forecast

## [2026-02-27] - Pre-Update Analysis: Sensor Group → Roof Association

### Identified Issues & Improvements

- **UX Redundancy**: `selected_sensor_group` is stored per-string, forcing users to repeat the same selection for every string on the same roof. Typically only 1 irradiance sensor exists in an installation.
- **Wrong Conceptual Association**: A sensor group is a property of the physical installation environment, not of an individual string. The transposition engine already handles adapting measured irradiance to different roof geometries, so a single sensor group per roof is architecturally correct.
- **SolarString model carries unnecessary field**: `selectedSensorGroup` on `SolarString` should be moved to `Roof` as `sensorGroupId`.

### Action Plan

1. **`core/models.py`**: Add `sensorGroupId: str` to `Roof`. Remove `selectedSensorGroup` from `SolarString` (keep `from_dict` backward-compat to migrate existing data).
2. **`databases/accurate_solar_sensor_db.py`**: Update `addRoof()` to accept `sensorGroupId`. Add `getSensorGroupForRoof()` helper. Add `migrateStringGroupToRoof()` for existing data.
3. **`databases/accurate_solar_sensor_db.py`**: Update `async_load()` to run migration: if a roof has no `sensorGroupId`, read it from the first string in that roof.
4. **`config_flow/flow_strings.py`**: Remove `selected_sensor_group` from `_getStringSelectRelationsSchema()`.
5. **`config_flow/__init__.py`**: Update `RoofSubentryFlowHandler` and `_getStringSelectRelationsSchema` — pass sensor group from roof context.
6. **`config_flow/flow_roofs.py`**: Add `selected_sensor_group` selector when creating/editing a roof.
7. **`sensor.py`**: Read sensor group from `roof.sensorGroupId` instead of `string.selectedSensorGroup`.
8. **Translations**: Remove `selected_sensor_group` from string steps, add it to roof steps.

---

## [2026-02-27] - v1.1.0: Stability & Deletion Fixes

### Identified Issues & Improvements

- **Integration Deletion Crash**: `async_unload_entry` blocking deletion when platforms failed to unload. [FIXED]
- **Integration Load Crash**: `AccurateSolarSensorDBSensor` calling `async_write_ha_state()` in `__init__` before entity registration. [FIXED]
- **Config Flow Crash**: Multiple mixin inheritance in `AccurateForecastFlow` causing "Invalid flow specified" errors. [FIXED]
- **Missing Translations**: `strings.json` missing `entity.number.azimuth`, `entity.binary_sensor`, and `config.error.sensor_unavailable`, causing HA to silently fail loading all translations. [FIXED]
- **Subentry Translations**: Management subentry flow steps missing translations for sub-steps (menu_pv_models, menu_roofs, etc.). [FIXED]
- **Unsafe Data Access**: Platform `async_setup_entry` functions using `hass.data[DOMAIN]["db"]` instead of safe `.get()` access. [FIXED]

### Action Plan

1. **Clean `__init__.py`**: Centralized DB loading via `_ensureDbLoaded()`, resilient `async_unload_entry` (returns `True` on error). [COMPLETED]
2. **Fix `AccurateSolarSensorDBSensor`**: Set initial value in `__init__` without `async_write_ha_state()`, guard in `_updateState`. [COMPLETED]
3. **Simplify `ConfigFlow`**: Clean inheritance (`config_entries.ConfigFlow` only), re-add `async_get_supported_subentry_types` separately. [COMPLETED]
4. **Sync Translations**: Added all missing keys to `strings.json`/`en.json`/`es.json`. Added all management sub-steps to `config_subentries.management.step`. [COMPLETED]
5. **Conditional Pills**: Roof pill requires sensor group; String pill requires roof + sensor group. [COMPLETED]
6. **Version Bump**: Updated manifest.json to v1.1.0. [COMPLETED]

---

## [2026-02-27] - Pre-Update Analysis (Global Refactor & Hotfix)

### Identified Issues & Improvements

- **Coding Standards**: Systematic violation of the `camelCase` naming convention for variables and internal functions. [FIXED]
- **Integration Failure**: Integration failed to start due to an `ImportError` after renaming core functions (`get_subentry_menu_state` -> `getSubentryMenuState`). [FIXED]
- **Inconsistent Config Flow**: Multiple files in `config_flow/` were still using legacy `snake_case` database calls. [FIXED]
- **Solar Engine Bug**: `NameError` related to `geometric_factor` in `core/engine.py`. [FIXED]
- **Error Handling**: Presence of bare `except:` blocks without proper logging. [FIXED]
- **Typing Gaps**: Missing type hints in core modules. [FIXED]

### Action Plan

1. **Bug Fixes**: Resolve the `NameError` in the solar engine and the `ImportError` in the config flow. [COMPLETED]
2. **Global Refactor**: Apply `camelCase` naming convention across all `core`, `databases`, and `root` files. [COMPLETED]
3. **Config Flow Sync**: Systematically update all mixins in `config_flow/` to match the new naming conventions and database methods. [COMPLETED]
4. **Resiliency**: Improve error handling with specific exceptions and logging. [COMPLETED]
5. **Type Safety**: Complete type hinting for better maintainability. [COMPLETED]
6. **Final Validation**: Ensure no remaining instances of the "Acurate" misspelling. [COMPLETED]

---

## [v1.3.2] - 2026-02-27: Stability & Standardization

### 🌟 Key Changes

- **Full camelCase Refactor**: Every variable and internal function now follows the project's standard naming convention.
- **Dataclass Standardization**: Updated `PvModel`, `SolarString`, and `SensorGroup` to use `camelCase` fields while maintaining backward compatibility.
- **Improved Observability**: Replaced bare `except:` blocks with specific error handling and informative logging.
- **Strict Typing**: Added comprehensive type hints across the entire codebase.

### 🩹 Bug Fixes

- **Hotfix**: Resolved integration startup failure caused by inconsistent function naming in imports.
- **Engine**: Fixed a critical `NameError` in the transposition factor calculation.
- **Config Flow**: Resolved multiple runtime errors in the setup screens for roofs, strings, and sensors.
- **Typo Cleanup**: Verified the complete removal of the "Acurate" misspelling in all files.

---

## Historical Notes

### [v1.3.0] - Structural Refactor & Optimization

This release focused on a complete internal restructuring of the integration to improve maintainability and performance.

### Current Situation Summary

- **Architecture**: Fully modularized (core, databases, config_flow, variables).
- **Consistency**: Spelling corrected to "Accurate" throughout the project.
- **Standards**: Code aligned with the project's style rules (camelCase).

Developed by Carlosjcfr
