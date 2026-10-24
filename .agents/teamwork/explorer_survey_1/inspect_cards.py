import os
import sys
import re
from playwright.sync_api import sync_playwright

chrome_path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")

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
    
    query = "roofing contractors in Lubbock TX"
    print(f"Searching: {query}", flush=True)
    page.goto(f"https://www.google.com/maps/search/{query.replace(' ', '+')}", timeout=25000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    # Let's inspect the feed
    feed = page.locator('div[role="feed"]')
    print(f"Feed count: {feed.count()}", flush=True)
    
    # In Google Maps feed, each business item has class or is an anchor tag or article
    # Typically: a.hfpxzc (the place link overlay)
    place_anchors = page.locator('a.hfpxzc')
    print(f"Found a.hfpxzc anchors: {place_anchors.count()}", flush=True)

    # Let's see all items in feed
    items = page.locator('div[role="feed"] > div > div[jsaction]')
    print(f"Found div[jsaction] cards: {items.count()}", flush=True)
    
    # Let's inspect each card
    for i in range(min(10, place_anchors.count())):
        anchor = place_anchors.nth(i)
        name = anchor.get_attribute("aria-label")
        href = anchor.get_attribute("href")
        
        # Parent container
        parent = anchor.locator('xpath=..')
        text = parent.inner_text().strip().replace("\n", " | ")
        
        # Look for website link in parent or sibling
        website_el = parent.locator('a[data-value="Website"], a[aria-label*="website" i], a[href*="http"]:not([href*="google.com"])')
        has_web = website_el.count() > 0
        web_url = website_el.first.get_attribute("href") if has_web else None
        
        print(f"\nItem [{i}]: Name='{name}'", flush=True)
        print(f"  Href: {href[:60]}...", flush=True)
        print(f"  Summary text: {text[:140]}", flush=True)
        print(f"  Website link: {web_url} (Found: {has_web})", flush=True)

    browser.close()
    print("\nDone!", flush=True)
