import urllib.request
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
url = 'https://raw.githubusercontent.com/home-assistant/core/dev/homeassistant/components/mqtt/strings.json'
r = urllib.request.urlopen(url)
d = json.loads(r.read())
with open("test.txt", "w") as f:
    json.dump(d.get('config_subentries', {}), f, indent=2)
