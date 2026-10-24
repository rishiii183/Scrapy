import httpx
import re
import json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

url = 'https://www.google.com/maps/search/roofing+contractors+in+Dallas+TX'
r = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)

# Find any strings containing "Roof" or "Roofing" in r.text
print("Searching raw text for roofing companies:")
matches = re.findall(r'(\[[^\]]*Roof[^\]]*\])', r.text)
print(f"Found {len(matches)} matches")
for m in matches[:5]:
    print("Match:", m[:150])

# Also let's check APP_INITIALIZATION_STATE
match = re.search(r'window\.APP_INITIALIZATION_STATE\s*=\s*(.*?);window\.', r.text)
if match:
    data = json.loads(match.group(1))
    raw_payload = data[3][1]
    if raw_payload.startswith(")]}'\n"):
        raw_payload = raw_payload[5:]
    parsed = json.loads(raw_payload)
    
    # Recursive search in parsed
    def find_paths(obj, target="roof", path=""):
        if isinstance(obj, str):
            if target.lower() in obj.lower():
                print(f"Found '{target}' at {path}: {obj[:80]}")
        elif isinstance(obj, list):
            for i, val in enumerate(obj):
                find_paths(val, target, f"{path}[{i}]")
        elif isinstance(obj, dict):
            for k, val in enumerate(obj):
                find_paths(val, target, f"{path}.{k}")

    print("\nSearching parsed structure:")
    find_paths(parsed, "Roofing")
