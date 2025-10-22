Cookie Policy Generator (MVP)

Simple Streamlit app that scans a website's cookies using Playwright and generates a cookie policy.

Quick local run

1. Create a Python 3.11 venv and activate it:

   ```powershell
   py -3.11 -m venv .\venv311-py311
   & .\venv311-py311\Scripts\Activate.ps1
   ```

2. Install requirements:

   ```powershell
   python -m pip install --upgrade pip setuptools wheel
   python -m pip install -r requirements.txt
   python -m playwright install chromium
   ```

3. Run the app:

   ```powershell
   streamlit run app.py
   ```

Deploying on GitHub (Streamlit Cloud)

1. Commit your repo to GitHub (root contains `app.py`, `requirements.txt`).
2. On Streamlit Cloud, "New app" → connect your GitHub repo → pick branch and `app.py`.
3. Streamlit Cloud will install packages from `requirements.txt` and run `app.py`.

Notes for Streamlit Cloud

- Playwright needs browser binaries. Streamlit Cloud's build runs in a container; you may need to add a small setup step in the app to call `playwright install chromium` at startup, or use a `packages.txt`/build script depending on the host.
- If Streamlit Cloud blocks subprocess creation, consider running Playwright in a separate worker or using requests-only scanning.

Alternative: Deploy on Render

1. Create a new Web Service on Render, link your GitHub repo.
2. Set the build command: `pip install -r requirements.txt && playwright install chromium`.
3. Set the start command: `streamlit run app.py --server.port $PORT`.

Security & notes

- Keep `venv` out of Git. Use `.gitignore` to exclude `venv*`, `.pytest_cache`, `__pycache__/`.
- Review Playwright/browser usage before deploying publicly — automated browser runs can be resource intensive.

If you want, I can create a `.gitignore` and a Git commit for you, and prepare a small start script to ensure `playwright install chromium` runs during deploy.
