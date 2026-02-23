import os

filepath = r"c:\Users\carlo\OneDrive\My_Projects\Domotica\Home Assistant\HA-Solar-Integrations\ha_acurate_solar_forecast\custom_components\accurate_solar_forecast\config_flow.py"

with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = lines[:186] + lines[550:]

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Done")
