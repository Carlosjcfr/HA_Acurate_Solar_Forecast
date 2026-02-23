import os

filepath = r"c:\Users\carlo\OneDrive\My_Projects\Domotica\Home Assistant\HA-Solar-Integrations\ha_acurate_solar_forecast\custom_components\accurate_solar_forecast\config_flow.py"

with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = lines[:186] + lines[550:]

# Insert imports at line 7
imports = [
    "from .flow_pv_models import PvModelsFlowMixin\n",
    "from .flow_roofs import RoofsFlowMixin\n",
    "from .flow_sensor_groups import SensorGroupsFlowMixin\n",
    "from .flow_strings import StringsFlowMixin\n"
]
new_lines = new_lines[:6] + imports + new_lines[6:]

# Modificar clase
for i, line in enumerate(new_lines):
    if line.startswith("class AccurateForecastFlow("):
        new_lines[i] = "class AccurateForecastFlow(AccurateForecastCommonFlow, PvModelsFlowMixin, RoofsFlowMixin, SensorGroupsFlowMixin, StringsFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):\n"
        break

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
