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
    
    query = "roofing contractors Tyler TX"
    page.goto(f"https://www.google.com/maps/search/{query.replace(' ', '+')}", timeout=25000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    
    feed = page.locator('div[role="feed"]')
    feed.evaluate("el => el.scrollBy(0, 2000)")
    page.wait_for_timeout(2000)
    
    cards = page.locator('div[role="feed"] > div > div[jsaction]')
    print(f"Cards found: {cards.count()}")
    
    clicked = False
    for i in range(cards.count()):
        card = cards.nth(i)
        text = card.inner_text()
        if not text:
            continue
        
        web_link = card.locator('a[data-value="Website"], a[aria-label*="website" i]')
        if web_link.count() == 0:
            anchor = card.locator('a.hfpxzc')
            if anchor.count() > 0:
                name = anchor.first.get_attribute("aria-label")
                print(f"Found no-website roofer: {name}")
                print(f"Card raw text:\n{text}\n")
                
                # Click it
                anchor.first.click()
                page.wait_for_timeout(3000)
                
                # Check detail pane
                main = page.locator('div[role="main"]')
                print(f"Detail pane visible: {main.count()}")
                if main.count() > 0:
                    addr_btn = page.locator('button[data-item-id="address"], button[aria-label*="Address:" i]')
                    if addr_btn.count() > 0:
                        print("Detail Address Aria:", addr_btn.first.get_attribute("aria-label"))
                        print("Detail Address Inner:", addr_btn.first.inner_text())
                    
                    phone_btn = page.locator('button[data-item-id*="phone:"], button[aria-label*="Phone:" i]')
                    if phone_btn.count() > 0:
                        print("Detail Phone Aria:", phone_btn.first.get_attribute("aria-label"))
                        print("Detail Phone Inner:", phone_btn.first.inner_text())
                        
                    # All buttons in detail pane
                    buttons = main.locator('button')
                    print(f"Total buttons in detail pane: {buttons.count()}")
                    for b_idx in range(min(15, buttons.count())):
                        b_aria = buttons.nth(b_idx).get_attribute("aria-label")
                        b_text = buttons.nth(b_idx).inner_text().replace('\n', ' ')
                        if b_aria or b_text:
                            print(f"   Btn[{b_idx}]: aria='{b_aria}', text='{b_text}'")
                clicked = True
                break
    browser.close()
