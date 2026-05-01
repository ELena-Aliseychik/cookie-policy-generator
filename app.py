import streamlit as st
from datetime import date
import subprocess
import sys
import json
import os
import time
from pathlib import Path
#i scraped the lokal storage too but dont know what to do. Its ugly

# Конфигурация страницы
# Page configuration
st.set_page_config(page_title="Cookie Policy Generator", layout="centered")

# --- КОНСТАНТЫ И БАЗА ДАННЫХ ---
# --- CONSTANTS AND DATABASE ---
DB_FILE = Path(__file__).parent / "cookie_db.json"

if DB_FILE.exists():
    with open(DB_FILE, "r", encoding="utf-8") as f:
        COOKIE_DB = json.load(f)
else:
    COOKIE_DB = {}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(COOKIE_DB, f, indent=2, ensure_ascii=False)

# --- ВНЕШНИЕ СКРИПТЫ ---
# --- EXTERNAL SCRIPTS ---

def scan_site(url: str) -> dict:
    script = Path(__file__).with_name("scan_one.py")
    cmd = [sys.executable, str(script), url]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if proc.returncode != 0:
        raise RuntimeError(f"Scanner crashed: {proc.stderr.strip()}")

    try:
        result = json.loads(proc.stdout)
        if "error" in result:
             raise RuntimeError(result["error"])
        return result
    except json.JSONDecodeError:
        raise RuntimeError(f"Invalid JSON output: {proc.stdout}")

def fetch_cookie_online(cookie_name: str) -> dict | None:
    script = Path(__file__).with_name("fetch_one.py")
    cmd = [sys.executable, str(script), cookie_name]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except:
        return None

def classify_and_enrich_cookie(cookie: dict):
    name = cookie.get("name", "")
    
    if name in COOKIE_DB:
        cookie.update(COOKIE_DB[name])
        return

    if " " not in name and "/" not in name and len(name) < 50: 
        online_info = fetch_cookie_online(name)
        if online_info:
            COOKIE_DB[name] = online_info
            save_db()
            cookie.update(online_info)
            return

    name_lower = name.lower()
    cat = "Unclassified"
    
    if any(x in name_lower for x in ["session", "csrf", "id", "auth", "token", "consent"]):
        cat = "Necessary"
    elif any(x in name_lower for x in ["ga", "gid", "analytics", "ym", "metrika", "stats"]):
        cat = "Analytical"
    elif any(x in name_lower for x in ["ads", "marketing", "fbp", "pixel", "tr"]):
        cat = "Marketing"
    elif any(x in name_lower for x in ["lang", "pref", "theme", "ui", "currency", "mode"]):
        cat = "Preference"

    cookie["category"] = cat
    cookie["provider"] = cookie.get("domain", "Unknown")
    default_descriptions = {
        "Necessary": "Essential cookie to ensure core website functionality and security.",
        "Analytical": "Used to collect anonymous data on how visitors interact with the website.",
        "Marketing": "Used to track visitors across websites to display relevant advertisements.",
        "Preference": "Used to remember user settings and preferences (e.g., language or region).",
        "Unclassified": "No description available. Pending classification."
    }
    
    cookie["description"] = default_descriptions.get(cat, "No description available.")

def generate_policy_text(site_name: str, cookies: list, local_storage: list | None = None) -> str:
    last_updated = date.today().strftime("%d.%m.%Y")
    
    def get_expiry_str(timestamp):
        if timestamp is None or timestamp == -1:
            return "Session"
        seconds_left = timestamp - time.time()
        if seconds_left <= 0: return "Session (Expired)"
        days = seconds_left / (24 * 3600)
        
        if days < 1: return "Less than 1 day"
        elif days < 30: return f"{int(days)} days"
        elif days < 365:
            months = round(days / 30)
            return f"{months} months"
        else:
            years = round(days / 365, 1)
            return f"{int(years)} year(s)" if years.is_integer() else f"{years} years"

    # Функция для создания Markdown таблицы (ИСПРАВЛЕНО)
    # Function to create a Markdown table (FIXED)
    def create_cookie_table(cookie_list):
        if not cookie_list:
            return "_No cookies found in this category._"
        
        table_lines = []
        table_lines.append("| Name | Category | Domain | Expiration | Description |")
        table_lines.append("| :--- | :--- | :--- | :--- | :--- |")
        
        for c in cookie_list:
            name = c.get("name") or "Unknown"
            ctype = c.get("category", "Unclassified")
            domain = c.get("domain", site_name)
            desc = c.get("description", "No description.")
            expiry = get_expiry_str(c.get("expires"))
            
            # Очистка
            # Cleanup
            desc = desc.replace("\n", " ").replace("|", "/").strip()
            name = name.replace("|", "")
            domain = domain.replace("|", "")
            
            # Если имя очень длинное, можно его обрезать или разбить, но обычно куки короткие.
            # If the name is very long, you can trim or split it, but cookies are usually short.
            row = f"| **{name}** | {ctype} | {domain} | {expiry} | {desc} |"
            table_lines.append(row)
            
        return "\n".join(table_lines)

    first_party = []
    third_party = []
    
    for c in cookies or []:
        dom = (c.get("domain") or "").lstrip('.')
        if site_name in dom or dom in site_name:
            first_party.append(c)
        else:
            third_party.append(c)

    lines = []
    lines.append(f"**Last Updated:** {last_updated}")
    lines.append("")
    lines.append("# Cookie Policy")
    lines.append("")
# --- INTRO ---
    lines.append(f"This Cookie Policy explains how we use cookies and similar technologies to recognize you when you visit our website at **{site_name}**. It explains what these technologies are and why we use them, as well as your rights to control our use of them.")
    lines.append("")
    lines.append("The Website owned by **[The Company Name]** (referred to as “we”, “us”, or “our”). Please take the time to read this Policy carefully. If you have any questions or comments, please contact us via email at **[The contact email]**.")
    lines.append("")
    lines.append("## What are cookies?")
    lines.append("Cookies are small data files that are placed on your computer or mobile device when you visit a website. Cookies are used by website owners in order to make their websites work, or to work more efficiently, as well as to provide reporting information.")
    lines.append("")
    lines.append("Cookies have many different features, such as allowing you to navigate between pages efficiently, remembering your preferences, and generally improving your user experience. They can also help ensure that the advertisements you see online are more relevant to you and your interests.")
    lines.append("")
    lines.append('Cookies set by the website owner are called "first party cookies". Cookies set by other parties other than the website owner are called "third party cookies". Third party cookies enable third party features or functionality to be provided on or through the website (e.g. like advertising, interactive content and analytics). The parties that set these third party cookies can recognise your computer or mobile device both when it visits the websites in question and also when it visits certain other websites.')
    lines.append("")
    
    lines.append("## Types of Cookies we use")
    lines.append("")
    lines.append("We use different types of cookies to run our website. The table below explains the categories of cookies we use and why:")
    lines.append("")
    

    lines.append("| Category | Description |")
    lines.append("| :--- | :--- |")
    lines.append("| **Necessary** | Essential for website function (login, security, shopping cart). |")
    lines.append("| **Preference** | Remember user choices (language, region, currency). |")
    lines.append("| **Analytical** | Anonymous data collection to improve website performance. |")
    lines.append("| **Marketing** | Track visitors to display relevant ads. |")
    lines.append("")

    lines.append("## Detailed list of cookies")
    lines.append("")
    
    lines.append("### First-Party Cookies")
    lines.append(create_cookie_table(first_party))
    
    lines.append("")
    lines.append("### Third-Party Cookies")
    lines.append(create_cookie_table(third_party))
    lines.append("")
    lines.append("## How can I control cookies?")
    lines.append("You have the right to decide whether to accept or reject specific types of cookies (except of strictly necessary cookies). You can exercise your cookie preferences on the cookie banner.")
    lines.append("")
    lines.append("You can set or amend your web browser controls to accept or refuse cookies. If you choose to reject cookies, you may still use our Website though your access to some functionality and areas of our Website may be restricted. As means by which you can refuse cookies through your web browser controls vary from browser to browser, you should visit your browser's help menu for more information.")
    lines.append("")
    lines.append("## Updates to this Policy")
    lines.append("We may update this Cookie Policy from time to time in order to reflect, for example, changes to the cookies we use or for other operational, legal, or regulatory reasons. Please therefore re-visit this Cookie Policy regularly to stay informed about our use of cookies and related technologies.")

    return "\n".join(lines)

# --- ИНТЕРФЕЙС ---
# --- INTERFACE ---

st.title("🍪 Cookie Policy Generator")
st.markdown(
    "Введите URL сайта. Приложение просканирует сайт (глубина - до 15 вкладок) и сгенерирует полный текст Политики cookies. Не забудьте сверить результат техническими специалистами."
    # Enter the site URL. The app will scan the site (depth - up to 15 tabs) and generate the full Cookie Policy text. Don't forget to check the result with technical specialists.
)

url = st.text_input("URL сайта (с https://):", "https://example.com")

if st.button("Generate Policy"):
    if not url.startswith("http"):
        st.error("Пожалуйста, введите полный URL (начиная с http:// или https://)")
        st.stop()
    
    data = None
    with st.spinner("🕵️ Сканируем сайт, переходим по страницам, соглашаемся на баннеры и ищем куки... Это займет время."):
        # Scanning the site, navigating pages, accepting banners, and searching for cookies... This will take some time.
        try:
            data = scan_site(url)
        except Exception as e:
            st.error(f"Ошибка сканирования: {e}")
            st.stop()

    cookies = data.get("cookies", [])
    st.info(f"Сканирование завершено. Найдено cookies: {len(cookies)}")
    # Scan complete. Cookies found: {len(cookies)}
    local_storage = data.get("local_storage", [])

    with st.spinner("🧠 Генерируем политику..."):
        # Generating policy...
        progress_bar = st.progress(0)
        for i, c in enumerate(cookies):
            classify_and_enrich_cookie(c)
            progress_bar.progress((i + 1) / len(cookies))
        progress_bar.empty()

    with st.spinner("🧠 Генерируем политику..."):
        # Generating policy...
        progress_bar = st.progress(0)
        for i, c in enumerate(cookies):
            classify_and_enrich_cookie(c)
            progress_bar.progress((i + 1) / len(cookies))
        progress_bar.empty()
            
    policy_md = generate_policy_text(url, cookies, local_storage)

    st.success("✅ Политика готова!")
    # Policy is ready!
    
    st.subheader("📜 Generated Policy Document")
    st.markdown("---")
    st.markdown(policy_md)
    st.markdown("---")

    st.download_button(
        label="📥 Скачать как .md файл",
        data=policy_md,
        file_name="cookie_policy.md",
        mime="text/markdown"
    )
    # Download as .md file