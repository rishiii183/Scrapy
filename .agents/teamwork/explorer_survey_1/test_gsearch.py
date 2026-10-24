import httpx
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
}

url = 'https://www.google.com/search?q=roofing+contractors+in+Dallas+TX'
r = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
print(f"Status: {r.status_code}, Length: {len(r.text)}")

# Check for local pack
matches = re.findall(r'([A-Za-z0-9\s&,.-]+(?:Roofing|Roof)[A-Za-z0-9\s&,.-]*)', r.text)
print("Found roofer mentions in search:", len(matches))
for m in matches[:10]:
    if len(m.strip()) > 5:
        print(" -", m.strip())

# Check for phone numbers
phones = re.findall(r'\(?\b[2-9][0-9]{2}\)?[-.\s]?[2-9][0-9]{2}[-.\s]?[0-9]{4}\b', r.text)
print("Found phones:", len(phones), phones[:5])
