import os
import sys
import re
import time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

chrome_path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")

def is_social_or_directory(url):
    if not url:
        return False
    domain = urlparse(url).netloc.lower()
    directories = [
        "facebook.com", "m.facebook.com", "instagram.com",
        "yelp.com", "bbb.org", "yellowpages.com", "angi.com",
        "homeadvisor.com", "thumbtack.com", "houzz.com",
        "linkedin.com", "nextdoor.com", "mapquest.com",
        "superpages.com", "manta.com", "chamberofcommerce.com"
    ]
    return any(d in domain for d in directories)

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
    
    # Query: roofing contractors in rural Texas or specific towns like Tyler TX, Waco TX, Abilene TX, Midland TX
    queries = [
        "roofing contractors Tyler TX",
        "roof repair contractor Abilene TX",
        "roofers Macon GA"
    ]
    
    no_website_leads = []
    
    for q in queries:
        print(f"\n==========================================", flush=True)
        print(f"Executing search: {q}", flush=True)
        print(f"==========================================", flush=True)
        
        page.goto(f"https://www.google.com/maps/search/{q.replace(' ', '+')}", timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        feed = page.locator('div[role="feed"]')
        if feed.count() == 0:
            print("No feed found")
            continue
            
        # Scroll feed 3 times to load more
        for scroll_idx in range(3):
            feed.evaluate("el => el.scrollBy(0, 1500)")
            page.wait_for_timeout(1500)
            
        cards = page.locator('div[role="feed"] > div > div[jsaction]')
        count = cards.count()
        print(f"Total cards visible after scrolling: {count}", flush=True)
        
        for i in range(count):
            card = cards.nth(i)
            text = card.inner_text().strip()
            if not text:
                continue
            
            # Place anchor
            anchor = card.locator('a.hfpxzc')
            if anchor.count() == 0:
                continue
            name = anchor.first.get_attribute("aria-label")
            if not name:
                continue
                
            # Website link
            # Look for <a> with data-value="Website" or aria-label containing website
            web_link = card.locator('a[data-value="Website"], a[aria-label*="website" i]')
            website = None
            if web_link.count() > 0:
                website = web_link.first.get_attribute("href")
            
            # Check phone number
            phone_match = re.search(r'(\+?1?[-.\s]?\(?[2-9][0-9]{2}\)?[-.\s]?[2-9][0-9]{2}[-.\s]?[0-9]{4})', text)
            phone = phone_match.group(1).strip() if phone_match else None
            
            # Check rating and reviews
            rating_match = re.search(r'([1-5]\.[0-9])\s*\(([0-9,]+)\)', text)
            rating = rating_match.group(1) if rating_match else None
            reviews = rating_match.group(2).replace(",", "") if rating_match else "0"
            
            # Website filtering
            has_no_website = (website is None) or is_social_or_directory(website)
            
            if has_no_website:
                status_type = "NO_WEBSITE" if website is None else f"DIRECTORY_ONLY ({urlparse(website).netloc})"
                no_website_leads.append({
                    "query": q,
                    "name": name,
                    "phone": phone,
                    "rating": rating,
                    "reviews": reviews,
                    "website": website,
                    "status_type": status_type,
                    "raw_text": text.replace("\n", " | ")[:120]
                })
                print(f"🎯 FOUND LEAD [{status_type}]: {name} | Phone: {phone} | Rating: {rating} ({reviews} revs)", flush=True)
                if website:
                    print(f"   Social/Directory URL: {website}", flush=True)
                    
    browser.close()
    print(f"\n==========================================", flush=True)
    print(f"TOTAL QUALIFIED LEADS (No website or social only): {len(no_website_leads)}", flush=True)
    for idx, lead in enumerate(no_website_leads[:15]):
        print(f"{idx+1}. {lead['name']} | {lead['phone']} | {lead['rating']} ({lead['reviews']} reviews) | {lead['status_type']}", flush=True)
