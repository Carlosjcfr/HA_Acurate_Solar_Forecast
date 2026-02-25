import urllib.request
import json
url = 'https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/mqtt/strings.json'
try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode('utf-8'))
        print(json.dumps(data.get('config_subentries', {}), indent=2))
except Exception as e:
    print(e)
