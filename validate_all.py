import py_compile
import sys

files = [
    'custom_components/accurate_solar_forecast/__init__.py',
    'custom_components/accurate_solar_forecast/sensor.py',
    'custom_components/accurate_solar_forecast/number.py',
    'custom_components/accurate_solar_forecast/select.py',
    'custom_components/accurate_solar_forecast/binary_sensor.py',
    'custom_components/accurate_solar_forecast/core/engine.py',
    'custom_components/accurate_solar_forecast/core/__init__.py',
    'custom_components/accurate_solar_forecast/core/helpers.py',
    'custom_components/accurate_solar_forecast/core/models.py',
    'custom_components/accurate_solar_forecast/core/number.py',
    'custom_components/accurate_solar_forecast/core/select.py',
    'custom_components/accurate_solar_forecast/databases/__init__.py',
    'custom_components/accurate_solar_forecast/databases/accurate_solar_sensor_db.py',
    'custom_components/accurate_solar_forecast/config_flow/__init__.py',
    'custom_components/accurate_solar_forecast/config_flow/flow_pv_models.py',
    'custom_components/accurate_solar_forecast/config_flow/flow_roofs.py',
    'custom_components/accurate_solar_forecast/config_flow/flow_sensor_groups.py',
    'custom_components/accurate_solar_forecast/config_flow/flow_strings.py',
    'custom_components/accurate_solar_forecast/variables/__init__.py',
    'custom_components/accurate_solar_forecast/variables/const.py',
]

errors = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"FAIL: {f}: {e}")
        errors += 1

if errors:
    print(f"\n{errors} file(s) have syntax errors!")
    sys.exit(1)
else:
    print(f"\nAll {len(files)} files compiled successfully!")
