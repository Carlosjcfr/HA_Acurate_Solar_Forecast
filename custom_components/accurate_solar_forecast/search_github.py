import urllib.request
import json
import traceback

def search_frontend():
    req = urllib.request.Request(
        'https://api.github.com/search/code?q=config_subentries+repo:home-assistant/frontend',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read())
        for item in data.get('items', [])[:5]:
            print(f"File: {item['path']}")
            print(f"URL: {item['html_url']}")
            print("---")
    except Exception as e:
        traceback.print_exc()

search_frontend()
