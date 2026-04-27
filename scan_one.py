from playwright.sync_api import sync_playwright
import sys
import json
import time
from urllib.parse import urlparse
import re

# --- НАСТРОЙКИ ---
MAX_PAGES_TO_SCAN = 30
# ### FIX: Добавили задержку перед сбором кук, чтобы JS успел отработать
COOKIE_WAIT_TIME = 3 

CMP_SELECTORS = [
    ".cky-btn-accept", "button.cky-btn-accept", "[data-cky-tag='accept-button']",
    "#cookie_action_close_header", ".cli_action_button", "#wt-cli-accept-all-btn",
    "#onetrust-accept-btn-handler", "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    ".cc-btn.cc-allow", ".cc-btn.cc-dismiss", "button[data-testid='uc-accept-all-button']",
    ".qc-cmp2-summary-buttons button:first-child", "#didomi-notice-agree-button",
    ".truste-button1", "#ccc-notify-accept", ".cmplz-accept", ".iubenda-cs-accept-btn",
    ".ms-cookie-banner-button", "#accept-cookies", "#cookie-accept", ".accept-cookies-button",
    "button[id*='accept']", "button[class*='accept']", "a[class*='accept']"
]

ACCEPT_PATTERNS = [
    re.compile(r"accept\s+all", re.I), re.compile(r"allow\s+all", re.I),
    re.compile(r"accept", re.I), re.compile(r"allow", re.I), re.compile(r"agree", re.I),
    re.compile(r"got\s+it", re.I), re.compile(r"okay", re.I), re.compile(r"consent", re.I),
    re.compile(r"принять\s+вс[её]", re.I), re.compile(r"принять", re.I),
    re.compile(r"соглас(ен|на|иться)", re.I), re.compile(r"разрешить", re.I),
    re.compile(r"хорошо", re.I), re.compile(r"да,\s+я\s+согласен", re.I),
    re.compile(r"akzeptieren", re.I), re.compile(r"zustimmen", re.I),
    re.compile(r"accepter", re.I), re.compile(r"tout\s+accepter", re.I)
]

def handle_banner(page):
    def check_context(context, context_name="Main"):
        for selector in CMP_SELECTORS:
            try:
                # ### FIX: Используем waitFor, если элемент появляется с задержкой
                if context.locator(selector).first.is_visible():
                    btn = context.locator(selector).first
                    print(f"🎯 Banner found by ID ({context_name}): {selector}", file=sys.stderr)
                    btn.click()
                    time.sleep(1.5)
                    return True
            except: pass

        for pattern in ACCEPT_PATTERNS:
            try:
                btn = context.get_by_role("button", name=pattern).first
                if btn.is_visible():
                    print(f"📝 Banner button found by Regex ({context_name}): {pattern.pattern}", file=sys.stderr)
                    btn.click()
                    time.sleep(1.5)
                    return True
            except: pass
            
            try:
                element = context.get_by_text(pattern).first
                if element.is_visible():
                    print(f"⚠️ Banner text found (fallback) ({context_name}): {pattern.pattern}", file=sys.stderr)
                    element.click(force=True)
                    time.sleep(1.5)
                    return True
            except: pass
        return False

    if check_context(page, "Main Page"): return True
    for frame in page.frames:
        if frame == page.main_frame: continue
        try:
            if check_context(frame, "iFrame"): return True
        except: pass
    return False

def get_internal_links(page, base_domain, current_url):
    links_found = set()
    try:
        hrefs = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a')).map(a => a.href);
        }""")
        for href in hrefs:
            href = href.split('#')[0].rstrip('/')
            if not href: continue
            parsed = urlparse(href)
            if parsed.netloc == base_domain:
                if not any(href.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.css', '.js', '.zip']):
                     links_found.add(href)
        del hrefs 
        return links_found
    except:
        return set()

def scan(start_url):
    unique_cookies = {}
    unique_local_storage = set() # <--- ДОБАВИТЬ ЭТО (set поможет избежать дубликатов) 
    queue = [start_url]
    visited = set()
    base_domain = urlparse(start_url).netloc
    pages_scanned = 0

    with sync_playwright() as p:
        #  Маскировка под реального пользователя
        # Отключаем флаги автоматизации Chrome
        browser = p.chromium.launch(
            headless=True, # Попробуйте False, если все равно не работает!
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US,en;q=0.9" # Некоторые сайты смотрят на локаль
        )
        
        #  Скрипт для удаления признаков webdriver
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.new_page()

        try:
            while queue and pages_scanned < MAX_PAGES_TO_SCAN:
                url = queue.pop(0)
                if url in visited: continue
                
                visited.add(url)
                pages_scanned += 1
                
                try:
                    #  WaitUntil = NetworkIdle
                    # Ждем, пока закончатся сетевые запросы (загрузятся скрипты аналитики)
                    # Если сайт слишком медленный, networkidle может отваливаться по таймауту, тогда используйте 'load'
                    try:
                        page.goto(url, wait_until="networkidle", timeout=30000)
                    except:
                        # Если networkidle не сработал за 30 сек, пробуем просто domcontentloaded
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)

                    if pages_scanned <= 3:
                        handle_banner(page)

                    # Скролл
                    page.mouse.wheel(0, 3000)
                    time.sleep(COOKIE_WAIT_TIME) # Даем время скриптам поставить куки
                    
                    # 4. Сбор куки
                    current_cookies = context.cookies()
                    for c in current_cookies:
                        unique_cookies[c['name']] = c
                    # 5. Сбор LocalStorage
                    try:
                        # Берем только названия ключей, чтобы не тащить лишние данные
                        ls_keys = page.evaluate("() => Object.keys(localStorage)")
                        for key in ls_keys:
                            unique_local_storage.add(key)
                    except:
                        pass

                    new_links = get_internal_links(page, base_domain, url)
                    for link in new_links:
                        if link not in visited and link not in queue:
                            queue.append(link)
                    
                except Exception as e:
                    print(f"Error scanning {url}: {e}", file=sys.stderr)

            return {
                "url": start_url,
                "cookies": list(unique_cookies.values()),
                "local_storage": list(unique_local_storage),
                "cookie_count": len(unique_cookies),
                "pages_scanned": pages_scanned,
                "visited_urls": list(visited)
            }

        except Exception as e:
            return {"error": str(e)}
        finally:
            browser.close()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    data = scan(url)
    print(json.dumps(data, indent=2))