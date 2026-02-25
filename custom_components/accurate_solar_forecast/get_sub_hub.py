import urllib.request

url = 'https://raw.githubusercontent.com/home-assistant/frontend/dev/src/panels/config/integrations/integration-panels/hub/ha-integration-hub-panel.ts'
try:
    with urllib.request.urlopen(url) as response:
        content = response.read().decode('utf-8')
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if 'config_subentries' in line or 'localize(' in line or 'mwc-button' in line or 'ha-fab' in line or 'ha-button' in line:
                print(f"{i}: {line.strip()}")
except Exception as e:
    print(e)
