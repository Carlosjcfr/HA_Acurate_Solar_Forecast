import sys
import os

try:
    from custom_components.accurate_solar_forecast import config_flow
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
