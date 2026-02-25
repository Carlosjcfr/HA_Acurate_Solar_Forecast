import urllib.request
import json
url = 'https://api.github.com/search/code?q=%22A%C3%B1adir+hub%22'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(e)
