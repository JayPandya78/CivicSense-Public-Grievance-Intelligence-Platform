# CivicSense

CivicSense is a community platform for reporting local issues, tracking their status, and coordinating neighborhood follow-up.

## Features

- Account registration and sign-in
- Civic issue reports with optional photo and location pins
- Personal report history, status timelines, and in-app notifications
- Community report search, filters, map, updates, and support
- Admin triage with categories, departments, priorities, response targets, approval, decline reasons, and resolution
- Rules-based NLP suggestions for language, category, urgency, report summaries, place hints, possible spam, and similar public reports

## Run locally

### Backend

From the project root, install dependencies and start the API:

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

The API is available at `http://127.0.0.1:8000`.

### Frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (usually `http://127.0.0.1:5173`).

## Configure an administrator

Register the intended reviewer through the app, then look up their user ID in the local SQLite database:

```powershell
python -c "import sqlite3; print(sqlite3.connect(r'backend\civicsense.sqlite3').execute('SELECT id FROM users WHERE email = ?', ('reviewer@example.com',)).fetchone()[0])"
$env:CIVICSENSE_ADMIN_USER_ID = "<account-id-from-the-query>"
python -m uvicorn app.main:app --app-dir backend --reload
```

Only the configured account can access the admin review queue.

## Local data and map

The backend creates its SQLite database and uploaded-photo directory locally. They are excluded from Git because they contain user-specific data. Do not commit real user records, photos, credentials, or environment files.

The community map uses OpenStreetMap tiles and updates periodically or on request. Residents can submit without sharing coordinates; they can use browser GPS or choose an exact map point, and only reports with shared coordinates appear as pins.

## NLP assistance

CivicSense runs lightweight, rules-based text analysis locally when a report is previewed or submitted. It detects supported writing systems, suggests an issue category, flags urgency or possible spam for human review, extracts a short extractive summary and place hints, and compares the report with recent approved/resolved public reports. These are advisory heuristics—not a trained classifier, a decision to reject a report, or measured model accuracy. Staff must review the suggestions.
