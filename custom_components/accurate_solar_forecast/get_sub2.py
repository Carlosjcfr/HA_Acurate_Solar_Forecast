import urllib.request
import json
urls = [
    'https://raw.githubusercontent.com/home-assistant/frontend/dev/src/dialogs/config-flow/step-flow-form.ts',
    'https://raw.githubusercontent.com/home-assistant/frontend/dev/src/panels/config/integrations/integration-panels/hub/ha-integration-hub-panel.ts',
    'https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/mqtt/strings.json'
]

for url in urls:
    try:
        if 'strings.json' in url:
            data = json.loads(urllib.request.urlopen(url).read().decode('utf-8'))
            print("MQTT:", json.dumps(data.get('config_subentries', {}), indent=2))
        else:
            text = urllib.request.urlopen(url).read().decode('utf-8')
            for line in text.splitlines():
                if 'subentry' in line.lower() or 'button' in line.lower() or 'localize' in line.lower():
                    pass # Just taking a look
    except Exception:
        pass
