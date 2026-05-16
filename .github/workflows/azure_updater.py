import re
import sys
from pathlib import Path
import requests

PAGE_URL = "https://www.microsoft.com/en-us/download/details.aspx?id=56519"
OUTPUT_FILE = "azure/ServiceTags_Public.json"
print(f"Fetching download page: {PAGE_URL}")
response = requests.get(PAGE_URL, timeout=30)
response.raise_for_status()
match = re.search(
    r"https://download\.microsoft\.com/download/[^\"]+ServiceTags_Public_[0-9]+\.json",
    response.text,
)
if not match:
    print("Could not find Azure Service Tags download URL")
    sys.exit(1)
download_url = match.group(0)
print(f"Found download URL:\n{download_url}")
print("Downloading JSON file...")
download_response = requests.get(download_url, timeout=300)
download_response.raise_for_status()
Path(OUTPUT_FILE).write_bytes(download_response.content)
size_mb = len(download_response.content) / 1024 / 1024
print(f"Saved to {OUTPUT_FILE} ({size_mb:.2f} MB)")