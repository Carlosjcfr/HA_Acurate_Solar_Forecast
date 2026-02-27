# Release Notes - Accurate Solar Forecast

## [2026-02-27] - Update Summary (Refactor & Bug Fixes)

### Identified Issues & Improvements - COMPLETED

- **Naming Convention Violation**: SYSTEMATIC REFACTOR. All variables and internal functions have been updated to `camelCase` to comply with user rules.
- **Logical Bug in Engine**: FIXED. Corrected the `geometric_factor` reference in `core/engine.py`.
- **Poor Error Handling**: FIXED. Replaced bare `except:` with proper logging and exception handling.
- **Type Hinting Gaps**: FIXED. Added missing type hints in `__init__.py` and other core files.
- **Standard Overrides**: MAINTAINED. Home Assistant standard overrides (like `async_setup_entry`) remain in `snake_case` for compatibility.

### Action Plan - PROGRESS

1. **Bug Fix**: COMPLETED.
2. **Naming Refactor**: COMPLETED. systematic update across `core/`, `databases/`, and root files.
3. **Error Handling**: COMPLETED.
4. **Type Hinting**: COMPLETED.
5. **Final Review**: COMPLETED. No "Acurate" instances found.

---

## [v1.3.1] - Naming Standardization & Stability

This release brings the codebase in full alignment with the project's coding standards and fixes a critical calculation bug.

### 🌟 Key Changes

- **Full camelCase Refactor**: Every variable and internal function now follows the `camelCase` naming convention.
- **Dataclass Alignment**: Updated `models.py` dataclasses to use `camelCase` fields while maintaining JSON compatibility for stored databases.
- **Engine Stability**: Fixed a `NameError` in `_updateLogic` that occurred during attribute updates.
- **Improved Observability**: Added better error logging in values conversion and calculation loops.
- **Strict Typing**: Enhanced type safety in entry point functions.

### 🩹 Bug Fixes

- Fixed `NameError` on `geometric_factor` in the solar engine.
- Corrected unit conversion debug logging.
- Unified `slugify` usage in all diagnostics.

---

## Historical Notes

### [2026-02-27] - Pre-Update Analysis (Step 4: Documentation & Standards)

- **Type Consistency**: While the new `core/models.py` uses dataclasses, many internal functions in `helpers.py` and `engine.py` lack explicit type hints. [RESOLVED]
- **Architectural Documentation**: README updated with new modular structure. [RESOLVED]

### [v1.3.0] - Structural Refactor & Optimization

This release focused on a complete internal restructuring of the integration to improve maintainability and performance.

### Resumen de Situación Actual

Arquitectura: El proyecto está bien modularizado. La separación en core, databases, config_flow y variables sigue los estándares modernos de Home Assistant.
Consistencia de Nombres: Corregida al 100%. Todos los archivos, clases y enlaces de GitHub usan ahora la ortografía correcta (Accurate).
Código: Completamente refactorizado a camelCase según las reglas del usuario.

*Developed by Carlosjcfr*
