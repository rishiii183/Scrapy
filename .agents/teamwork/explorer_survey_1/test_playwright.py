import sys
import os

from playwright.sync_api import sync_playwright

chrome_path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
print(f"Testing Chrome at: {chrome_path}, exists={os.path.exists(chrome_path)}")

with sync_playwright() as p:
    try:
        print("Attempting to launch browser...")
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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        print("Navigating to Google Maps search...")
        page.goto("https://www.google.com/maps/search/roofing+contractors+in+Dallas+TX", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        
        title = page.title()
        print(f"Page title: {title}")
        
        # Check if consent / accept button exists
        for text in ["Accept all", "I agree", "Reject all"]:
            btn = page.get_by_role("button", name=text)
            if btn.count() > 0:
                print(f"Found consent button: {text}, clicking...")
                btn.first.click()
                page.wait_for_timeout(2000)
        
        # Check feed items
        feed = page.locator('div[role="feed"]')
        print(f"Found role='feed': {feed.count()}")
        
        # Let's find place links / articles
        places = page.locator('div[role="article"], a[href*="/maps/place/"]')
        print(f"Found place locators: {places.count()}")
        
        # Let's inspect first few
        for i in range(min(5, places.count())):
            aria = places.nth(i).get_attribute("aria-label")
            text = places.nth(i).inner_text().replace("\n", " | ")
            print(f" Place [{i}]: aria='{aria}', text='{text[:100]}'")

        browser.close()
        print("Success! Headless Chrome via Playwright works seamlessly.")
    except Exception as e:
        print(f"Error during Playwright test: {e}")
