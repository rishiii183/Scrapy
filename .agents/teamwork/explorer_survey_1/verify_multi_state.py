import os
import re
import json
import time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

chrome_path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")

SOCIAL_AND_DIRECTORIES = {
    "facebook.com", "m.facebook.com", "fb.me",
    "instagram.com", "linkedin.com", "twitter.com", "x.com", "tiktok.com", "youtube.com",
    "yelp.com", "bbb.org", "yellowpages.com", "angi.com", "angieslist.com",
    "homeadvisor.com", "thumbtack.com", "houzz.com", "nextdoor.com",
    "manta.com", "mapquest.com", "superpages.com", "chamberofcommerce.com",
    "porch.com", "buildzoom.com", "dandb.com", "expertise.com", "bark.com"
}

def clean_phone(raw_phone):
    if not raw_phone:
        return None
    digits = re.sub(r'\D', '', raw_phone)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw_phone.strip()

def normalize_name(name):
    if not name:
        return ""
    clean = name.lower()
    clean = re.sub(r'\b(llc|inc|corp|co|ltd|company|roofing|construction|contractor|contracting)\b', '', clean)
    clean = re.sub(r'[^a-z0-9]', '', clean)
    return clean.strip()

def is_social_or_directory(url):
    if not url:
        return False
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return any(domain == d or domain.endswith("." + d) for d in SOCIAL_AND_DIRECTORIES)

def classify_specialty(name, raw_text):
    text = f"{name} {raw_text}".lower()
    if any(k in text for k in ["commercial", "tpo", "epdm", "flat roof", "industrial"]):
        return "commercial"
    elif any(k in text for k in ["storm", "hail", "wind", "disaster", "restoration", "insurance claim"]):
        return "storm repair"
    elif any(k in text for k in ["leak", "emergency leak", "waterproofing", "patch", "flashing"]):
        return "leak repair"
    else:
        return "residential"

def parse_address_string(addr_str, default_city, default_state):
    # Format e.g.: "7922 S Broadway Ave, Tyler, TX 75703, United States"
    # or "Tyler, TX 75703"
    city = default_city
    state = default_state
    zip_code = None
    
    if addr_str:
        # Match US zip code: 5 digits
        zip_match = re.search(r'\b([0-9]{5})(?:-[0-9]{4})?\b', addr_str)
        if zip_match:
            zip_code = zip_match.group(1)
            
        # Match State and ZIP: e.g., TX 75703 or Texas 75703
        state_match = re.search(r',\s*([A-Z]{2})\s+[0-9]{5}', addr_str)
        if state_match:
            state = state_match.group(1)
            
        parts = [p.strip() for p in addr_str.split(',') if p.strip()]
        if len(parts) >= 3:
            # Usually [Street, City, State ZIP, Country]
            city = parts[-3] if "united states" in parts[-1].lower() else parts[-2]
            
    return city, state, zip_code

# Queries covering target US states: TX, FL, OH, GA, AZ
QUERIES = [
    {"query": "roofing contractors Tyler TX", "city": "Tyler", "state": "TX"},
    {"query": "roofing contractor Ocala FL", "city": "Ocala", "state": "FL"},
    {"query": "roof repair contractor Canton OH", "city": "Canton", "state": "OH"},
    {"query": "roofers Macon GA", "city": "Macon", "state": "GA"},
    {"query": "roofing contractors Flagstaff AZ", "city": "Flagstaff", "state": "AZ"}
]

print("Ready to run multi-state verification...")

def run_multi_state_survey():
    extracted_leads = []
    seen_dedup_keys = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=chrome_path,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--lang=en-US,en"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        for target in QUERIES:
            q = target["query"]
            def_city = target["city"]
            def_state = target["state"]
            
            print(f"\n--- Scraping region: {q} ({def_state}) ---", flush=True)
            page.goto(f"https://www.google.com/maps/search/{q.replace(' ', '+')}", timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            feed = page.locator('div[role="feed"]')
            if feed.count() == 0:
                print("No feed found, skipping...", flush=True)
                continue
                
            # Scroll feed 4 times to populate list
            for s in range(4):
                feed.evaluate("el => el.scrollBy(0, 1500)")
                page.wait_for_timeout(1200)
                
            cards = page.locator('div[role="feed"] > div > div[jsaction]')
            count = cards.count()
            print(f"Loaded {count} cards in feed.", flush=True)
            
            for i in range(count):
                card = cards.nth(i)
                text = card.inner_text().strip()
                if not text:
                    continue
                
                anchor = card.locator('a.hfpxzc')
                if anchor.count() == 0:
                    continue
                name = anchor.first.get_attribute("aria-label")
                if not name:
                    continue
                    
                # Website element check
                web_link = card.locator('a[data-value="Website"], a[aria-label*="website" i]')
                raw_website = None
                if web_link.count() > 0:
                    raw_website = web_link.first.get_attribute("href")
                    
                # Strict Website filtering
                if raw_website:
                    if not is_social_or_directory(raw_website):
                        # Has custom website -> Strictly skip!
                        continue
                    else:
                        website_val = f"Social/Directory: {raw_website}"
                else:
                    website_val = "No Website"
                    
                # Phone extraction
                phone_match = re.search(r'(\+?1?[-.\s]?\(?[2-9][0-9]{2}\)?[-.\s]?[2-9][0-9]{2}[-.\s]?[0-9]{4})', text)
                raw_phone = phone_match.group(1).strip() if phone_match else None
                cleaned_phone = clean_phone(raw_phone)
                
                # Rating and Reviews
                rating_match = re.search(r'([1-5]\.[0-9])\s*\(([0-9,]+)\)', text)
                star_rating = float(rating_match.group(1)) if rating_match else None
                review_count = int(rating_match.group(2).replace(",", "")) if rating_match else 0
                
                # Address parsing from card lines
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                # Address often appears in lines containing street number or city
                addr_line = None
                for line in lines:
                    if re.search(r'\b[0-9]{1,5}\s+[A-Za-z0-9\s.,#-]+', line) and not line.startswith('+1'):
                        addr_line = line
                        break
                        
                city, state, zip_code = parse_address_string(addr_line, def_city, def_state)
                
                # Specialty classification
                specialty = classify_specialty(name, text)
                
                # Deduplication key: normalized_phone or normalized_name + state
                norm_phone = re.sub(r'\D', '', cleaned_phone or "")
                norm_name = normalize_name(name)
                dedup_key = norm_phone if norm_phone else f"{norm_name}_{state}"
                
                if dedup_key in seen_dedup_keys:
                    continue
                seen_dedup_keys.add(dedup_key)
                
                lead_data = {
                    "company_name": name,
                    "phone": cleaned_phone,
                    "city": city,
                    "state": state,
                    "zip_code": zip_code,
                    "review_count": review_count,
                    "star_rating": star_rating,
                    "primary_specialty": specialty,
                    "website_status": website_val,
                    "priority": "🔥 High" if review_count > 10 else "Standard",
                    "search_query": q
                }
                
                extracted_leads.append(lead_data)
                print(f"  [+] Captured: {name} | {cleaned_phone} | {city}, {state} | {specialty} | {website_val} | {lead_data['priority']}", flush=True)

        browser.close()
        
    print(f"\n==========================================", flush=True)
    print(f"TOTAL UNIQUE LEADS EXTRACTED: {len(extracted_leads)}", flush=True)
    with open("verified_leads_sample.json", "w", encoding="utf-8") as f:
        json.dump(extracted_leads, f, indent=2)
    print("Saved to verified_leads_sample.json", flush=True)
    return extracted_leads

if __name__ == "__main__":
    run_multi_state_survey()

