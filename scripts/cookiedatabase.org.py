"""Scrape cookiedatabase.org and extract slim cookie metadata.

Pipeline:
  1. Enumerate all services from /wp-json/wp/v2/service.
  2. For each service page, collect cookie URLs from #hiddenCookies.
  3. For each cookie page, extract: name, vendor, category, functionality,
     expiration.
  4. For each unique service, scrape the service page once to find the
     vendor's privacy-policy URL. Store it in `service_url`.

Output: ../databases/cookiedatabase.org.csv (semicolon-separated).
"""

import csv
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

API = "https://cookiedatabase.org/wp-json/wp/v2/service"
PER_PAGE = 100
MAX_WORKERS = 4
MAX_RETRIES = 5
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "databases" / "cookiedatabase.org.csv"
CSV_DELIMITER = ";"
CHECKPOINT_EVERY = 500

CSV_FIELDS = [
    "name", "vendor", "category", "functionality", "expiration",
    "service_name", "service_url",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (cookie-policy-generator scraper)"}

session = requests.Session()
session.headers.update(HEADERS)


# ---------- HTTP: retry with backoff on 429/503 ----------

def polite_get(url: str, **kwargs) -> requests.Response:
    """GET with exponential backoff on 429/503."""
    kwargs.setdefault("timeout", 30)
    for attempt in range(MAX_RETRIES):
        r = session.get(url, **kwargs)
        if r.status_code in (429, 503):
            retry_after = r.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = int(retry_after)
            else:
                delay = (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(min(delay, 60))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


# ---------- WP REST API ----------

def fetch_services_page(page: int) -> list[dict]:
    try:
        r = polite_get(API, params={"per_page": PER_PAGE, "page": page})
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 400:
            return []
        raise
    return r.json()


def fetch_all_services() -> list[dict]:
    services = []
    page = 1
    while True:
        batch = fetch_services_page(page)
        if not batch:
            break
        services.extend(batch)
        page += 1
    return services


# ---------- Service page → cookie URL list ----------

def scrape_service_cookies(service_url: str) -> list[str]:
    r = polite_get(service_url)
    soup = BeautifulSoup(r.text, "html.parser")
    section = soup.find(id="hiddenCookies")
    if section is None:
        return []
    urls = []
    for article in section.find_all("article"):
        h3 = article.find("h3")
        if not h3:
            continue
        a = h3.find("a")
        if not a:
            continue
        href = a.get("href")
        if href:
            urls.append(href)
    return urls


# ---------- Service page → vendor privacy URL ----------

def scrape_vendor_privacy_url(service_page_url: str) -> str | None:
    """Best-effort vendor privacy-policy URL from a service page.

    Service pages display 'Legal: <url>' linking to the vendor's privacy
    policy. Some pages have placeholder/malformed text instead — we filter
    those out by requiring a parseable host with no whitespace.
    """
    try:
        r = polite_get(service_page_url)
    except requests.RequestException:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if not text.lower().startswith("legal"):
            continue
        href = a["href"]
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https"):
            continue
        if " " in parsed.netloc or "%20" in parsed.netloc or not parsed.netloc:
            continue
        if "cookiedatabase.org" in parsed.netloc:
            continue
        return href
    return None


# ---------- Cookie detail page ----------

def _strip_label(text: str, label: str) -> str:
    pattern = re.compile(r"^\s*" + re.escape(label) + r"\s*:?\s*", re.I)
    return pattern.sub("", text, count=1).strip()


def scrape_cookie_detail(cookie_url: str) -> dict:
    r = polite_get(cookie_url)
    soup = BeautifulSoup(r.text, "html.parser")

    h1 = soup.find("h1")
    name = h1.get_text(strip=True) if h1 else None

    h2 = soup.find("h2")
    vendor = h2.get_text(strip=True) if h2 else None

    h3s = soup.find_all("h3")
    functionality = h3s[0].get_text(strip=True) if len(h3s) >= 1 else None
    category = h3s[1].get_text(strip=True) if len(h3s) >= 2 else None

    expiration = None
    for a in soup.select("a.elementor-accordion-title"):
        t = a.get_text(" ", strip=True)
        if t.lower().startswith("expiration period"):
            expiration = _strip_label(t, "Expiration period")
            break

    return {
        "name": name,
        "vendor": vendor,
        "category": category,
        "functionality": functionality,
        "expiration": expiration,
    }


# ---------- Pipeline ----------

def save_csv(records: list[dict]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=CSV_FIELDS,
            delimiter=CSV_DELIMITER,
            quoting=csv.QUOTE_MINIMAL,
            extrasaction="ignore",
        )
        writer.writeheader()
        for rec in records:
            writer.writerow({k: ("" if rec.get(k) is None else rec.get(k)) for k in CSV_FIELDS})


def main():
    started = time.time()

    print("Phase 1: enumerating services from WP API...")
    services = fetch_all_services()
    print(f"  found {len(services)} services in {time.time() - started:.1f}s")

    print("\nPhase 2: scraping service pages for cookie URLs...")
    t2 = time.time()
    service_name_by_link: dict[str, str] = {}
    for svc in services:
        link = svc.get("link")
        if not link:
            continue
        service_name_by_link[link] = svc.get("name") or svc.get("slug") or "?"

    cookie_urls_by_service: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(scrape_service_cookies, link): link
                for link in service_name_by_link}
        for fut in as_completed(futs):
            link = futs[fut]
            try:
                cookie_urls_by_service[link] = fut.result()
            except Exception as e:
                print(f"  [{service_name_by_link[link]}] error: {e}")
                cookie_urls_by_service[link] = []

    total_cookie_urls = sum(len(v) for v in cookie_urls_by_service.values())
    print(f"  collected {total_cookie_urls} cookie URLs in {time.time() - t2:.1f}s")

    print("\nPhase 3 + 4: privacy URLs and cookie details concurrently...")
    t34 = time.time()
    services_with_cookies = [link for link, cs in cookie_urls_by_service.items() if cs]
    work = [
        (svc_link, cookie_url)
        for svc_link, cookies in cookie_urls_by_service.items()
        for cookie_url in cookies
    ]

    # Phase 3 — kick off in its own pool so it runs alongside Phase 4.
    phase3_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="p3")
    phase3_futs = {phase3_pool.submit(scrape_vendor_privacy_url, link): link
                   for link in services_with_cookies}

    # Phase 4 — main pool. Records are written without service_url; merged below.
    records: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="p4") as pool4:
        futs = {pool4.submit(scrape_cookie_detail, cookie_url): (svc_link, cookie_url)
                for svc_link, cookie_url in work}
        for done, fut in enumerate(as_completed(futs), start=1):
            svc_link, cookie_url = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"name": None, "error": str(e)}
            rec["service_name"] = service_name_by_link.get(svc_link, "")
            rec["_svc_link"] = svc_link  # internal; CSV writer ignores via extrasaction
            records.append(rec)
            if done % 100 == 0:
                print(f"  phase 4: {done}/{len(work)} cookies scraped...")
            if done % CHECKPOINT_EVERY == 0:
                save_csv(records)  # service_url empty until Phase 3 merge below
    print(f"  phase 4 done in {time.time() - t34:.1f}s")

    # Collect Phase 3 results (typically already complete by now since it's smaller).
    privacy_url_by_service: dict[str, str | None] = {}
    for fut in as_completed(phase3_futs):
        link = phase3_futs[fut]
        try:
            privacy_url_by_service[link] = fut.result()
        except Exception:
            privacy_url_by_service[link] = None
    phase3_pool.shutdown()
    enriched = sum(1 for v in privacy_url_by_service.values() if v)
    print(f"  phase 3 done: {enriched}/{len(services_with_cookies)} privacy URLs found")

    # Merge privacy URLs into records.
    for rec in records:
        rec["service_url"] = privacy_url_by_service.get(rec.pop("_svc_link", ""))

    save_csv(records)
    print(f"\nSaved {len(records)} cookie records to {OUTPUT_FILE}")
    print(f"Total time: {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
