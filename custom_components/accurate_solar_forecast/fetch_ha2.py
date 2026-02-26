import urllib.request
import re
import traceback

try:
    url = "https://raw.githubusercontent.com/home-assistant/frontend/dev/src/panels/config/integrations/integration-panels/config-entry/ha-config-integration-page.ts"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla'})
    r = urllib.request.urlopen(req)
    content = r.read().decode('utf-8')
    with open("ha_out.txt", "w", encoding="utf-8") as out:
        matches = re.finditer(r'config_subentries', content)
        for m in matches:
            start = max(0, m.start() - 100)
            end = min(len(content), m.end() + 200)
            out.write("-------\n")
            out.write(content[start:end] + "\n")
except Exception as e:
    with open("ha_out.txt", "w") as out:
        out.write(str(e))
