# DoseMate-backend

FastAPI backend service for DoseMate, providing APIs for medication schedules, reminders, authentication, and data storage.

---

# FastAPI Project Setup

This guide walks you through setting up a FastAPI project using **Python 3.11.4** and a virtual environment.

Reference: [FastAPI Requirements](https://fastapi.tiangolo.com/#requirements)

---

## 1. Install Python 3.11.4

Download from [python.org](https://www.python.org/downloads/release/python-3114/).

During installation:

- ✅ Check **"Add Python to PATH"**
- ✅ Check **"Install for all users"**
- ✅ Include **development headers**

Confirm installation:

```bash
python --version
```

this should return: `Python 3.11.4`

## 2. Create and Activate a Virtual Environment (Bash)

From the root of your project:
\*Make sure to select right version of python if prompted multiple versions

```bash
python -m venv .venv
source .venv/bin/activate
```

## 3. Upgrade pip

```bash
python -m pip install --upgrade pip
```

## 4. Install Project Dependencies

From the root of your project:

```bash
pip install -r requirements.txt
```

## 5. Run the Server

After adding your FastAPI app code:

```bash
uvicorn main:app --reload
```

Visit http://127.0.0.1:8000 to verify, and check the interactive API docs at http://127.0.0.1:8000/docs
