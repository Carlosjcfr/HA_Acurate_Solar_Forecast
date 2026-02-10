# Changelog

All notable changes to this project will be documented in this file.

## [v1.1.0-beta2] - 2026-02-10

### Added

- **Bulk Creation Loop:** Added "Add another module" option after saving a PV Model to allow continuous creation without restarting the flow.
- **Improved Form Layouts:** Reordered Sensor Group fields for better UX (Tilt/Orientation moved up).

### Changed

- **Menu Consistency:** All sub-menus (PV Models, Strings, Sensor Groups) now share a consistent title "Actions" // "Acciones".
- **Empty Forms:** PV Model creation forms now start empty (`vol.UNDEFINED`) instead of showing confusing default values.
- **Label Cleanups:** Removed redundant double asterisks (`**`) from required form fields.
- **Translations:** Synced ES/EN translations for new menu structures.

### Fixed

- **Code Optimization:** Removed dead code (`config_flow.py`) related to old deletion methods and unused constants.
- **State Management:** Fixed potential data leak issues by resetting `temp_data` on flow start.

## [v1.1.0-beta1] - 2026-02-10

### Added

- **Modular Menu System:** New 3-branch configuration flow (PV Models, Sensor Groups, Strings).
- **CRUD for PV Models:** Full Create, Read, Update functionality for PV Models.

### Changed

- **Deletion Handling:** Moved deletion logic to Home Assistant's native integration removal process, ensuring database cleanup.
- **Project Structure:** Moved release notes to root folder.

### Fixed

- **Orphaned Entries:** Fixed issue where deleted sensor groups remained in the internal database.
