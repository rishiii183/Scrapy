import os
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
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900}
    )
    
    # Let's inspect A&W Hill Roofing & Construction in Tyler TX (14 reviews, no website)
    query = "A&W Hill Roofing & Construction Tyler TX"
    page.goto(f"https://www.google.com/maps/search/{query.replace(' ', '+')}", timeout=25000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    
    # When single result matches, Google Maps often navigates directly to place view
    text = page.locator('div[role="main"]').inner_text()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    print(f"Total lines in place view: {len(lines)}")
    for i, line in enumerate(lines[:35]):
        print(f" [{i}]: {line}")
        
    # Check for services tab or section
    service_els = page.locator('div[aria-label*="Service" i], div:has-text("Services"), button:has-text("Services")')
    print("Service locators found:", service_els.count())
    for s_idx in range(min(5, service_els.count())):
        print(f" Service el [{s_idx}]: {service_els.nth(s_idx).inner_text()[:100]}")

    browser.close()
