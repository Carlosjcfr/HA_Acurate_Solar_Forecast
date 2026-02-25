import urllib.request
import json
url = 'https://raw.githubusercontent.com/home-assistant/frontend/dev/src/panels/config/integrations/integration-panels/hub/ha-integration-hub-panel.ts'
try:
    content = urllib.request.urlopen(url).read().decode('utf-8')
    res = []
    for line in content.split('\n'):
        if 'title' in line or 'name' in line or 'config_subentries' in line or 'localize' in line or 'mwc-button' in line:
            res.append(line)
    with open('hub_panel.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(res))
    print("Done")
except Exception as e:
    with open('hub_panel.txt', 'w') as f:
        f.write(str(e))
