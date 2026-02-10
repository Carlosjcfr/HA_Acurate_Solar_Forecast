# 🚀 Release Notes: v1.1.0-beta2 (Optimization Release)

**Focus: Codebase optimization, dead code removal, and UI consistency updates.**

#### 🧹 Code Quality & Optimizations

* **Dead Code Removal:** Cleaned up `config_flow.py` by removing unused action constants and unreachable deletion steps (deletion is now handled natively via Home Assistant).
* **State Management:** improved `temp_data` handling to prevent data leaking between configuration attempts.
* **Form Logic:** Updated `_show_pv_model_form` to use `vol.UNDEFINED`. Fields now properly show as empty when creating new items, instead of having potentially misleading default values.
* **Translation Cleanup:** Removed orphaned translation keys for deleted steps.

#### 🎨 UI / UX Improvements

* **Consistent Menus:** All sub-menus (PV Models, Strings, Sensor Groups) now share a consistent title **"Actions"**.
* **Simplified Options:** Configuration menus have been streamlined to focus on `Create` and `Edit` actions.
* **Bulk Creation Loop:** Added a new *"Add another module"* option after creating/editing a PV model, allowing you to create multiple models in a single session without navigating back.
* **Improved Form Layout:** Reordered fields in the **Sensor Group** configuration to group geometry settings (Tilt/Orientation) closer to the reference sensor for better logical flow.
* **Cleaner Labels:** Removed redundant double asterisks (`**`) from required fields in the UI.

#### ⚠️ Upgrade Notes

* This release refines the "Modular Config Flow" introduced in previous betas.
* No breaking changes for existing configurations, but the setup UI is now cleaner.

#### 🧪 Testing Instructions

1. Update to this beta release in HACS.
2. Navigate to **Settings > Devices > Add Integration > Accurate Solar Forecast**.
3. Check the 3 sub-menus. They should all be titled **"Actions"**.
4. Try creating a new PV Model. The form fields should start **empty** (no pre-filled 450W values).
5. Verify that basic creation flows still work for all 3 types.
