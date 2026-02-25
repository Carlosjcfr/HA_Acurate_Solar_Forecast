import urllib.request
import zipfile
import io

url = "https://github.com/dalathegreat/haeo/archive/refs/heads/main.zip"
response = urllib.request.urlopen(url)
with zipfile.ZipFile(io.BytesIO(response.read())) as z:
    z.extractall("haeo_extracted")
print("Done extracting haeo")
