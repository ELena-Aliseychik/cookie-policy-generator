from playwright.sync_api import sync_playwright
import json
import sys


def scan_site(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        requests = []
        page.on("request", lambda req: requests.append(req.url))

        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print("Warning during goto:", e)

        cookies = context.cookies()
        browser.close()

    return {"url": url, "cookies": cookies, "requests": requests}


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    data = scan_site(url)
    print(json.dumps(data, indent=2))
