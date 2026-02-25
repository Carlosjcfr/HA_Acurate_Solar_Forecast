import urllib.request
import zipfile
import io

url = "https://github.com/dalathegreat/haeo/archive/refs/heads/main.zip"
print("Downloading...")
response = urllib.request.urlopen(url)
print("Extracting...")
with zipfile.ZipFile(io.BytesIO(response.read())) as z:
    z.extractall("C:\\temp\\haeo")
print("Done")
