import sys
import traceback
import os

sys.path.append(os.getcwd())

try:
    import custom_components.accurate_solar_forecast.config_flow
    print("SUCCESS")
except Exception as e:
    traceback.print_exc()
