# Release Notes - Accurate Solar Forecast

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

### Resumen de Situación Actual

- **Arquitectura**: Totalmente modularizada (core, databases, config_flow, variables).
- **Consistencia**: Ortografía corregida a "Accurate" en todo el proyecto.
- **Estándares**: Código alineado con las reglas de estilo del proyecto (camelCase).

Developed by Carlosjcfr
