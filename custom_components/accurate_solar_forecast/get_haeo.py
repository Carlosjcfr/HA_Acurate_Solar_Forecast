import urllib.request
import json
url = 'https://raw.githubusercontent.com/dalathegreat/haeo/main/custom_components/haeo/manifest.json'
try:
    with urllib.request.urlopen(url) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(e)
