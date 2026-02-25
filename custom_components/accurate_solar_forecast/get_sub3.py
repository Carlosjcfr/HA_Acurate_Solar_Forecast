import urllib.request
import json
url = 'https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/mqtt/strings.json'
try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode('utf-8'))
        with open('output_mqtt.json', 'w') as f:
            json.dump(data.get('config_subentries', {}), f, indent=2)
except Exception as e:
    with open('output_mqtt.json', 'w') as f:
        f.write(str(e))
