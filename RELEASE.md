# Release Notes - Accurate Solar Forecast

## [2026-03-02] - Pre-Update Analysis (Global Refactor: Flat Structure)

### Identified Issues & Improvements

- **Fragmented Architecture**: 15+ files across 4 subdirectories (`core`, `variables`, `databases`, `config_flow`) cause complex import paths and fragile dependencies.
- **Import Frailty**: Excessive use of `..` relative imports leads to potential circular dependency issues.
- **Development Overhead**: High cognitive load due to jumping between multiple directories for a single feature.

### Summary of Changes (Refactor)

- **Unified Structure**: Moved all core logic to the root directory for better reliability and simpler imports.
- **Consolidated Config Flow**: Entire configuration logic is now in `config_flow.py`, reducing complexity and avoiding circular imports.
- **Improved Maintainability**: Standard Home Assistant file layout.
- **Zero-Dependency Imports**: All local imports updated to `.const`, `.db`, etc.

### [2026-03-02] - Structural Simplification (Final Hierarchy)

### [2026-03-02] - Pre-Update Analysis (Hierarchy & String Linking)

### Identified Issues & Improvements (Hierarchy Fixes)

- **Conceptual Confusion**: The term "Roof Hub" for the device name might lead users to think a new integration Hub is created. It needs to be clear that these are subentries within the main Hub ("Accurate Solar Forecast").
- **Subentry Clutter**: The "Add String" pill creates an empty subentry of type `string` because it ends with `async_create_entry`. This should be an `async_abort` since the string data is already persisted into the parent Roof subentry.
- **Diagnostic Sync**: The diagnosis might fail to link sensor groups if it's looking for the slug while the data contains the name (or vice versa).

### Action Plan (Hierarchy Fixes)

1. **Clean Up Standalone Flows**: Modify `flow_strings.py` to use `async_abort(reason="list_updated")` when adding strings standalone, preventing empty subentry creation.
2. **Clarify Device Naming**: Keep the hierarchy but ensure logging confirms that strings are indeed processed within the correct Roof subentry.
3. **Robust Linker**: Ensure `_runAllChecks` in `binary_sensor.py` uses both ID and Name to verify the Roof -> Sensor Group link.

---

## [2026-03-02] - Pre-Update Analysis (Diagnosis Error Fixes)

### Identified Issues & Improvements (Diagnosis Fixes)

- **Diagnostic Crash**: The `AccurateSolarHealthSensor` crashes during early startup because `sub.data` might be `None` or inaccessible while Home Assistant is still initializing subentries. This results in the generic "Error reading database" message.
- **Resilience**: Lack of `None` checks in `_runAllChecks` and `getSubentryMenuState`.
- **Informative Errors**: The catch block in `extra_state_attributes` hides the real exception, making debugging difficult.
- **Linker Logic**: Possible mismatch or initialization order issue causing sensor groups to appear "unlinked" immediately after startup.

### Action Plan (Diagnosis Fixes)

1. **Guard Subentry Access**: Add checks for `if sub.data:` before iterating or accessing keys in `binary_sensor.py` and `core/helpers.py`.
2. **Improve Error Visibility**: Update the catch block in `binary_sensor.py` to log the actual exception.
3. **Refactor Internal Logic**: Ensure `roofs` are correctly identified by checking for `CONF_ROOF_NAME` key existence and validity.

---

## [2026-03-02] - Pre-Update Analysis (Roof/String Refactor)

### Identified Issues & Improvements (Roof/String Refactor)

- **Guided Flow Incompleteness**: The `RoofSubentryFlowHandler` successfully starts the guided flow but fails to integrate the string creation loop, ending prematurely after sensor group selection.
- **Redundant & Divergent Logic**: Overlapping implementations of `async_step_roof_create` between mixins and handlers cause unpredictable behavior depending on the entry point.
- **Missing Loop Step**: `async_step_string_loop` is currently a placeholder, preventing users from adding multiple strings during initial roof setup.
- **Fragile Subentry Updates**: Strings added via the "String" pill rely on matching roof names, which is less reliable than using unique subentry IDs.
- **State Management**: Manual `tempData` cleanup is scattered, potentially leading to "ghost" data in subsequent flow attempts.

### Action Plan (Roof/String Refactor)

1. **Refactor RoofSubentryFlowHandler**: Properly sequence the guided flow: `Geometry -> Sensor Group (Select/Create) -> String Loop -> Finalize`.
2. **Consolidate Building Blocks**: Move shared schema generation and basic steps to the Mixins while keeping flow orchestration in the Handlers.
3. **Implement String Loop**: Create a functional `async_step_string_loop` that allows adding multiple strings or finishing the process.
4. **Targeted Subentry Updates**: Update `StringSubentryFlowHandler` to use proper subentry identification for standalone string additions.
5. **Clean State Lifecycle**: Ensure `temp_data` is cleared at the beginning and end of every flow to ensure a fresh state.

### [2026-03-02] - Completion Status

- [x] **Refactored RoofSubentryFlowHandler**: Implemented the complete guided flow sequence: `Geometry -> Sensor Group -> Strings Addition Loop -> Finalize`.
- [x] **Improved Subentry Targeting**: standalone string additions now use subentry IDs rather than matching by name, making the process much more robust.
- [x] **Fixed Platform Bugs**: Corrected `NameError` and missing import bugs in `select.py` and `number.py` related to sensor group lookups (`selected_sensor_group` -> `CONF_SENSOR_GROUP_NAME`).
- [x] **Consolidated State Management**: Centralized `tempData` cleanup and ensured fresh state initialization at the start of each flow.
- [x] **Aligned Translations**: Updated `en.json` and `es.json` to match the new step IDs used in the guided flow loop.
- [x] **Diagnostic Resilience**: Added `sub.data` guards to prevent "Error reading database" crashes during startup.
- [x] **Robust SG Linker**: Improved diagnostic check to match sensor groups by both slugged ID and display name.

---

## [2026-03-02] - Architectural Simplification: Roof Storage Refactor

### Summary of Changes

- **Refactored Storage Architecture**: Completely removed `roofs` and `strings` from the internal JSON database (`AccurateSolarSensorDB`).
- **Subentry as Source of Truth**: All roof geometry (tilt, azimuth), linked sensor groups, and associated strings are now stored directly in the `ConfigSubentry.data`.
- **Dynamic Platform Setup**: Updated `sensor.py`, `select.py`, and `number.py` to read configuration directly from the subentry, eliminating race conditions.
- **Refactored Config Flows**:
  - `RoofSubentryFlowHandler` now constructs a consolidated data dictionary during initial creation.
  - `StringsFlowMixin` supports both guided flows and standalone additions by updating existing subentry data.
  - `RoofsFlowMixin` (Pill: Gestión → Tejados) now manages HA subentries directly.
- **Improved Removal & Device Cleanup**: Updating `async_remove_subentry` and `async_remove_config_entry_device` in `__init__.py` to handle the new subentry-based structure correctly.

### Benefits

- Eliminated redundancy and potential synchronization mismatches.
- Simplified integration logic and improved performance during startup.
- More robust and predictable entity creation flow.

---

---

## [2026-03-01] - String Creation & UI Sync Fix

### Identified Issues & Improvements (2026-03-01)

- **UI Sync Gap**: Strings added via the "String" pill (quick action) are saved to the database but do not appear as sensors until a restart or manual reload. [BUG]
- **Alarming Logs**: Diagnostic warnings (`_LOGGER.warning`) in `sensor.py` are being flagged by Home Assistant as "Integration Errors" in the UI. [UX]
- **Subentry Traceability**: Lack of sufficient logging during the `async_setup_subentry` phase. [MAINTAINABILITY]

### Action Plan (2026-03-01)

1. **Lower Log Severity**: Change diagnostic `warning` logs to `info` in `sensor.py` and `__init__.py`.
2. **Implement Subentry Reload**: Update `flow_strings.py` to reload the corresponding Roof subentry after adding a string.
3. **Enhance Traceability**: Add specific success/fail logs in `sensor.py` for each subentry.
4. **Fix Select Platform Data Access**: Correct architectural error in `select.py` for DB sync.

### Completion Status (2026-03-01)

- [x] Step 1: Lower Log Severity implemented (Warn -> Info)
- [x] Step 2: Automatic Subentry Reload implemented in `flow_strings.py`
- [x] Step 3: Diagnostic logging trace added to `sensor.py`
- [x] Step 4: `select.py` architectural fix (DB sync)
- [x] **Extra**: Diagnosis entity unique_id updated to `accurate_solar_forecast_diagnosis`
- [x] **Audit**: Performed dead code audit and removed unused classes/imports.

---

## [2026-03-01.1] - Subentry Lifecycle Architecture Fix

### Identified Issues & Improvements (2026-03-01.1)

- **CRITICAL: Missing `async_setup_subentry`**: Platforms only implemented `async_setup_entry`, leading to broken dynamic updates.

### Completion Status (2026-03-01.1)

- [x] Step 1: `async_setup_subentry` + `async_unload_subentry` implemented
- [x] Step 2: All 4 platforms refactored with `async_setup_subentry` handlers
- [x] Step 3: Diagnostic system expanded (15+ checks, 3 severity levels)
- [x] Step 4: Platform files consolidated

---

## [2026-02-28] - Initial Installation Diagnostics

### Identified Issues & Improvements (2026-02-28)

- **Missing Brand Identity**: Integration devices show "icon not available".
- **Summary count mismatch**: Integration shows incorrect device count in summary.
- **Sensor Group Discovery Error**: Sync issue between Config Entries and JSON DB.
- **"Unknown error occurred"**: Generic error in guided flow.

### Action Plan (2026-02-28)

1. **Static Assets**: Recommend `static/` folder for icons/logos.
2. **Device Registry**: Review registration to fix device count summary.
3. **DB Consistency**: Force DB reload during setup.
4. **Flow Resilience**: Add robust error handling in sensor group creation.

---

## [2026-02-27.2] - Sensor Group -> Roof Association

### Identified Issues & Improvements (2026-02-27.2)

- **UX Redundancy**: `selected_sensor_group` stored per-string causes repetition.
- **Wrong Conceptual Association**: Sensor group belongs to the physical environment (Roof), not the string.

### Action Plan (2026-02-27.2)

1. **Models Update**: Move `sensorGroupId` from `SolarString` to `Roof`.
2. **DB Update**: Update helpers and implement migration for existing data.
3. **Flow Update**: Update selectors in config flows.
4. **Sensor Update**: Read sensor group from roof context.

---

## [2026-02-27.1] - v1.1.0: Stability & Deletion Fixes

### Identified Issues & Improvements (2026-02-27.1)

- **Deletion Crash**: `async_unload_entry` blocking deletion.
- **Load Crash**: Calling `async_write_ha_state()` before registration.
- **Missing Translations**: Essential translation keys missing in `strings.json`.

---

## [2026-02-27.0] - Global Refactor & Hotfix

### Identified Issues & Improvements (2026-02-27.0)

- **Coding Standards**: Violation of `camelCase` convention.
- **Integration Failure**: `ImportError` after renaming core functions.

### Action Plan (2026-02-27.0)

1. **Bug Fixes**: Resolve `NameError` and `ImportError`.
2. **Global Refactor**: Apply `camelCase` across the project.
3. **Type Safety**: Complete type hinting.
