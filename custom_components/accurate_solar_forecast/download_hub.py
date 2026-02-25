import urllib.request
url = 'https://raw.githubusercontent.com/home-assistant/frontend/dev/src/panels/config/integrations/integration-panels/hub/ha-integration-hub-panel.ts'
try:
    content = urllib.request.urlopen(url).read().decode('utf-8')
    with open('hub_panel.ts', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
except Exception as e:
    print(e)
