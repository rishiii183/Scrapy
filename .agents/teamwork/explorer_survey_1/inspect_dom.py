import re

with open('test_chrome_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

print("File Length:", len(text))
title = re.findall(r'<title>(.*?)</title>', text)
print("Title:", title)

# Look for aria-label or role="feed" or role="article"
feed = re.findall(r'role="feed"', text)
print("role=feed found:", len(feed))

# Look for business links /maps/place/
place_links = re.findall(r'href="(/maps/place/[^"]*)"', text)
print("place links found:", len(place_links))
for link in place_links[:5]:
    print(" - Place link:", link[:80])

# Look for text with roofer names
names = re.findall(r'aria-label="([^"]+)"', text)
print("aria-labels count:", len(names))
roofer_labels = [n for n in names if any(k in n.lower() for k in ['roof', 'contractor', 'construction'])]
print("Roofer aria-labels:", len(roofer_labels))
for rl in roofer_labels[:5]:
    print(" -", rl)
