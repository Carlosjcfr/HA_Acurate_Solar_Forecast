import urllib.request
with open('haeo_config_flow.py', 'wb') as f:
    f.write(urllib.request.urlopen('https://raw.githubusercontent.com/dalathegreat/haeo/main/custom_components/haeo/config_flow.py').read())
with open('haeo_strings.json', 'wb') as f:
    f.write(urllib.request.urlopen('https://raw.githubusercontent.com/dalathegreat/haeo/main/custom_components/haeo/strings.json').read())
