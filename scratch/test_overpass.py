import urllib.request
import json

url = "https://overpass-api.de/api/interpreter"
query = '[out:json][timeout:15];node["man_made"="webcam"];out 150;'
req = urllib.request.Request(url, data=query.encode('utf-8'), headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        elems = data.get("elements", [])
        print("Total webcams found:", len(elems))
        valid = 0
        for e in elems[:15]:
            tags = e.get("tags", {})
            url_val = tags.get("url") or tags.get("contact:webcam") or tags.get("image") or tags.get("website")
            if url_val:
                valid += 1
                print(f"Name: {tags.get('name', 'Cam')}, Lat: {e.get('lat')}, Lng: {e.get('lon')}, URL: {url_val}")
        print("Valid with URLs in first 15:", valid)
except Exception as err:
    print("Error:", err)
