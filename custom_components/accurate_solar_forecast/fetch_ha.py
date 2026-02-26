import urllib.request
import re
import traceback

try:
    url = "https://raw.githubusercontent.com/home-assistant/frontend/dev/src/panels/config/integrations/integration-panels/config-entry/ha-config-integration-page.ts"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla'})
    r = urllib.request.urlopen(req)
    content = r.read().decode('utf-8')
    matches = re.finditer(r'config_subentries', content)
    for m in matches:
        start = max(0, m.start() - 100)
        end = min(len(content), m.end() + 200)
        print("-------")
        print(content[start:end])
    with open("frontend_code.txt", "w", encoding="utf-8") as f:
        f.write(content)
except Exception as e:
    traceback.print_exc()
