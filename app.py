import streamlit as st
from datetime import date
import subprocess
import sys
import json
from pathlib import Path

st.set_page_config(page_title="Cookie Policy Generator", layout="centered")

st.title("🍪 Cookie Policy Generator (MVP)")

st.markdown(
    "Введи URL сайта, нажми **Generate Policy** — приложение просканирует сайт (cookies) и сгенерирует политику и превью баннера."
)

url = st.text_input("Enter website URL (include https://):", "https://example.com")

def scan_site(url: str) -> dict:
    """Run the scanner in a separate Python process (scan_one.py) and parse JSON output.

    This avoids launching Playwright (which spawns subprocesses) inside the Streamlit
    process where asyncio subprocess support may be unavailable.
    """
    script = Path(__file__).with_name("scan_one.py")
    if not script.exists():
        raise FileNotFoundError(f"Scanner script not found: {script}")

    # Use the same Python executable that's running Streamlit so the venv is used.
    cmd = [sys.executable, str(script), url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # Include stderr for debugging
        raise RuntimeError(f"Scanner failed (rc={proc.returncode}): {proc.stderr.strip()}")

    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        raise RuntimeError(f"Failed to parse scanner output: {e}\nOutput:\n{proc.stdout}")

    return data

def classify_cookie(cookie: dict) -> str:
    name = (cookie.get("name") or "").lower()
    if "session" in name or "csrf" in name:
        return "Essential"
    if "ga" in name or "gid" in name or "analytics" in name:
        return "Analytics"
    if "ads" in name or "marketing" in name or "fb" in name:
        return "Marketing"
    return "Unclassified"

def generate_policy_text(site_name: str, cookies: list) -> str:
    # Template-based policy using the user's provided English template
    last_updated = date.today().strftime("%d.%m.%Y")

    def fmt_cookie_row(c):
        name = c.get("name") or "<no-name>"
        ctype = c.get("category", "Unclassified")
        domain = c.get("domain", site_name)
        expires = c.get("expires", "session")
        return f"- **{name}** | {ctype} | domain: {domain} | expires: {expires}"

    # Split cookies into first-party vs third-party by domain (simple heuristic)
    first_party = []
    third_party = []
    for c in cookies or []:
        dom = (c.get("domain") or "").lstrip('.')
        if dom and dom in site_name:
            first_party.append(c)
        else:
            third_party.append(c)

    lines = []
    lines.append(f"[Last Updated: {last_updated}]")
    lines.append("# Cookie Policy")
    lines.append("")
    lines.append("This Cookie Policy (the \"Policy\") explains how we use cookies and other similar technologies to recognize you when you visit our website at [WEBSITE ADDRESS] (the \"Website\"). It explains what these technologies are, why we use them, and your rights to control their use.")
    lines.append("")
    lines.append("Please take the time to read this Policy carefully. If you have any questions or comments, please contact us at [CONTACT EMAIL].")
    lines.append("")
    lines.append("## What are cookies")
    lines.append("Cookies are small data files that are placed on your computer or mobile device when you visit a website. Cookies are widely used by website owners to make their websites work, or to work more efficiently, as well as to provide reporting information.")
    lines.append("")
    lines.append("## What cookies we use")
    lines.append("We use first-party and third-party cookies for several reasons. They are categorized as follows:")
    lines.append("")
    lines.append("### Technical and Functional (Strictly Necessary) Cookies")
    lines.append("These cookies are necessary for the Website to function properly when you visit it and cannot be disabled on our systems.")
    lines.append("")
    lines.append("### Analytical Cookies")
    lines.append("These cookies allow us to understand how you use our Website (e.g., count visits and traffic sources) so we can measure and improve the performance of our site and make our Website more user-friendly in the future.")
    lines.append("")
    lines.append("### Marketing Cookies")
    lines.append("These cookies may be set through our site by our advertising partners. They may be used by those companies to build a profile of your interests and show you relevant adverts on other sites.")
    lines.append("")
    lines.append("## Detailed list of cookies we use")
    lines.append("")
    lines.append("### First-Party Cookies")
    lines.append("")
    if not first_party:
        lines.append("No first-party cookies detected during the scan.")
    else:
        for c in first_party:
            lines.append(fmt_cookie_row(c))

    lines.append("")
    lines.append("### Third-Party Cookies")
    lines.append("")
    if not third_party:
        lines.append("No third-party cookies detected during the scan.")
    else:
        for c in third_party:
            provider = c.get("provider", "")
            if provider:
                lines.append(fmt_cookie_row(c) + f" | provider: {provider}")
            else:
                lines.append(fmt_cookie_row(c))

    lines.append("")
    lines.append("## How to manage cookie settings")
    lines.append("You can accept or refuse certain types of cookies when you first visit our Website via the cookie banner, or at any time in our cookie preference center / privacy settings panel.")
    lines.append("")
    lines.append("You can also manage cookies through your browser settings. Most browsers allow you to: see what cookies you've got and delete them individually, block third-party cookies, or block cookies from particular sites.")
    lines.append("")
    lines.append("## Policy Updates")
    lines.append("We may update this Cookie Policy from time to time to reflect changes to the cookies we use or for other operational, legal, or regulatory reasons. Please re-visit this Policy regularly to stay informed about our use of cookies.")

    return "\n".join(lines)

if st.button("Generate Policy"):
    if not url.startswith("http"):
        st.error("Please enter a full URL starting with http:// or https://")
    else:
        with st.spinner("Scanning site... This may take a few seconds..."):
            try:
                data = scan_site(url)
            except Exception as e:
                st.error(f"Scan failed: {e}")
                st.stop()

        cookies = data.get("cookies", [])
        for c in cookies:
            c["category"] = classify_cookie(c)

        policy_md = generate_policy_text(url, cookies)

        st.success("✅ Policy generated")
        st.subheader("📜 Cookie Policy (Markdown)")
        st.code(policy_md, language="markdown")

        st.subheader("🍪 Cookie Banner Preview")
        banner_html = """
        <div style="max-width:700px;padding:16px;border-radius:8px;border:1px solid #e2e8f0;background:#fafafa;color:#0f172a;">
            <strong style="font-size:1.05em;">Cookies</strong>
            <p style="margin:8px 0;">We'd like to set cookies to provide you our web-services properly and to improve our website by collecting information on how you use it.</p>
            <p style="margin:8px 0;">For more information on how these cookies work please see our <a href="#" target="_blank">Cookie Policy</a>.</p>
            <p style="margin:8px 0;">You can manage your consent preferences by clicking the "Manage cookies" button.</p>
            <p style="margin:8px 0;">If you decline cookies, only strictly necessary cookies will be set into your browser. Please note that in this case we cannot guarantee that you will be able to use all website features in the fast and convenient way.</p>
            <div style="margin-top:8px;">
                <button id="accept-cookie" style="margin-right:8px;padding:8px 14px;border-radius:6px;background:#10b981;color:white;border:none;">Accept</button>
                <button id="reject-cookie" style="margin-right:8px;padding:8px 14px;border-radius:6px;background:#f3f4f6;border:none;color:#111827;">Reject</button>
                <button id="manage-cookie" style="padding:8px 14px;border-radius:6px;background:#3b82f6;color:white;border:none;">Manage cookies</button>
            </div>
        </div>
        """
        st.markdown(banner_html, unsafe_allow_html=True)

        st.download_button("Download policy as .md", policy_md, file_name="cookie_policy.md", mime="text/markdown")
# Note: don't run a scan at import time. The app runs inside Streamlit's
# runtime which may not support creating subprocesses during module import
# (Playwright launches browser subprocesses). Scans are triggered only when
# the user clicks the "Generate Policy" button above.
