import urllib.request
import json

url = 'https://api.github.com/search/code?q=async_get_supported_subentry_types+repo:home-assistant/core'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
        paths = [i['path'] for i in data.get('items', [])]
        print(paths)
except Exception as e:
    print(e)
