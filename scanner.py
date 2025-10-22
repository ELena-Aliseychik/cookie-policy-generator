from playwright.sync_api import sync_playwright

def scan(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            cookies = page.context.cookies()
        finally:
            browser.close()
        return cookies

