# DoseMate-backend

FastAPI backend service for DoseMate, providing APIs for medication schedules, reminders, authentication, and data storage.

---

## 🚀 Quick start

Reference: [FastAPI Requirements](https://fastapi.tiangolo.com/#requirements)

#### 1. Install `Python 3.11.4`

Download from [python.org](https://www.python.org/downloads/release/python-3114/) and set it up.

```bash
python --version     # should print Python 3.11.4
python -m pip install --upgrade pip
```

#### 2. Clone repo & set current directory to root

```
git clone https://github.com/dcsil/DoseMate-backend.git
cd dosemate-backend
```

#### 3. Create & Activate Virtual Environment

```bash
python -m venv .venv
# then activate (choose one depending on OS)
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

✅ If active, your terminal prompt should start with (.venv).

#### 4. Install Project Dependencies

```bash
pip install -r requirements.txt
```

Keep this file updated to ensure others can reproduce your environment.

#### 5. Run the Server

```bash
uvicorn app.main:app --reload --port 8000
```

- API root: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs

#### 6. Expose via Ngrok

```bash
ngrok http 8000
```

Note the Forwarding URL, e.g. `https://example.ngrok-free.dev -> http://localhost:8000`

Use this URL in Google OAuth Authorized Redirect URIs (more info in `.env.template`).
Confirm it works by visiting the forwarding link in your browser.

#### 7. Setting up env

Use `.env.template` as reference and fill in required keys.
