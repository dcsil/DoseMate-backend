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

---

## 📈 Progress Tracking API (New)

Endpoints:
- `GET /users/{user_id}/progress?metric_name=&limit=` – list latest progress entries (default limit 50)
- `POST /users/{user_id}/progress` – create a new progress entry. Body: `{ "metric_name": "streak_days", "value": 5, "int_value": 5 }`

Example response item:
```json
{
	"id": "4c1aef0d-...",
	"user_id": "9b821e33-...",
	"metric_name": "streak_days",
	"value": 5.0,
	"int_value": 5,
	"created_at": "2025-10-16T12:34:56.000Z"
}
```

### Frontend Fetch Examples (TypeScript)
```ts
const API = process.env.API_BASE;

export async function fetchProgress(userId: string, metricName?: string) {
	const params = new URLSearchParams();
	if (metricName) params.append('metric_name', metricName);
	const res = await fetch(`${API}/users/${userId}/progress?${params}`);
	if (!res.ok) throw new Error('Failed progress fetch');
	return res.json();
}

export async function createProgress(userId: string, metric: string, value: number, intValue?: number) {
	const res = await fetch(`${API}/users/${userId}/progress`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ metric_name: metric, value, int_value: intValue })
	});
	if (!res.ok) throw new Error('Failed progress create');
	return res.json();
}
```

### Notes / Next Steps
- Add auth guard (require user ID from token rather than path).
- Add aggregation endpoint (e.g. latest value only `/users/{id}/progress/latest`).
- Consider pruning old entries or summarizing daily metrics.
- Add tests for progress CRUD (mock DB / add integration test once DB available).

