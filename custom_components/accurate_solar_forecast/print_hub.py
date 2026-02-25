import urllib.request
url = 'https://raw.githubusercontent.com/home-assistant/frontend/dev/src/panels/config/integrations/integration-panels/hub/ha-integration-hub-panel.ts'
try:
    content = urllib.request.urlopen(url).read().decode('utf-8')
    for line in content.split('\n'):
        if 'localize' in line or 'config_subentries' in line or 'name' in line or 'title' in line:
            print(line.strip()[:100])
except Exception as e:
    print(e)
